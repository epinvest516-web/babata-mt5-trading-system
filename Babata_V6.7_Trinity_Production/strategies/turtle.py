from strategies.base import BaseStrategy
import MetaTrader5 as mt5
import pandas as pd

class TurtleStrategy(BaseStrategy):
    def check_signal(self):
        self.fetch_data(500)
        if self.df is None or len(self.df) < 60: return 0
        
        # Donchian
        high_20 = self.df['high'].iloc[-21:-1].max()
        low_20 = self.df['low'].iloc[-21:-1].min()
        curr = self.df['close'].iloc[-1]
        
        if curr > high_20: return 1
        if curr < low_20: return -1
        return 0
