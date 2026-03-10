# ============================================================
# SMC Phantom V3.1 - Main Execution Engine (Hybrid Mode)
# Smart Money Concepts + ICT Silver Bullet
#
# Architecture:
#   SWING:  Daily + H4 + H1 Bias → H1 Sweep → M15 FVG+OB+OTE
#   SCALP:  Silver Bullet Windows → M5 Sweep → M1 FVG Entry
#   RISK:   Swing 2% | Scalp 1% | Daily limit 5%
# ============================================================

import time
import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime, timezone

from config import *
from engine.smc_core import SMCCore
from strategies.silver_bullet import run_silver_bullet, in_silver_bullet_window
from risk.position_sizing import (
    calculate_lot_size, check_daily_drawdown,
    check_weekly_drawdown, already_in_trade, total_open_trades
)
from notifications.telegram import (
    alert_startup, alert_trade_open, alert_trailing_stop,
    alert_daily_limit, alert_daily_report, alert_signal_skipped
)
from journal.logger import log, record_trade_open, get_daily_stats

smc = SMCCore()

# ─────────────────────────────────────────────────────────
# STATE
# ─────────────────────────────────────────────────────────
daily_start_balance  = None
weekly_start_balance = None
last_day  = None
last_week = None
last_daily_report_hour = -1
daily_scalp_count    = 0       # Silver Bullet trades today


# ─────────────────────────────────────────────────────────
# DATA FETCH
# ─────────────────────────────────────────────────────────
def get_data(symbol, timeframe, count=200):
    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, count)
    if rates is None:
        return None
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    df = df.set_index('time')
    df.columns = [c.lower() for c in df.columns]
    return df


# ─────────────────────────────────────────────────────────
# KILLZONE & SESSION
# ─────────────────────────────────────────────────────────
def current_session():
    hour = datetime.now(timezone.utc).hour
    for name, (start, end) in KILLZONES.items():
        if start <= hour < end:
            return name
    return None


# ─────────────────────────────────────────────────────────
# ORDER EXECUTION
# ─────────────────────────────────────────────────────────
def execute_trade(symbol, direction, entry, sl, tp, lots, confidence, factors, session):
    rr = round(abs(tp - entry) / abs(entry - sl), 2) if abs(entry - sl) > 0 else 0

    if USE_LIMIT_ORDER:
        order_type = mt5.ORDER_TYPE_BUY_LIMIT if direction == 'bullish' else mt5.ORDER_TYPE_SELL_LIMIT
        action     = mt5.TRADE_ACTION_PENDING
        otype_str  = "limit"
    else:
        order_type = mt5.ORDER_TYPE_BUY if direction == 'bullish' else mt5.ORDER_TYPE_SELL
        action     = mt5.TRADE_ACTION_DEAL
        otype_str  = "market"

    request = {
        "action":      action,
        "symbol":      symbol,
        "volume":      lots,
        "type":        order_type,
        "price":       round(entry, 5),
        "sl":          round(sl, 5),
        "tp":          round(tp, 5),
        "deviation":   MT5_DEVIATION,
        "magic":       MAGIC,
        "comment":     f"SMC_V{VERSION}",
        "type_time":   mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }

    result = mt5.order_send(request)
    if result and result.retcode == mt5.TRADE_RETCODE_DONE:
        ticket = result.order
        log(f"✅ TRADE OPEN | {symbol} {direction.upper()} | "
            f"Entry:{entry:.5f} SL:{sl:.5f} TP:{tp:.5f} | "
            f"Lots:{lots} RR:1:{rr} Conf:{confidence*100:.1f}%")
        alert_trade_open(symbol, direction, entry, sl, tp, lots, rr, confidence, factors, session, otype_str)
        record_trade_open(symbol, direction, entry, sl, tp, lots, rr, confidence, factors, session, ticket)
        return ticket
    else:
        err = result.comment if result else "unknown"
        log(f"❌ TRADE FAILED | {symbol} | {err}", "ERROR")
        return None


