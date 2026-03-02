import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import time
import traceback
import requests
from datetime import datetime
import pytz
import config

# --- 基础工具 ---
def now_local_dt():
    try:
        tz = pytz.timezone(config.LOCAL_TZ)
        return datetime.now(tz=tz)
    except: return datetime.now()

def log(msg: str):
    print(f"[{now_local_dt().strftime('%H:%M:%S')}] {msg}", flush=True)

# --- 📡 Telegram 推送模块 ---
def send_tg(message):
    try:
        url = f"https://api.telegram.org/bot{config.TG_TOKEN}/sendMessage"
        data = {"chat_id": config.TG_CHAT_ID, "text": message}
        # 设置 5 秒超时，防止卡死主线程
        requests.post(url, data=data, timeout=5)
    except Exception as e:
        log(f"⚠️ TG 推送失败: {e}")

# --- 🧬 动态计算引擎 ---
def get_atr(symbol, timeframe, period=14):
    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, period + 5)
    if rates is None or len(rates) < period: return 0.0
    df = pd.DataFrame(rates)
    df['h-l'] = df['high'] - df['low']
    df['h-pc'] = abs(df['high'] - df['close'].shift(1))
    df['l-pc'] = abs(df['low'] - df['close'].shift(1))
    df['tr'] = df[['h-l', 'h-pc', 'l-pc']].max(axis=1)
    return df['tr'].rolling(period).mean().iloc[-1]

def calc_lot_size(symbol):
    """ 激进复利核心: 余额每增加 $1000，手数增加 0.05 """
    if not config.ENABLE_COMPOUNDING: return 0.01
    
    acc = mt5.account_info()
    if not acc: return 0.01
    
    balance = acc.balance
    lot = (balance / 1000.0) * config.LOT_PER_1000
    lot = round(lot, 2)
    
    # 限制极值
    lot = max(0.01, min(lot, config.MAX_LOT_SIZE))
    return lot

def refine_stops_atr(symbol, order_type, entry_price, timeframe):
    """ 使用 ATR 计算动态止损，并解决 Invalid stops 问题 """
    atr = get_atr(symbol, timeframe, config.ATR_PERIOD)
    if atr == 0: atr = 0.002 # 兜底默认值
    
    dist_sl = atr * config.ATR_MULTIPLIER_SL
    dist_tp = atr * config.ATR_MULTIPLIER_TP
    
    # 获取券商最小限制
    info = mt5.symbol_info(symbol)
    if not info: return 0, 0
    p = info.point
    min_dist_broker = max(info.trade_stops_level or 0, info.trade_freeze_level or 0) * p * 1.5
    
    # 确保 ATR 距离大于券商限制
    final_dist_sl = max(dist_sl, min_dist_broker)
    final_dist_tp = max(dist_tp, min_dist_broker)
    
    sl, tp = 0.0, 0.0
    if order_type == 0: # BUY
        sl = entry_price - final_dist_sl
        tp = entry_price + final_dist_tp
    else: # SELL
        sl = entry_price + final_dist_sl
        tp = entry_price - final_dist_tp
        
    return round(sl, info.digits), round(tp, info.digits)

# --- SMC 策略引擎 ---
class SMCAnalyzer:
    def __init__(self, s, tf):
        self.s, self.tf = s, tf
        r = mt5.copy_rates_from_pos(s, tf, 0, 500)
        self.df = pd.DataFrame(r) if r is not None else None
        if self.df is not None: self.df['ema'] = self.df['close'].ewm(span=200).mean()
    def get_trend(self):
        if self.df is None: return 0
        return 1 if self.df['close'].iloc[-1] > self.df['ema'].iloc[-1] else -1
    def detect_fvg(self):
        if self.df is None or len(self.df) < 5: return 0
        h, l = self.df['high'], self.df['low']
        return 1 if h.iloc[-3] < l.iloc[-1] else (-1 if l.iloc[-3] > h.iloc[-1] else 0)
    def detect_choch(self):
        if self.df is None or len(self.df) < 22: return 0
        h, l, c = self.df['high'].iloc[-20:-1].max(), self.df['low'].iloc[-20:-1].min(), self.df['close'].iloc[-1]
        return 1 if c > h else (-1 if c < l else 0)

