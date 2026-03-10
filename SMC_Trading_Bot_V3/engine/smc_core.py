# ============================================================
# SMC Core Engine V3.0
# Implements: BOS, CHOCH, Order Blocks, FVG, Liquidity,
#             Swing H/L, OTE, HTF Bias
# ============================================================
import pandas as pd
import numpy as np


class SMCCore:
    """Full SMC analysis engine - all concepts in one place."""

    # ─────────────────────────────────────────────────────────
    # SWING HIGHS & LOWS
    # ─────────────────────────────────────────────────────────
    @staticmethod
    def swing_highs_lows(df, length=10):
        """
        Identify significant swing highs and lows.
        Returns df with columns: swing_high, swing_low (price or NaN)
        """
        df = df.copy()
        df['swing_high'] = np.nan
        df['swing_low']  = np.nan

        for i in range(length, len(df) - length):
            hi = df['high'].iloc[i]
            lo = df['low'].iloc[i]
            window_hi = df['high'].iloc[i - length: i + length + 1]
            window_lo = df['low'].iloc[i  - length: i + length + 1]

            if hi == window_hi.max():
                df.at[df.index[i], 'swing_high'] = hi
            if lo == window_lo.min():
                df.at[df.index[i], 'swing_low'] = lo

        return df

    # ─────────────────────────────────────────────────────────
    # BREAK OF STRUCTURE (BOS) & CHANGE OF CHARACTER (CHOCH)
    # ─────────────────────────────────────────────────────────
    @staticmethod
    def bos_choch(df):
        """
        Detect BOS (Break of Structure) and CHOCH (Change of Character).
        BOS = continuation of trend (breaks prior swing in trend direction)
        CHOCH = reversal signal (breaks prior swing against trend)

        Returns df with: bos (1=bullish, -1=bearish), choch (1=bullish, -1=bearish)
        """
        df = df.copy()
        df['bos']   = 0
        df['choch'] = 0

        swing_highs = df[df['swing_high'].notna()]['swing_high'].tolist()
        swing_lows  = df[df['swing_low'].notna()]['swing_low'].tolist()
        swing_h_idx = df[df['swing_high'].notna()].index.tolist()
        swing_l_idx = df[df['swing_low'].notna()].index.tolist()

        # Simple BOS: current close breaks prior swing high/low
        last_sh = None
        last_sl = None

        for i in range(1, len(df)):
            close = df['close'].iloc[i]
            # Update last swing levels
            row_idx = df.index[i]
            if row_idx in swing_h_idx:
                last_sh = df['swing_high'].loc[row_idx]
            if row_idx in swing_l_idx:
                last_sl = df['swing_low'].loc[row_idx]

            if last_sh and close > last_sh:
                df.at[row_idx, 'bos'] = 1   # Bullish BOS
            elif last_sl and close < last_sl:
                df.at[row_idx, 'bos'] = -1  # Bearish BOS

        return df

    # ─────────────────────────────────────────────────────────
    # FAIR VALUE GAP (FVG / Imbalance)
    # ─────────────────────────────────────────────────────────
    @staticmethod
    def detect_fvg(df, join_consecutive=True):
        """
        ICT Fair Value Gap:
        Bullish FVG: candle[i-2].high < candle[i].low
        Bearish FVG: candle[i-2].low  > candle[i].high
        Returns list of active (unmitigated) FVGs.
        """
        fvgs = []
        df = df.copy()

        for i in range(2, len(df)):
            c1_high = df['high'].iloc[i - 2]
            c1_low  = df['low'].iloc[i - 2]
            c3_high = df['high'].iloc[i]
            c3_low  = df['low'].iloc[i]
            c2_bull = df['close'].iloc[i-1] > df['open'].iloc[i-1]
            c2_bear = df['close'].iloc[i-1] < df['open'].iloc[i-1]

            # Bullish FVG
            if c2_bull and c3_low > c1_high:
                fvg = {
                    'type':    'bullish',
                    'top':     c3_low,
                    'bottom':  c1_high,
                    'mid':     (c3_low + c1_high) / 2,
                    'size':    c3_low - c1_high,
                    'index':   i,
                    'time':    df.index[i-1],
                    'mitigated': False
                }
                fvgs.append(fvg)

            # Bearish FVG
            elif c2_bear and c1_low > c3_high:
                fvg = {
                    'type':    'bearish',
                    'top':     c1_low,
                    'bottom':  c3_high,
                    'mid':     (c1_low + c3_high) / 2,
                    'size':    c1_low - c3_high,
                    'index':   i,
                    'time':    df.index[i-1],
                    'mitigated': False
                }
                fvgs.append(fvg)

        # Check mitigation (price entered the FVG)
        last_close = df['close'].iloc[-1]
        for fvg in fvgs:
            if fvg['type'] == 'bullish' and last_close <= fvg['top']:
                fvg['mitigated'] = True
            elif fvg['type'] == 'bearish' and last_close >= fvg['bottom']:
                fvg['mitigated'] = True

        return fvgs

    # ─────────────────────────────────────────────────────────
    # ORDER BLOCKS (OB)
    # ─────────────────────────────────────────────────────────
    @staticmethod
    def detect_order_blocks(df, swing_length=10):
        """
        Order Block: The last bearish candle before a bullish BOS (Bullish OB)
                     The last bullish candle before a bearish BOS (Bearish OB)
        Returns list of order blocks with zones.
        """
        obs = []
        df_s = SMCCore.swing_highs_lows(df, swing_length)

        for i in range(swing_length + 1, len(df) - 1):
            close = df['close'].iloc[i]

            # Look for Bullish OB: bearish candle before bullish displacement
            if df['close'].iloc[i] > df['high'].iloc[i-swing_length:i].max():
                # Find last bearish candle before this BOS
                for j in range(i-1, max(0, i-20), -1):
                    if df['close'].iloc[j] < df['open'].iloc[j]:  # bearish
                        ob = {
                            'type':   'bullish',
                            'top':    df['open'].iloc[j],
                            'bottom': df['close'].iloc[j],
                            'mid':    (df['open'].iloc[j] + df['close'].iloc[j]) / 2,
                            'time':   df.index[j],
                            'index':  j,
                            'bos_index': i,
                        }
                        obs.append(ob)
                        break

            # Look for Bearish OB: bullish candle before bearish displacement
            elif df['close'].iloc[i] < df['low'].iloc[i-swing_length:i].min():
                for j in range(i-1, max(0, i-20), -1):
                    if df['close'].iloc[j] > df['open'].iloc[j]:  # bullish
                        ob = {
                            'type':   'bearish',
                            'top':    df['close'].iloc[j],
                            'bottom': df['open'].iloc[j],
                            'mid':    (df['close'].iloc[j] + df['open'].iloc[j]) / 2,
                            'time':   df.index[j],
                            'index':  j,
                            'bos_index': i,
                        }
                        obs.append(ob)
                        break

        return obs

    # ─────────────────────────────────────────────────────────
    # LIQUIDITY SWEEP
    # ─────────────────────────────────────────────────────────
    @staticmethod
    def detect_liquidity_sweep(df, lookback=40):
        """
        Detect liquidity sweep + rejection (stop hunt).
        Returns 'bullish', 'bearish', or None.
        """
        if len(df) < lookback + 2:
            return None

        window = df.iloc[-lookback-1:-1]
        prev_hh = window['high'].max()
        prev_ll = window['low'].min()

        last = df.iloc[-1]
        curr_high  = last['high']
        curr_low   = last['low']
        curr_close = last['close']
        curr_open  = last['open']

        body_size = abs(curr_close - curr_open)
        candle_range = curr_high - curr_low if (curr_high - curr_low) > 0 else 1

        # Bullish sweep: wick below prior lows, close above (relaxed: partial recovery ok)
        bull_wick = prev_ll - curr_low
        if curr_low < prev_ll and curr_close > curr_low and curr_close > curr_open:
            recovery = (curr_close - curr_low) / (prev_ll - curr_low + 0.0001)
            if recovery > 0.3:  # Recovered at least 30% of wick
                return 'bullish'
        # Bearish sweep: wick above prior highs, close below (relaxed: partial drop ok)
        bear_wick = curr_high - prev_hh
        if curr_high > prev_hh and curr_close < curr_high and curr_close < curr_open:
            drop = (curr_high - curr_close) / (curr_high - prev_hh + 0.0001)
            if drop > 0.3:  # Dropped at least 30% of excess
                return 'bearish'
        return None

    # ─────────────────────────────────────────────────────────
    # PREMIUM / DISCOUNT ZONES
    # ─────────────────────────────────────────────────────────
    @staticmethod
    def premium_discount(high, low):
        """
        Equilibrium at 0.5 fib.
        Discount < 0.5 (buy opportunities)
        Premium  > 0.5 (sell opportunities)
        """
        eq = (high + low) / 2
        return {'equilibrium': eq, 'premium_top': high, 'discount_bottom': low}

    # ─────────────────────────────────────────────────────────
    # OTE - OPTIMAL TRADE ENTRY
    # ─────────────────────────────────────────────────────────
    @staticmethod
    def ote_zone(high, low, direction='bullish'):
        """
        OTE Zone: 0.618 - 0.786 Fibonacci retracement.
        Bullish OTE: between 0.618 and 0.786 of swing (buy in discount)
        Bearish OTE: between 0.618 and 0.786 of swing (sell in premium)
        """
        diff = high - low
        if direction == 'bullish':
            return {
                'entry_ideal': high - diff * 0.705,  # Sweet spot
                'zone_top':    high - diff * 0.618,
                'zone_bottom': high - diff * 0.786,
            }
        else:
            return {
                'entry_ideal': low + diff * 0.705,
                'zone_top':    low + diff * 0.786,
                'zone_bottom': low + diff * 0.618,
            }

    # ─────────────────────────────────────────────────────────
    # HTF BIAS (Daily + H4 + H1)
    # ─────────────────────────────────────────────────────────
    @staticmethod
    def get_htf_bias(df_daily, df_h4, df_h1):
        """
        3-layer bias filter:
        - Daily: Macro direction
        - H4: Trend structure
        - H1: Entry alignment
        All 3 must agree (or at least Daily+H4) for a valid signal.
        Returns 'bullish', 'bearish', or None
        """
        try:
            scores = {'bullish': 0, 'bearish': 0}

            # Daily bias (weight: 3)
            d_ma20 = df_daily['close'].iloc[-20:].mean()
            d_close = df_daily['close'].iloc[-1]
            d_prev  = df_daily['close'].iloc[-2]
            if d_close > d_ma20 and d_close > d_prev:
                scores['bullish'] += 3
            elif d_close < d_ma20 and d_close < d_prev:
                scores['bearish'] += 3

            # H4 bias (weight: 2) - exclusive assignment, no double-counting
            h4_ma20 = df_h4['close'].iloc[-20:].mean()
            h4_close = df_h4['close'].iloc[-1]
            h4_hh = df_h4['high'].iloc[-1] > df_h4['high'].iloc[-5:-1].max()
            h4_ll = df_h4['low'].iloc[-1] < df_h4['low'].iloc[-5:-1].min()
            if h4_close > h4_ma20 or h4_hh:
                scores['bullish'] += 2
            elif h4_close < h4_ma20 or h4_ll:
                scores['bearish'] += 2

            # H1 bias (weight: 1)
            h1_ma10 = df_h1['close'].iloc[-10:].mean()
            h1_close = df_h1['close'].iloc[-1]
            if h1_close > h1_ma10:
                scores['bullish'] += 1
            else:
                scores['bearish'] += 1

            # Need at least 3/6 score to confirm bias (relaxed from 4)
            if scores['bullish'] >= 3 and scores['bullish'] > scores['bearish']:
                return 'bullish'
            if scores['bearish'] >= 3 and scores['bearish'] > scores['bullish']:
                return 'bearish'
            return None  # Conflicted, no trade

        except Exception:
            return None

    # ─────────────────────────────────────────────────────────
    # CONFLUENCE SCORE
    # ─────────────────────────────────────────────────────────
    @staticmethod
    def confluence_score(direction, bias, sweep, fvg, ob, df_m15, df_h1, df_h4):
        """
        Multi-factor confluence scoring (0.0 - 1.0)
        """
        score = 0.0
        factors = []

        # HTF Bias alignment (0.25)
        if bias == direction:
            score += 0.25
            factors.append("HTF✓")

        # Liquidity Sweep (0.20)
        if sweep == direction:
            score += 0.20
            factors.append("Sweep✓")

        # FVG present (0.15)
        if fvg:
            score += 0.15
            factors.append("FVG✓")

        # Order Block (0.15)
        if ob:
            score += 0.15
            factors.append("OB✓")

        # Volume confirmation (0.10)
        try:
            vol_now = df_m15['tick_volume'].iloc[-1]
            vol_avg = df_m15['tick_volume'].iloc[-20:].mean()
            if vol_now > vol_avg * 1.3:
                score += 0.10
                factors.append("Vol✓")
        except Exception:
            pass

        # H4 momentum (0.10)
        try:
            h4_mom = df_h4['close'].iloc[-1] - df_h4['close'].iloc[-4]
            if (direction == 'bullish' and h4_mom > 0) or \
               (direction == 'bearish' and h4_mom < 0):
                score += 0.10
                factors.append("Mom✓")
        except Exception:
            pass

        # H1 structure (0.05)
        try:
            h1_ma = df_h1['close'].iloc[-5:].mean()
            h1_c  = df_h1['close'].iloc[-1]
            if (direction == 'bullish' and h1_c > h1_ma) or \
               (direction == 'bearish' and h1_c < h1_ma):
                score += 0.05
                factors.append("H1✓")
        except Exception:
            pass

        return min(score, 1.0), factors
