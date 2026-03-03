import MetaTrader5 as mt5
import pandas as pd
import json
import os
from datetime import datetime
import config
from engine.indicators import calculate_adx, calculate_macd
from strategies.smc import SMCStrategy
from strategies.vegas import VegasStrategy
from strategies.turtle import TurtleStrategy
from strategies.naked_k import NakedKStrategy

class StrategySelector:
    def __init__(self, symbol):
        self.symbol = symbol
        self.strategies = {
            "SMC": SMCStrategy(symbol, mt5.TIMEFRAME_M15),
            "Vegas": VegasStrategy(symbol, mt5.TIMEFRAME_H1),
            "Turtle": TurtleStrategy(symbol, mt5.TIMEFRAME_H4),
            "NakedK": NakedKStrategy(symbol, mt5.TIMEFRAME_M15)
        }
        self.h4_analyzer = SMCStrategy(symbol, mt5.TIMEFRAME_H4)

    def is_blacklisted(self):
        if not os.path.exists(config.BLACKLIST_PATH): return False
        try:
            with open(config.BLACKLIST_PATH, 'r') as f:
                blacklist = json.load(f)
            now = datetime.now()
            day = now.strftime("%A")
            hour = now.hour
            for item in blacklist:
                if item['day'] == day and item['hour'] == hour:
                    return True
        except: pass
        return False

    def check_filters(self, df):
        if self.is_blacklisted(): return False, "Blacklisted Time Slot"
        
        adx = calculate_adx(df).iloc[-1]
        if adx < config.ADX_THRESHOLD: return False, f"Low ADX ({adx:.1f})"
        
        avg_vol = df['tick_volume'].rolling(20).mean().iloc[-1]
        if df['tick_volume'].iloc[-1] < avg_vol * config.VOL_MULTIPLIER: 
            return False, "Low Volume"
            
        macd, sig, hist = calculate_macd(df['close'])
        momentum = 1 if hist.iloc[-1] > 0 else -1
        return True, momentum

    def get_h4_trend(self):
        self.h4_analyzer.fetch_data(200)
        if self.h4_analyzer.df is None: return 0
        ema = self.h4_analyzer.df['close'].ewm(span=200).mean()
        return 1 if self.h4_analyzer.df['close'].iloc[-1] > ema.iloc[-1] else -1

    def get_best_signal(self):
        h4_trend = self.get_h4_trend()
        rates = mt5.copy_rates_from_pos(self.symbol, mt5.TIMEFRAME_M15, 0, 200)
        if rates is None: return 0, "No Data"
        df = pd.DataFrame(rates)
        
        passed, momentum = self.check_filters(df)
        if not passed: return 0, momentum

        for name, strat in self.strategies.items():
            sig = strat.check_signal()
            if sig != 0 and sig == h4_trend and sig == momentum:
                return sig, f"Predator {name} (H4+Momentum Confirmed)"
        
        return 0, "No Triple-Align Signal"
