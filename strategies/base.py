import pandas as pd
import MetaTrader5 as mt5

class BaseStrategy:
    def __init__(self, symbol, timeframe):
        self.symbol = symbol
        self.timeframe = timeframe
        self.df = None

    def fetch_data(self, bars=500):
        # Only fetch if df is None (Live mode)
        # In backtest mode, df is pre-set by the backtester
        if self.df is None:
            rates = mt5.copy_rates_from_pos(self.symbol, self.timeframe, 0, bars)
            if rates is not None and len(rates) > 0:
                self.df = pd.DataFrame(rates)
        
    def check_signal(self):
        return 0
