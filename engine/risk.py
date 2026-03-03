import MetaTrader5 as mt5
import pandas as pd
import config

class RiskManager:
    def __init__(self, equity_start):
        self.equity_start = equity_start

    def check_drawdown(self, current_equity):
        if self.equity_start == 0: return False
        return (self.equity_start - current_equity) / self.equity_start >= config.MAX_DAILY_DD_PCT

    def calculate_lot(self, balance):
        if not config.ENABLE_COMPOUNDING: return 0.01
        lot = (balance / 1000.0) * config.LOT_PER_1000
        return max(0.01, min(round(lot, 2), 5.0))

    def get_atr(self, symbol, timeframe, period=14):
        rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, period + 5)
        if rates is None or len(rates) < period: return 0.0
        df = pd.DataFrame(rates)
        tr1 = df['high'] - df['low']
        tr2 = abs(df['high'] - df['close'].shift(1))
        tr3 = abs(df['low'] - df['close'].shift(1))
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        return tr.rolling(period).mean().iloc[-1]

    def refine_stops(self, symbol, t, entry, atr):
        info = mt5.symbol_info(symbol)
        if not info: return 0, 0
        p, d = info.point, info.digits
        
        sl_dist = atr * 2.0
        tp_dist = atr * 4.0
        
        # Broker restrictions
        min_dist = max(info.trade_stops_level or 0, info.trade_freeze_level or 0) * p * 1.5
        sl_dist = max(sl_dist, min_dist)
        tp_dist = max(tp_dist, min_dist)
        
        if t == 0: # BUY
            sl, tp = entry - sl_dist, entry + tp_dist
        else: # SELL
            sl, tp = entry + sl_dist, entry - tp_dist
            
        return round(sl, d), round(tp, d)
