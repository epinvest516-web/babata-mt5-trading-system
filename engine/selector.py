import MetaTrader5 as mt5
import pandas as pd
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
        self.scores = {name: 1.0 for name in self.strategies} # Initial bias

    def update_performance(self, results_df):
        """ Update strategy scores based on recent 3-month performance (Stub) """
        # In a real implementation, this would run a backtest and adjust scores
        pass

    def get_best_signal(self):
        """ Analyzes all strategies and returns the one with consensus or highest score """
        signals = {}
        for name, strat in self.strategies.items():
            signals[name] = strat.check_signal()
            
        # For V6.0: If multiple strategies agree, it's a high-prob signal
        buy_votes = [n for n, s in signals.items() if s == 1]
        sell_votes = [n for n, s in signals.items() if s == -1]
        
        if len(buy_votes) >= 2: return 1, f"Consensus Buy ({', '.join(buy_votes)})"
        if len(sell_votes) >= 2: return -1, f"Consensus Sell ({', '.join(sell_votes)})"
        
        # Or pick the single strongest (currently just picking first non-zero for simplicity)
        for name, sig in signals.items():
            if sig != 0: return sig, f"Solo {name}"
            
        return 0, "No Signal"
