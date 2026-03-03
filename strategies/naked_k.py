from strategies.base import BaseStrategy
import pandas as pd

class NakedKStrategy(BaseStrategy):
    def check_signal(self):
        self.fetch_data(50)
        if self.df is None or len(self.df) < 5: return 0
        
        last = self.df.iloc[-2]
        prev = self.df.iloc[-3]
        
        # 1. Engulfing (吞没)
        is_bull_engulf = last['close'] > prev['high'] and last['open'] < prev['low']
        is_bear_engulf = last['close'] < prev['low'] and last['open'] > prev['high']
        
        # 2. Pinbar (拒绝)
        body = abs(last['close'] - last['open'])
        range_k = last['high'] - last['low']
        if range_k == 0: return 0
        
        upper_wick = last['high'] - max(last['close'], last['open'])
        lower_wick = min(last['close'], last['open']) - last['low']
        
        is_bull_pin = lower_wick > (body * 2) and upper_wick < (range_k * 0.2)
        is_bear_pin = upper_wick > (body * 2) and lower_wick < (range_k * 0.2)
        
        if is_bull_engulf or is_bull_pin: return 1
        if is_bear_engulf or is_bear_pin: return -1
        return 0
