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
        tr = pd.concat([df['high'] - df['low'], 
                        abs(df['high'] - df['close'].shift(1)), 
                        abs(df['low'] - df['close'].shift(1))], axis=1).max(axis=1)
        return tr.rolling(period).mean().iloc[-1]

    def refine_stops(self, symbol, t, entry, atr):
        info = mt5.symbol_info(symbol)
        if not info: return 0, 0
        p, d = info.point, info.digits
        sl_dist = atr * 2.0
        # For V6.6, TP is initial target, but we'll trail past it
        tp_dist = atr * 6.0 
        
        min_dist = max(info.trade_stops_level or 0, info.trade_freeze_level or 0) * p * 1.5
        sl_dist = max(sl_dist, min_dist)
        
        if t == 0: sl, tp = entry - sl_dist, entry + tp_dist
        else: sl, tp = entry + sl_dist, entry - tp_dist
        return round(sl, d), round(tp, d)

    def apply_smart_trailing(self, position):
        """ V6.6 Predator: Infinite RR Logic """
        symbol = position.symbol
        magic = position.magic
        entry = position.price_open
        curr_sl = position.sl
        curr_tp = position.tp
        ticket = position.ticket
        
        info = mt5.symbol_info(symbol)
        tick = mt5.symbol_info_tick(symbol)
        if not info or not tick: return

        # Calculate original risk distance
        # Note: This is simplified, real version would store initial SL
        initial_risk = abs(entry - curr_sl) if curr_sl != 0 else 0.005
        current_profit = (tick.bid - entry) if position.type == 0 else (entry - tick.ask)
        
        # 1. Move to Breakeven (BE) at 2R
        if current_profit >= initial_risk * config.BE_RR_LEVEL:
            new_sl = entry + (info.point * 10) if position.type == 0 else entry - (info.point * 10)
            # Only update if moving in favor
            if (position.type == 0 and new_sl > curr_sl) or (position.type == 1 and new_sl < curr_sl):
                req = {
                    "action": mt5.TRADE_ACTION_SLTP, "position": ticket,
                    "sl": round(new_sl, info.digits), "tp": 0.0, # Remove TP for infinite run
                    "comment": "Predator BE"
                }
                mt5.order_send(req)
                return True

        # 2. Candle-by-Candle Trailing (after BE is hit)
        # Check if TP is 0 (signaling we are in infinite trail mode)
        if curr_tp == 0:
            rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M15, 0, 2)
            if rates is not None and len(rates) >= 2:
                last_candle = rates[0] # Previous closed candle
                new_sl = last_candle['low'] if position.type == 0 else last_candle['high']
                if (position.type == 0 and new_sl > curr_sl) or (position.type == 1 and new_sl < curr_sl):
                    req = {
                        "action": mt5.TRADE_ACTION_SLTP, "position": ticket,
                        "sl": round(new_sl, info.digits), "tp": 0.0
                    }
                    mt5.order_send(req)
        return False
