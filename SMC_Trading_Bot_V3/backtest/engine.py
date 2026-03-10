# ============================================================
# SMC Phantom V3.0 - Backtest Engine
# Supports: 1-month / 1-quarter simulation
# ============================================================
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, timezone
from engine.smc_core import SMCCore
from config import *

smc = SMCCore()


def get_historical(symbol, timeframe, start_dt, end_dt, count=5000):
    rates = mt5.copy_rates_range(symbol, timeframe,
                                  start_dt.replace(tzinfo=None),
                                  end_dt.replace(tzinfo=None))
    if rates is None or len(rates) == 0:
        return None
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    df = df.set_index('time')
    df.columns = [c.lower() for c in df.columns]
    return df


def simulate_lot(balance, entry, sl, risk_pct=2.0):
    """Simple lot sim for backtest (no MT5 contract specs needed)."""
    risk_amt = balance * (risk_pct / 100)
    sl_dist  = abs(entry - sl)
    if sl_dist == 0:
        return 0.01
    # Approximate: $1/pip for 0.01 lot on Gold
    pip_value = 1.0
    lots = risk_amt / (sl_dist * 100 * pip_value)
    return max(0.01, round(lots, 2))


def run_backtest(symbol, period_days=30, risk_pct=2.0, min_rr=MIN_RR):
    if not mt5.initialize():
        print("MT5 init failed")
        return None

    end_dt   = datetime.now(timezone.utc)
    start_dt = end_dt - timedelta(days=period_days)

    print(f"\n{'='*60}")
    print(f"SMC Phantom V3.0 — Backtest")
    print(f"Symbol: {symbol} | Period: {period_days} days")
    print(f"From: {start_dt.date()} To: {end_dt.date()}")
    print(f"{'='*60}")

    # Load data
    df_d   = get_historical(symbol, mt5.TIMEFRAME_D1,  start_dt - timedelta(days=100), end_dt)
    df_h4  = get_historical(symbol, mt5.TIMEFRAME_H4,  start_dt - timedelta(days=50), end_dt)
    df_h1  = get_historical(symbol, mt5.TIMEFRAME_H1,  start_dt - timedelta(days=30), end_dt)
    df_m15 = get_historical(symbol, mt5.TIMEFRAME_M15, start_dt, end_dt)

    if any(d is None for d in [df_d, df_h4, df_h1, df_m15]):
        print("Failed to load data")
        return None

    # Filter test period
    df_test = df_m15[df_m15.index >= pd.Timestamp(start_dt.replace(tzinfo=None))]

    trades   = []
    balance  = INITIAL_BALANCE
    equity   = balance
    peak_eq  = balance
    max_dd   = 0.0
    signals  = 0

    # Sliding window backtest
    window = 200
    for i in range(window, len(df_test) - 1):
        bar_time = df_test.index[i]
        hour     = bar_time.hour

        # Killzone filter
        in_kz = any(s <= hour < e for s, e in KILLZONES.values())
        if not in_kz:
            continue

        # Build local windows
        m15_slice = df_test.iloc[max(0, i-window):i+1]
        h1_idx    = df_h1.index.searchsorted(bar_time)
        h4_idx    = df_h4.index.searchsorted(bar_time)
        d_idx     = df_d.index.searchsorted(bar_time)

        if h1_idx < 50 or h4_idx < 30 or d_idx < 20:
            continue

        h1_sl  = df_h1.iloc[max(0, h1_idx-100):h1_idx]
        h4_sl  = df_h4.iloc[max(0, h4_idx-60):h4_idx]
        d_sl   = df_d.iloc[max(0, d_idx-50):d_idx]

        if len(h1_sl) < 10 or len(h4_sl) < 10 or len(d_sl) < 10:
            continue

        # Bias
        bias = smc.get_htf_bias(d_sl, h4_sl, h1_sl)
        if not bias:
            continue

        # Sweep — check last 10 H1 bars, fallback to M15 sweep
        sweep = None
        for _lookback_offset in range(1, 11):
            _h1_check = h1_sl.iloc[:-_lookback_offset+1] if _lookback_offset > 1 else h1_sl
            _s = smc.detect_liquidity_sweep(_h1_check, lookback=SWEEP_LOOKBACK)
            if _s == bias:
                sweep = _s
                break
        if not sweep:
            # Fallback: M15 sweep
            _m15_s = smc.detect_liquidity_sweep(m15_slice, lookback=SWEEP_LOOKBACK)
            if _m15_s == bias:
                sweep = _m15_s
        if not sweep:
            continue

        # FVG + OB
        fvgs = smc.detect_fvg(m15_slice)
        active_fvgs = [f for f in fvgs
                       if f['type'] == bias and not f['mitigated']
                       and f['index'] >= len(m15_slice) - 10]
        best_fvg = active_fvgs[-1] if active_fvgs else None

        obs = smc.detect_order_blocks(m15_slice)
        recent_obs = [o for o in obs if o['type'] == bias and o['index'] >= len(m15_slice)-20]
        best_ob = recent_obs[-1] if recent_obs else None

        # OTE
        h20 = m15_slice['high'].iloc[-20:].max()
        l20 = m15_slice['low'].iloc[-20:].min()
        ote = smc.ote_zone(h20, l20, bias)

        entry = best_fvg['mid'] if best_fvg else (best_ob['mid'] if best_ob else ote['entry_ideal'])

        swing_range = h20 - l20
        sl_buf  = swing_range * SL_BUFFER_PCT
        sl  = (l20 - sl_buf)  if bias == 'bullish' else (h20 + sl_buf)
        tp  = (entry + abs(entry-sl)*min_rr) if bias == 'bullish' else (entry - abs(entry-sl)*min_rr)

        # Confidence
        confidence, factors = smc.confluence_score(
            bias, bias, bias, best_fvg, best_ob, m15_slice, h1_sl, h4_sl
        )
        if confidence < MIN_CONFIDENCE:
            continue

        signals += 1
        lots = simulate_lot(balance, entry, sl, risk_pct)

        # Simulate outcome (next N candles)
        result = 'OPEN'
        pnl    = 0.0
        for j in range(i+1, min(i+300, len(df_test)-1)):
            fut_high = df_test['high'].iloc[j]
            fut_low  = df_test['low'].iloc[j]
            if bias == 'bullish':
                if fut_low <= sl:
                    pnl = -(abs(entry - sl) * lots * 100)
                    result = 'LOSS'
                    break
                if fut_high >= tp:
                    pnl = abs(tp - entry) * lots * 100
                    result = 'WIN'
                    break
            else:
                if fut_high >= sl:
                    pnl = -(abs(entry - sl) * lots * 100)
                    result = 'LOSS'
                    break
                if fut_low <= tp:
                    pnl = abs(entry - tp) * lots * 100
                    result = 'WIN'
                    break

        if result == 'OPEN':
            continue  # Skip incomplete trades

        balance += pnl
        equity   = balance
        peak_eq  = max(peak_eq, equity)
        dd       = (peak_eq - equity) / peak_eq * 100
        max_dd   = max(max_dd, dd)

        trades.append({
            'time':       bar_time,
            'direction':  bias,
            'entry':      round(entry, 5),
            'sl':         round(sl, 5),
            'tp':         round(tp, 5),
            'lots':       lots,
            'result':     result,
            'pnl':        round(pnl, 2),
            'balance':    round(balance, 2),
            'confidence': round(confidence, 3),
            'factors':    '|'.join(factors)
        })

    mt5.shutdown()

    # ── Report ──
    if not trades:
        print("No completed trades in test period.")
        return None

    df_trades = pd.DataFrame(trades)
    wins      = df_trades[df_trades['result'] == 'WIN']
    losses    = df_trades[df_trades['result'] == 'LOSS']
    total_pnl = df_trades['pnl'].sum()
    win_rate  = len(wins) / len(df_trades) * 100
    avg_win   = wins['pnl'].mean() if len(wins) > 0 else 0
    avg_loss  = losses['pnl'].mean() if len(losses) > 0 else 0
    profit_factor = abs(wins['pnl'].sum() / losses['pnl'].sum()) if losses['pnl'].sum() != 0 else 999
    monthly_return = (balance - INITIAL_BALANCE) / INITIAL_BALANCE / period_days * 30 * 100

    print(f"\n{'='*60}")
    print(f"BACKTEST RESULTS — {symbol} ({period_days}d)")
    print(f"{'='*60}")
    print(f"Period:         {start_dt.date()} → {end_dt.date()}")
    print(f"Initial Balance: ${INITIAL_BALANCE:,.2f}")
    print(f"Final Balance:   ${balance:,.2f}")
    print(f"Total P&L:       ${total_pnl:+,.2f}")
    print(f"Monthly Return:  {monthly_return:+.2f}%")
    print(f"─────────────────────────────────────────")
    print(f"Total Signals:   {signals}")
    print(f"Total Trades:    {len(df_trades)}")
    print(f"Wins:            {len(wins)}  ({win_rate:.1f}%)")
    print(f"Losses:          {len(losses)}")
    print(f"Avg Win:         ${avg_win:+.2f}")
    print(f"Avg Loss:        ${avg_loss:+.2f}")
    print(f"Profit Factor:   {profit_factor:.2f}")
    print(f"Max Drawdown:    {max_dd:.2f}%")
    print(f"{'='*60}")

    # Save CSV
    out = os.path.join(os.path.dirname(__file__), f"backtest_{symbol}_{period_days}d.csv")
    df_trades.to_csv(out, index=False)
    print(f"Saved: {out}")

    return {
        'symbol': symbol, 'period': period_days,
        'initial': INITIAL_BALANCE, 'final': balance,
        'pnl': total_pnl, 'monthly_return': monthly_return,
        'trades': len(df_trades), 'win_rate': win_rate,
        'profit_factor': profit_factor, 'max_dd': max_dd,
        'trades_df': df_trades
    }


if __name__ == "__main__":
    # Run 30-day and 90-day backtests
    for sym in ["XAUUSD.s", "XAGUSD.s"]:
        for days in [30, 90]:
            run_backtest(sym, period_days=days)
