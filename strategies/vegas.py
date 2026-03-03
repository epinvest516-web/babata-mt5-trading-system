from strategies.base import BaseStrategy
import config

class VegasStrategy(BaseStrategy):
    def check_signal(self):
        self.fetch_data(500)
        if self.df is None or len(self.df) < 200: return 0
        
        ema144 = self.df['close'].ewm(span=144).mean()
        ema169 = self.df['close'].ewm(span=169).mean()
        curr = self.df['close'].iloc[-1]
        
        # Bullish: Price above tunnel, pull back to tunnel
        if curr > ema144.iloc[-1] and curr > ema169.iloc[-1]:
            # Simple bounce logic
            if self.df['low'].iloc[-1] <= max(ema144.iloc[-1], ema169.iloc[-1]):
                return 1
        
        # Bearish
        if curr < ema144.iloc[-1] and curr < ema169.iloc[-1]:
            if self.df['high'].iloc[-1] >= min(ema144.iloc[-1], ema169.iloc[-1]):
                return -1
                
        return 0