# --- 交易主程序 ---
class BabataBot:
    def __init__(self):
        self.equity_start = None
        self.last_heartbeat = 0
    
    def connect(self):
        if not mt5.initialize(): quit()
        self.equity_start = mt5.account_info().equity
        msg = f"🚀 **Babata V5.0 [暴利进化版]** 启动成功!\n账号: `{mt5.account_info().login}`\n余额: `${mt5.account_info().balance}`\n模式: 激进复利 + ATR风控 + TG推送"
        log("上线成功"); send_tg(msg)

    def trade(self, s, t, magic, comment, tf_atr):
        # 1. 检查持仓
        if len(mt5.positions_get(symbol=s, magic=magic) or []) > 0: return
        
        # 2. 获取价格
        tk = mt5.symbol_info_tick(s)
        if not tk: return
        entry = tk.ask if t == 0 else tk.bid
        
        # 3. 计算复利手数
        lot = calc_lot_size(s)
        
        # 4. 计算动态 ATR 止损
        sl, tp = refine_stops_atr(s, t, entry, tf_atr)
        
        # 5. 下单
        req = {
            "action": mt5.TRADE_ACTION_DEAL, "symbol": s, "volume": lot,
            "type": t, "price": entry, "sl": sl, "tp": tp,
            "magic": magic, "comment": comment, "type_filling": config.FILLING_MODE
        }
        res = mt5.order_send(req)
        
        if res.retcode == 10009:
            emoji = "🟢 多单" if t == 0 else "🔴 空单"
            msg = f"{emoji} **开仓成功**\n品种: {s}\n手数: {lot}\n价格: {entry}\nSL: {sl}\nTP: {tp}\n策略: {comment}"
            log(f"开仓: {s} {lot}手"); send_tg(msg)
        else:
            log(f"❌ 下单失败: {res.comment}")

    def run(self):
        self.connect()
        while True:
            # 风控
            if (self.equity_start - mt5.account_info().equity) / self.equity_start >= config.MAX_DAILY_DD_PCT:
                send_tg("🛑 **触发 5% 强制风控，停止交易**"); time.sleep(3600); continue
            
            # 扫描
            for s in config.SYMBOLS:
                if not mt5.symbol_select(s, 1): continue
                
                # 策略 A: 刺客 (M15+M1) -> 用 M1 的 ATR 止损 (紧)
                a15, a1 = SMCAnalyzer(s, 15), SMCAnalyzer(s, 1)
                if a15.get_trend() == 1 and a1.detect_choch() == 1:
                    self.trade(s, 0, config.MAGIC_SCALP, "Scalp_V5", 1)
                elif a15.get_trend() == -1 and a1.detect_choch() == -1:
                    self.trade(s, 1, config.MAGIC_SCALP, "Scalp_V5", 1)
                
                # 策略 B: 猎手 (H4+M15) -> 用 M15 的 ATR 止损 (宽)
                ah4, am15 = SMCAnalyzer(s, 16388), SMCAnalyzer(s, 15)
                if ah4.get_trend() == 1 and am15.detect_fvg() == 1:
                    self.trade(s, 0, config.MAGIC_SWING, "Swing_V5", 15)
                elif ah4.get_trend() == -1 and am15.detect_fvg() == -1:
                    self.trade(s, 1, config.MAGIC_SWING, "Swing_V5", 15)

            # 心跳 (每分钟)
            if time.time() - self.last_heartbeat > 60:
                print(f"[{datetime.now().strftime('%H:%M')}] 📡 V5.0 正在扫描... 复利倍数: {config.LOT_PER_1000}/$1k", flush=True)
                self.last_heartbeat = time.time()
            
            time.sleep(10)

if __name__ == "__main__":
    try: BabataBot().run()
    except Exception as e:
        err = f"💀 **程序崩溃**: {e}\n{traceback.format_exc()}"
        print(err); send_tg(err)
