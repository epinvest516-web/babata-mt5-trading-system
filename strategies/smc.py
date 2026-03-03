from strategies.base import BaseStrategy
import pandas as pd

class SMCStrategy(BaseStrategy):
    def check_signal(self):
        self.fetch_data(500) # Only fetches if not in backtest
        if self.df is None or len(self.df) < 200: return 0
        
        # Calculate EMA
        ema = self.df['close'].ewm(span=200).mean()
        curr = self.df['close'].iloc[-1]
        trend = 1 if curr > ema.iloc[-1] else -1
        
        # CHoCH
        lookback = 20
        h = self.df['high'].iloc[-lookback:-1].max()
        l = self.df['low'].iloc[-lookback:-1].min()
        c = self.df['close'].iloc[-1]
        
        if trend == 1 and c > h: return 1
        if trend == -1 and c < l: return -1
        return 0
