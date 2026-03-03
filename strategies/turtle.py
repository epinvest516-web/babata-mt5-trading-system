from strategies.base import BaseStrategy
import pandas as pd
import numpy as np
import MetaTrader5 as mt5

class TurtleStrategy(BaseStrategy):
    def check_signal(self):
        # Turtle needs enough history for 20-day high/low
        # Assuming H4 timeframe, 20 days is about 120 bars. 
        # We'll fetch 500 to be safe.
        self.fetch_data(500)
        if self.df is None or len(self.df) < 60: return 0
        
        # Donchian Channel (20-period)
        high_20 = self.df['high'].iloc[-21:-1].max()
        low_20 = self.df['low'].iloc[-21:-1].min()
        curr_close = self.df['close'].iloc[-1]
        
        # Entry Logic
        if curr_close > high_20:
            return 1 # Bullish Breakout
        elif curr_close < low_20:
            return -1 # Bearish Breakout
            
        return 0