# ─────────────────────────────────────────────────────────
# TRAILING STOP MANAGER
# ─────────────────────────────────────────────────────────
def manage_trailing_stops():
    if not TRAIL_ENABLED:
        return
    positions = mt5.positions_get()
    if not positions:
        return

    for pos in positions:
        if pos.magic != MAGIC:
            continue
        try:
            sym  = mt5.symbol_info(pos.symbol)
            if not sym:
                continue
            entry = pos.price_open
            sl    = pos.sl
            tp    = pos.tp
            price = sym.bid if pos.type == mt5.ORDER_TYPE_BUY else sym.ask

            if sl == 0 or tp == 0:
                continue

            risk   = abs(entry - sl)
            profit = abs(price - entry)

            # Move to breakeven at 1:1
            if profit >= risk * TRAIL_AT_RR:
                pt = sym.point * TRAIL_LOCK_POINTS
                if pos.type == mt5.ORDER_TYPE_BUY and sl < entry:
                    new_sl = entry + pt
                    if new_sl > sl:
                        mt5.order_send({
                            "action": mt5.TRADE_ACTION_SLTP,
                            "position": pos.ticket,
                            "sl": round(new_sl, 5),
                            "tp": pos.tp
                        })
                        alert_trailing_stop(pos.symbol, pos.ticket, new_sl)
                        log(f"🔒 TRAIL | {pos.symbol} #{pos.ticket} SL→{new_sl:.5f}")

                elif pos.type == mt5.ORDER_TYPE_SELL and sl > entry:
                    new_sl = entry - pt
                    if new_sl < sl:
                        mt5.order_send({
                            "action": mt5.TRADE_ACTION_SLTP,
                            "position": pos.ticket,
                            "sl": round(new_sl, 5),
                            "tp": pos.tp
                        })
                        alert_trailing_stop(pos.symbol, pos.ticket, new_sl)
                        log(f"🔒 TRAIL | {pos.symbol} #{pos.ticket} SL→{new_sl:.5f}")
        except Exception as e:
            log(f"Trailing error: {e}", "WARN")


# ─────────────────────────────────────────────────────────
# DAILY REPORT
# ─────────────────────────────────────────────────────────
def send_daily_report():
    account = mt5.account_info()
    if not account:
        return
    stats   = get_daily_stats()
    daily_pnl = account.balance - (daily_start_balance or account.balance)
    alert_daily_report(
        balance=account.balance,
        equity=account.equity,
        daily_pnl=daily_pnl,
        total_trades=stats['total'],
        win_trades=stats['wins']
    )


# ─────────────────────────────────────────────────────────
# MAIN ANALYSIS LOOP (per symbol)
# ─────────────────────────────────────────────────────────
def analyze_symbol(symbol, session):
    # Guard: max open trades
    if total_open_trades() >= MAX_OPEN_TRADES:
        return
    if already_in_trade(symbol):
        return

    # ── Fetch multi-TF data ──
    df_d  = get_data(symbol, mt5.TIMEFRAME_D1, 100)
    df_h4 = get_data(symbol, mt5.TIMEFRAME_H4, 200)
    df_h1 = get_data(symbol, mt5.TIMEFRAME_H1, 200)
    df_m15 = get_data(symbol, mt5.TIMEFRAME_M15, 200)

    if any(d is None for d in [df_d, df_h4, df_h1, df_m15]):
        log(f"[{symbol}] Data fetch failed", "WARN")
        return

    # ── Layer 1: HTF Bias (Daily + H4 + H1) ──
    bias = smc.get_htf_bias(df_d, df_h4, df_h1)
    if bias is None:
        return  # No clear bias, skip

    # ── Layer 2: Liquidity Sweep (H1) ──
    sweep = smc.detect_liquidity_sweep(df_h1, lookback=SWEEP_LOOKBACK)
    if not sweep:
        return  # No sweep, no setup

    direction = sweep  # 'bullish' or 'bearish'

    # Sweep direction must match HTF bias
    if direction != bias:
        log(f"[{symbol}] Sweep({direction}) ≠ Bias({bias}) — skip")
        return

    # ── Layer 3: FVG on M15 ──
    fvgs = smc.detect_fvg(df_m15)
    active_fvgs = [f for f in fvgs
                   if f['type'] == direction and not f['mitigated']
                   and f['index'] >= len(df_m15) - 10]
    best_fvg = active_fvgs[-1] if active_fvgs else None

    # ── Layer 4: Order Block on M15 ──
    obs = smc.detect_order_blocks(df_m15)
    recent_obs = [o for o in obs
                  if o['type'] == direction
                  and o['index'] >= len(df_m15) - 20]
    best_ob = recent_obs[-1] if recent_obs else None

    # ── Layer 5: OTE Zone ──
    high_20 = df_m15['high'].iloc[-20:].max()
    low_20  = df_m15['low'].iloc[-20:].min()
    ote     = smc.ote_zone(high_20, low_20, direction)

    # ── Determine Entry ──
    # Priority: FVG mid > OB mid > OTE ideal
    if best_fvg:
        entry = best_fvg['mid']
    elif best_ob:
        entry = best_ob['mid']
    else:
        entry = ote['entry_ideal']

    # ── Stop Loss ──
    swing_range = high_20 - low_20
    sl_buf      = swing_range * SL_BUFFER_PCT
    sl = (low_20 - sl_buf) if direction == 'bullish' else (high_20 + sl_buf)

    # ── Take Profit ──
    risk = abs(entry - sl)
    tp   = (entry + risk * MIN_RR) if direction == 'bullish' else (entry - risk * MIN_RR)

    # ── Confluence Score ──
    confidence, factors = smc.confluence_score(
        direction, bias, direction, best_fvg, best_ob, df_m15, df_h1, df_h4
    )

    log(f"[{symbol}] Signal {direction.upper()} | "
        f"Bias:{bias} Sweep:✓ FVG:{'✓' if best_fvg else '✗'} OB:{'✓' if best_ob else '✗'} | "
        f"Conf:{confidence*100:.1f}% [{', '.join(factors)}]")

    # ── Confidence Gate ──
    if confidence < MIN_CONFIDENCE:
        alert_signal_skipped(symbol, f"置信度不足({confidence*100:.1f}%)", confidence)
        return

    # ── Position Size ──
    use_compound = USE_COMPOUNDING and (mt5.account_info().balance >= COMPOUND_THRESHOLD)
    lots = calculate_lot_size(symbol, entry, sl, confidence, use_compound)
    if lots is None or lots < MIN_LOT_SIZE:
        log(f"[{symbol}] Lot size too small, skip", "WARN")
        return

    # ── Execute ──
    execute_trade(symbol, direction, entry, sl, tp, lots, confidence, factors, session)


