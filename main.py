import MetaTrader5 as mt5
import time
import os
import traceback
from datetime import datetime
import config
from engine.risk import RiskManager
from engine.reporter import Reporter
from engine.selector import StrategySelector

class BabataUltimateV6:
    def __init__(self):
        if not mt5.initialize():
            print("❌ MT5 Init Failed")
            quit()
        
        self.reporter = Reporter()
        self.risk = RiskManager(mt5.account_info().equity)
        self.selectors = {s: StrategySelector(s) for s in config.SYMBOLS}
        self.current_day = datetime.now().day
        
        log_msg = f"🚀 **Babata V6.0 Ultimate** Online!\nEquity: ${self.risk.equity_start}\nSymbols: {config.SYMBOLS}"
        print(log_msg)
        self.reporter.send_tg(log_msg)

    def run(self):
        while True:
            # 1. New Day Reset
            now = datetime.now()
            if now.day != self.current_day:
                self.risk.equity_start = mt5.account_info().equity
                self.current_day = now.day
                self.reporter.send_tg(f"🌅 New Day. Risk Baseline Reset: ${self.risk.equity_start}")

            # 2. Risk Check
            info = mt5.account_info()
            if self.risk.check_drawdown(info.equity):
                self.reporter.send_tg("🛑 5% Drawdown Limit Hit. Stopping for today.")
                time.sleep(3600); continue

            # 3. Strategy Loop
            for s in config.SYMBOLS:
                if not mt5.symbol_select(s, 1): continue
                
                # Dynamic Selector
                sig, reason = self.selectors[s].get_best_signal()
                
                if sig != 0:
                    # Check if already in position
                    if len(mt5.positions_get(symbol=s, magic=config.MAGIC_NUMBER)) > 0: continue
                    
                    # Entry Execution
                    tk = mt5.symbol_info_tick(s)
                    entry = tk.ask if sig == 1 else tk.bid
                    lot = self.risk.calculate_lot(info.balance)
                    
                    # ATR Stops
                    atr = self.risk.get_atr(s, mt5.TIMEFRAME_M15)
                    sl, tp = self.risk.refine_stops(s, 0 if sig == 1 else 1, entry, atr)
                    
                    req = {
                        "action": mt5.TRADE_ACTION_DEAL, "symbol": s, "volume": lot,
                        "type": mt5.ORDER_TYPE_BUY if sig == 1 else mt5.ORDER_TYPE_SELL,
                        "price": entry, "sl": sl, "tp": tp, "magic": config.MAGIC_NUMBER,
                        "comment": reason, "type_filling": config.FILLING_MODE
                    }
                    res = mt5.order_send(req)
                    
                    if res and res.retcode == 10009:
                        self.reporter.log_trade(s, config.MAGIC_NUMBER, "BUY" if sig == 1 else "SELL", entry, lot, sl, tp, reason)
                        self.reporter.send_tg(f"🔥 **Trade Executed**\nSymbol: {s}\nAction: {'BUY' if sig == 1 else 'SELL'}\nLot: {lot}\nReason: {reason}")

            # 4. Reporting (End of day)
            if now.strftime("%H:%M") == config.DAILY_REPORT_HHMM:
                report = self.reporter.generate_daily_report()
                self.reporter.send_tg(report)
                time.sleep(60)

            time.sleep(config.POLL_SECONDS)

if __name__ == "__main__":
    try:
        BabataUltimateV6().run()
    except Exception as e:
        print(f"💀 Fatal Error: {e}")
        traceback.print_exc()
    finally:
        mt5.shutdown()
