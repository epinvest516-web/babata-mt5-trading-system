import pandas as pd
import MetaTrader5 as mt5

class BaseStrategy:
    def __init__(self, symbol, timeframe):
        self.symbol = symbol
        self.timeframe = timeframe
        self.df = None

    def fetch_data(self, bars=500):
        rates = mt5.copy_rates_from_pos(self.symbol, self.timeframe, 0, bars)
        if rates is None or len(rates) == 0:
            self.df = None
            return
        self.df = pd.DataFrame(rates)
        
    def check_signal(self):
        """ Returns (1 for Buy, -1 for Sell, 0 for None) """
        return 0
