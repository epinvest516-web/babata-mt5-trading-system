# ============================================================
# SMC Phantom V3.1 - Backtest Engine (Fixed)
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


def get_hist(symbol, tf, days_back, count=5000):
    """Fetch historical OHLCV data."""
    end   = datetime.now()
    start = end - timedelta(days=days_back)
    rates = mt5.copy_rates_range(symbol, tf, start, end)
    if rates is None or len(rates) == 0:
        return None
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    df = df.set_index('time')
    df.columns = [c.lower() for c in df.columns]
    return df


def find_symbol(base):
    """Find the correct symbol name (try multiple suffixes)."""
    variants = [base, base + '.s', base.replace('.s', ''), base + 'm']
    all_syms = [s.name for s in mt5.symbols_get()]
    for v in variants:
        if v in all_syms:
            return v
    # Partial match
    for s in all_syms:
        if base.replace('.s', '') in s:
            return s
    return None


def simulate_lot(balance, entry, sl, risk_pct=2.0):
    risk_amt = balance * (risk_pct / 100)
    sl_dist  = abs(entry - sl)
    if sl_dist == 0:
        return 0.01
    lots = risk_amt / (sl_dist * 100)
    return max(0.01, round(lots, 2))


def run_backtest(symbol_raw, period_days=30, risk_pct=2.0):
    print(f"\n{'='*60}")
    print(f"SMC Phantom V3.1 — Backtest")
    print(f"Symbol: {symbol_raw} | Period: {period_days} days")
    print(f"{'='*60}")

    # ── Find correct symbol name ──
    symbol = find_symbol(symbol_raw)
    if not symbol:
        print(f"❌ Symbol not found: {symbol_raw}")
        print(f"   Available metals: {[s for s in [s.name for s in mt5.symbols_get()] if 'XAU' in s or 'XAG' in s]}")
        return None
    print(f"✅ Symbol resolved: {symbol}")

    # ── Load data ──
    df_d   = get_hist(symbol, mt5.TIMEFRAME_D1,  period_days + 120)
    df_h4  = get_hist(symbol, mt5.TIMEFRAME_H4,  period_days + 60)
    df_h1  = get_hist(symbol, mt5.TIMEFRAME_H1,  period_days + 30)
    df_m15 = get_hist(symbol, mt5.TIMEFRAME_M15, period_days + 10)

    loaded = {
        'D1':  len(df_d)  if df_d  is not None else 0,
        'H4':  len(df_h4) if df_h4 is not None else 0,
        'H1':  len(df_h1) if df_h1 is not None else 0,
        'M15': len(df_m15)if df_m15 is not None else 0,
    }
    print(f"📊 Data loaded: {loaded}")

    if any(v == 0 for v in loaded.values()):
        print("❌ Failed to load one or more timeframes.")
        return None

    # ── Trim to test period ──
    cutoff  = pd.Timestamp(datetime.now() - timedelta(days=period_days))
    df_test = df_m15[df_m15.index >= cutoff].copy()
    print(f"📅 Test bars: {len(df_test)} M15 candles")

    if len(df_test) < 50:
        print("❌ Not enough test bars.")
        return None

    # ── Backtest loop ──
    trades       = []
    balance      = INITIAL_BALANCE
    peak_eq      = balance
    max_dd       = 0.0
    signals      = 0
    skipped_bias = 0
    skipped_sweep= 0
    skipped_conf = 0
    window       = 100  # lookback window for each step

    for i in range(window, len(df_test) - 5):
        bar_time = df_test.index[i]
        hour     = bar_time.hour

        # Killzone check
        in_kz = any(s <= hour < e for s, e in KILLZONES.values())
        if not in_kz:
            continue

        # Build local slices
        m15_slice = df_test.iloc[max(0, i - window): i + 1].copy()

        # Find matching indices in H1/H4/D1
        h1_mask  = df_h1.index <= bar_time
        h4_mask  = df_h4.index <= bar_time
        d_mask   = df_d.index  <= bar_time

        h1_sl = df_h1[h1_mask].iloc[-80:]
        h4_sl = df_h4[h4_mask].iloc[-60:]
        d_sl  = df_d[d_mask].iloc[-50:]

        if len(h1_sl) < 10 or len(h4_sl) < 10 or len(d_sl) < 5:
            continue

        # ── Layer 1: HTF Bias ──
        bias = smc.get_htf_bias(d_sl, h4_sl, h1_sl)
        if bias is None:
            skipped_bias += 1
            continue

        # ── Layer 2: Liquidity Sweep (H1) ──
        sweep = smc.detect_liquidity_sweep(h1_sl, lookback=30)
        if not sweep or sweep != bias:
            skipped_sweep += 1
            continue

        direction = sweep

        # ── Layer 3: FVG on M15 ──
        fvgs = smc.detect_fvg(m15_slice)
        active_fvgs = [f for f in fvgs
                       if f['type'] == direction
                       and not f['mitigated']
                       and f['index'] >= len(m15_slice) - 8]
        best_fvg = active_fvgs[-1] if active_fvgs else None

        # ── Layer 4: OB on M15 ──
        obs = smc.detect_order_blocks(m15_slice, swing_length=8)
        recent_obs = [o for o in obs
                      if o['type'] == direction
                      and o['index'] >= len(m15_slice) - 15]
        best_ob = recent_obs[-1] if recent_obs else None

        # Need at least FVG or OB
        if not best_fvg and not best_ob:
            continue

        # ── Entry / SL / TP ──
        h20 = m15_slice['high'].iloc[-20:].max()
        l20 = m15_slice['low'].iloc[-20:].min()
        ote = smc.ote_zone(h20, l20, direction)

        if best_fvg:
            entry = best_fvg['mid']
        elif best_ob:
            entry = best_ob['mid']
        else:
            entry = ote['entry_ideal']

        swing_range = h20 - l20
        sl_buf = swing_range * SL_BUFFER_PCT
        sl = (l20 - sl_buf) if direction == 'bullish' else (h20 + sl_buf)
        tp = (entry + abs(entry - sl) * MIN_RR) if direction == 'bullish' \
             else (entry - abs(entry - sl) * MIN_RR)

        # Validate
        if abs(entry - sl) == 0:
            continue

        rr_actual = abs(tp - entry) / abs(entry - sl)
        if rr_actual < 1.5:
            continue

        # ── Confidence ──
        confidence, factors = smc.confluence_score(
            direction, bias, direction, best_fvg, best_ob, m15_slice, h1_sl, h4_sl
        )
        if confidence < MIN_CONFIDENCE:
            skipped_conf += 1
            continue

        signals += 1
        lots = simulate_lot(balance, entry, sl, risk_pct)

        # ── Simulate outcome (limit order: wait for fill first) ──
        result    = 'TIMEOUT'
        pnl       = 0.0
        filled    = False
        future    = df_test.iloc[i + 1: min(i + 300, len(df_test))]

        for _, bar in future.iterrows():
            # Step 1: Check if limit order fills
            if not filled:
                if direction == 'bullish' and bar['low'] <= entry <= bar['high']:
                    filled = True
                elif direction == 'bearish' and bar['low'] <= entry <= bar['high']:
                    filled = True
                # Also fill if price gaps through entry
                elif direction == 'bullish' and bar['high'] < entry:
                    filled = True  # price came down past entry
                elif direction == 'bearish' and bar['low'] > entry:
                    filled = True  # price went up past entry
                if not filled:
                    continue

            # Step 2: Check SL/TP after fill
            if direction == 'bullish':
                if bar['low'] <= sl:
                    pnl    = -(abs(entry - sl) * lots * 100)
                    result = 'LOSS'
                    break
                if bar['high'] >= tp:
                    pnl    = abs(tp - entry) * lots * 100
                    result = 'WIN'
                    break
            else:
                if bar['high'] >= sl:
                    pnl    = -(abs(entry - sl) * lots * 100)
                    result = 'LOSS'
                    break
                if bar['low'] <= tp:
                    pnl    = abs(entry - tp) * lots * 100
                    result = 'WIN'
                    break

        if result == 'TIMEOUT':
            continue

        balance += pnl
        peak_eq  = max(peak_eq, balance)
        dd       = (peak_eq - balance) / peak_eq * 100
        max_dd   = max(max_dd, dd)

        trades.append({
            'time':       str(bar_time),
            'direction':  direction,
            'entry':      round(entry, 5),
            'sl':         round(sl, 5),
            'tp':         round(tp, 5),
            'lots':       lots,
            'result':     result,
            'pnl':        round(pnl, 2),
            'balance':    round(balance, 2),
            'confidence': round(confidence, 3),
            'factors':    '|'.join(factors),
        })

    # ── Print Debug Stats ──
    print(f"\n📊 Signal Analysis:")
    print(f"   Total M15 bars scanned:  {len(df_test)}")
    print(f"   Bars in killzone:        ~{len(df_test)//3}")
    print(f"   Skipped (no bias):       {skipped_bias}")
    print(f"   Skipped (no sweep):      {skipped_sweep}")
    print(f"   Skipped (low conf):      {skipped_conf}")
    print(f"   Signals generated:       {signals}")
    print(f"   Completed trades:        {len(trades)}")

    if not trades:
        print("\n⚠️  No trades completed. Conditions may be too strict.")
        print("   Consider relaxing MIN_CONFIDENCE or SWEEP_LOOKBACK.")
        return None

    # ── Report ──
    df_t    = pd.DataFrame(trades)
    wins    = df_t[df_t['result'] == 'WIN']
    losses  = df_t[df_t['result'] == 'LOSS']
    total_pnl  = df_t['pnl'].sum()
    win_rate   = len(wins) / len(df_t) * 100
    avg_win    = wins['pnl'].mean()    if len(wins) > 0    else 0
    avg_loss   = losses['pnl'].mean()  if len(losses) > 0  else 0
    pf = abs(wins['pnl'].sum() / losses['pnl'].sum()) if losses['pnl'].sum() != 0 else 999
    monthly    = (balance - INITIAL_BALANCE) / INITIAL_BALANCE / period_days * 30 * 100

    print(f"\n{'='*60}")
    print(f"RESULTS — {symbol} ({period_days}d)")
    print(f"{'='*60}")
    print(f"Initial Balance:  ${INITIAL_BALANCE:,.2f}")
    print(f"Final Balance:    ${balance:,.2f}")
    print(f"Total P&L:        ${total_pnl:+,.2f}")
    print(f"Monthly Return:   {monthly:+.1f}%")
    print(f"─────────────────────────────")
    print(f"Total Trades:     {len(df_t)}")
    print(f"Wins:             {len(wins)}  ({win_rate:.1f}%)")
    print(f"Losses:           {len(losses)}")
    print(f"Avg Win:          ${avg_win:+.2f}")
    print(f"Avg Loss:         ${avg_loss:+.2f}")
    print(f"Profit Factor:    {pf:.2f}")
    print(f"Max Drawdown:     {max_dd:.2f}%")
    print(f"{'='*60}")

    # Save CSV
    out = os.path.join(os.path.dirname(__file__), f"result_{symbol}_{period_days}d.csv")
    df_t.to_csv(out, index=False)
    print(f"Saved: {out}")
    return {'symbol': symbol, 'period': period_days, 'pnl': total_pnl,
            'win_rate': win_rate, 'max_dd': max_dd, 'monthly': monthly,
            'trades': len(df_t), 'pf': pf}


if __name__ == "__main__":
    if not mt5.initialize():
        print("MT5 init failed!")
        sys.exit(1)

    print("MT5 Connected ✅")
    print(f"Account: {mt5.account_info().login}")

    results = []
    for sym in ["XAUUSD.s", "XAGUSD.s"]:
        for days in [30, 90]:
            r = run_backtest(sym, period_days=days, risk_pct=RISK_PER_TRADE_PCT)
            if r:
                results.append(r)

    mt5.shutdown()

    if results:
        print(f"\n{'='*60}")
        print("SUMMARY")
        print(f"{'='*60}")
        for r in results:
            print(f"{r['symbol']:12} {r['period']:3}d | "
                  f"Trades:{r['trades']:3} | WR:{r['win_rate']:.1f}% | "
                  f"PF:{r['pf']:.2f} | DD:{r['max_dd']:.1f}% | "
                  f"Monthly:{r['monthly']:+.1f}%")