# ─────────────────────────────────────────────────────────
# MAIN LOOP
# ─────────────────────────────────────────────────────────
def main():
    global daily_start_balance, weekly_start_balance, last_day, last_week, last_daily_report_hour

    if not mt5.initialize():
        print("❌ MT5 initialize failed!")
        return

    account = mt5.account_info()
    log(f"=== {BOT_NAME} {VERSION} ONLINE ===")
    log(f"Account:{account.login} | Balance:${account.balance:.2f} | Equity:${account.equity:.2f}")

    daily_start_balance  = account.balance
    weekly_start_balance = account.balance
    now = datetime.now(timezone.utc)
    last_day  = now.day
    last_week = now.isocalendar()[1]

    alert_startup(account)

    while True:
        try:
            now  = datetime.now(timezone.utc)

            # ── Daily/Weekly Reset ──
            if now.day != last_day:
                daily_start_balance = mt5.account_info().balance
                last_daily_report_hour = -1
                daily_scalp_count = 0
                last_day = now.day
                log("Daily balance reset + scalp counter reset")

            if now.isocalendar()[1] != last_week:
                weekly_start_balance = mt5.account_info().balance
                last_week = now.isocalendar()[1]
                log("Weekly balance reset")

            # ── Daily Report at 22:00 UTC ──
            if now.hour == 22 and last_daily_report_hour != 22:
                send_daily_report()
                last_daily_report_hour = 22

            # ── Risk Guards ──
            if check_daily_drawdown(daily_start_balance):
                acct = mt5.account_info()
                dd = (daily_start_balance - acct.equity) / daily_start_balance * 100
                alert_daily_limit(dd, acct.balance)
                log("⛔ Daily drawdown limit hit — pausing 5 min", "WARN")
                time.sleep(300)
                continue

            # ── Trailing Stop Management ──
            manage_trailing_stops()

            # ── Session Check ──
            session = current_session()
            if not session:
                time.sleep(60)
                continue

            log(f"🕐 Active session: {session}")

            # ── Silver Bullet Scalp (优先执行) ──
            sb_window = in_silver_bullet_window()
            if sb_window:
                log(f"⚡ Silver Bullet Window: {sb_window}")
                for symbol in PRIMARY_PAIRS:  # 超短线只做黄金+白银
                    try:
                        placed = run_silver_bullet(symbol, sb_window, daily_scalp_count, daily_start_balance)
                        if placed:
                            daily_scalp_count += 1
                    except Exception as e:
                        log(f"[SB][{symbol}] Error: {e}", "ERROR")

            # ── Swing 波段分析 ──
            for symbol in TARGET_PAIRS:
                try:
                    analyze_symbol(symbol, session)
                except Exception as e:
                    log(f"[{symbol}] Analysis error: {e}", "ERROR")

            time.sleep(30)

        except Exception as e:
            log(f"Main loop error: {e}", "ERROR")
            time.sleep(10)


if __name__ == "__main__":
    main()
