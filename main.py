import MetaTrader5 as mt5
import time
import os
import traceback
from datetime import datetime
import config
from engine.risk import RiskManager
from engine.reporter import Reporter
from engine.selector import StrategySelector
from engine.evolve import analyze_and_evolve

class BabataPredatorV6:
    def __init__(self):
        if not mt5.initialize(): quit()
        self.reporter = Reporter()
        self.risk = RiskManager(mt5.account_info().equity)
        self.selectors = {s: StrategySelector(s) for s in config.SYMBOLS}
        self.current_day = datetime.now().day
        self.last_heartbeat = 0
        
        msg = f"🐺 **Babata V6.6 Predator** Active!\nTarget: Infinite RR & Self-Evolution"
        self.reporter.send_tg(msg); print(msg)

    def run(self):
        while True:
            now = datetime.now()
            # 1. Weekly Evolution (Every Saturday 10:00)
            if now.strftime("%A") == "Saturday" and now.hour == 10 and now.minute == 0:
                count = analyze_and_evolve()
                self.reporter.send_tg(f"🧠 **Self-Evolution Complete**\nBlacklisted {count} underperforming zones.")
                time.sleep(60)

            # 2. Daily Reset
            if now.day != self.current_day:
                self.risk.equity_start = mt5.account_info().equity
                self.current_day = now.day
                self.reporter.send_tg(f"🌅 New Day Reset. Base: ${self.risk.equity_start:.0f}")

            # 3. Trailing Management (CRITICAL for V6.6)
            positions = mt5.positions_get(magic=config.MAGIC_NUMBER)
            if positions:
                for pos in positions:
                    self.risk.apply_smart_trailing(pos)

            # 4. Risk Check
            info = mt5.account_info()
            if self.risk.check_drawdown(info.equity):
                time.sleep(60); continue

            # 5. Entry Loop
            for s in config.SYMBOLS:
                if not mt5.symbol_select(s, 1): continue
                sig, reason = self.selectors[s].get_best_signal()
                
                if sig != 0:
                    if len(mt5.positions_get(symbol=s, magic=config.MAGIC_NUMBER)) > 0: continue
                    tk = mt5.symbol_info_tick(s)
                    entry = tk.ask if sig == 1 else tk.bid
                    lot = self.risk.calculate_lot(info.balance)
                    atr = self.risk.get_atr(s, mt5.TIMEFRAME_M15)
                    sl, tp = self.risk.refine_stops(s, 0 if sig == 1 else 1, entry, atr)
                    
                    req = {
                        "action": mt5.TRADE_ACTION_DEAL, "symbol": s, "volume": round(lot, 2),
                        "type": mt5.ORDER_TYPE_BUY if sig == 1 else mt5.ORDER_TYPE_SELL,
                        "price": entry, "sl": sl, "tp": tp, "magic": config.MAGIC_NUMBER,
                        "comment": reason, "type_filling": config.FILLING_MODE
                    }
                    res = mt5.order_send(req)
                    if res and res.retcode == 10009:
                        self.reporter.log_trade(s, config.MAGIC_NUMBER, "BUY" if sig == 1 else "SELL", entry, lot, sl, tp, reason)
                        self.reporter.send_tg(f"🐺 **Predator Strike**\n{s} | {'BUY' if sig == 1 else 'SELL'}\nLot: {lot:.2f}\n{reason}")

            if time.time() - self.last_heartbeat > 300:
                print(f"[{now.strftime('%H:%M')}] 🐺 Predator Scanning..."); self.last_heartbeat = time.time()
            time.sleep(config.POLL_SECONDS)

if __name__ == "__main__":
    try: BabataPredatorV6().run()
    except Exception as e:
        msg = f"💀 Predator Crashed: {e}\n{traceback.format_exc()}"
        print(msg); mt5.shutdown()
