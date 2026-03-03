import MetaTrader5 as mt5
import pandas as pd
import time
import requests
from datetime import datetime
import config
from engine.risk import RiskManager
from engine.selector import StrategySelector

class BabataTrinityV6:
    def __init__(self):
        print(">>> [1/3] 正在建立 MT5 神经连接...")
        if not mt5.initialize(): 
            print("❌ MT5 失败"); quit()
        
        print(">>> [2/3] 正在同步账户风控...")
        acc = mt5.account_info()
        self.risk = RiskManager(acc.equity)
        
        print(">>> [3/3] 正在部署策略指挥部 (轻量化加载模式)...")
        # 优化：动态初始化品种，不在此处拉取大量历史数据
        self.selectors = {s: StrategySelector(s) for s in config.SYMBOLS}
        self.current_day = datetime.now().day
        self.last_heartbeat = 0

    def send_tg(self, msg):
        try: requests.post(f"https://api.telegram.org/bot{config.TG_TOKEN}/sendMessage", 
                           data={"chat_id": config.TG_CHAT_ID, "text": msg}, timeout=5)
        except: pass

    def execute_trinity(self, s, t, sig_reason):
        tk = mt5.symbol_info_tick(s)
        info = mt5.symbol_info(s)
        if not tk or not info: return
        entry = tk.ask if t == 0 else tk.bid
        atr_points = self.risk.get_atr_points(s)
        sl_points = atr_points * 2.0
        lot = self.risk.calculate_lot(s, sl_points)
        sl = entry - (sl_points * info.point) if t == 0 else entry + (sl_points * info.point)
        legs = [{"magic": config.MAGIC_BASE + 1, "tp_mult": config.LEG1_TP_RATIO, "name": "Scalper"},
                {"magic": config.MAGIC_BASE + 2, "tp_mult": config.LEG2_TP_RATIO, "name": "Runner"},
                {"magic": config.MAGIC_BASE + 3, "tp_mult": config.LEG3_TP_RATIO, "name": "Predator"}]
        for leg in legs:
            tp = 0.0
            if leg["tp_mult"] > 0:
                tp = entry + (sl_points * leg["tp_mult"] * info.point) if t == 0 else entry - (sl_points * leg["tp_mult"] * info.point)
            req = {"action": mt5.TRADE_ACTION_DEAL, "symbol": s, "volume": lot, "type": t, "price": entry, 
                   "sl": round(sl, info.digits), "tp": round(tp, info.digits), "magic": leg["magic"], 
                   "comment": f"V6.7_{leg['name']}", "type_filling": config.FILLING_MODE}
            res = mt5.order_send(req)
            if res.retcode == 10009:
                self.send_tg(f"🚀 **{leg['name']} 成功发射**\n品种: {s} | 手数: {lot}\n原因: {sig_reason}")

    def run(self):
        log_msg = f"🔱 **Babata V6.7 Trinity** 已上线!\n基准: ${self.risk.equity_start:.0f}"
        print(f"\n{log_msg}\n")
        self.send_tg(log_msg)
        
        while True:
            # 1. 每日重置
            now = datetime.now()
            if now.day != self.current_day:
                self.risk.equity_start = mt5.account_info().equity
                self.current_day = now.day
                self.send_tg("🌅 新的一天，风控已重置")

            # 2. 追踪管理
            for p in (mt5.positions_get() or []):
                if config.MAGIC_BASE < p.magic < config.MAGIC_BASE + 10:
                    self.risk.apply_trinity_management(p)

            # 3. 扫描品种
            for s in config.SYMBOLS:
                if not mt5.symbol_select(s, 1): continue
                # 动态获取信号 (Selector 内部会自动 fetch_data)
                try:
                    sig, reason = self.selectors[s].get_best_signal()
                    if sig != 0:
                        if not any(p.symbol == s for p in (mt5.positions_get(magic=config.MAGIC_BASE+1) or [])):
                            print(f"🎯 发现机会: {s} | {reason}")
                            self.execute_trinity(s, 0 if sig == 1 else 1, reason)
                except Exception as e:
                    print(f"⚠️ 扫描品种 {s} 时出错: {e}")

            if time.time() - self.last_heartbeat > 60:
                print(f"[{datetime.now().strftime('%H:%M')}] 📡 V6.7 正在扫描中... (健康)")
                self.last_heartbeat = time.time()

            time.sleep(config.POLL_SECONDS)

if __name__ == "__main__":
    try: BabataTrinityV6().run()
    except Exception as e:
        print(f"💀 Fatal: {e}")
        import traceback; traceback.print_exc()
        mt5.shutdown()
