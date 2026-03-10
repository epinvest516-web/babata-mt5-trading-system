# ============================================================
# ICT Silver Bullet - Scalp Module V3.1
# Time Windows: London 10:00-11:00 UTC / NY 14:00-15:00 UTC
# Logic: Liquidity Sweep → M5 FVG → Limit Entry
# Risk: 1% per scalp (separate from swing allocation)
# ============================================================
import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime, timezone
from engine.smc_core import SMCCore
from risk.position_sizing import already_in_trade, total_open_trades
from notifications.telegram import _send
from journal.logger import log, record_trade_open
from config import *

smc = SMCCore()

# ─────────────────────────────────────────────
# Silver Bullet Windows (UTC)
# ─────────────────────────────────────────────
SILVER_BULLET_WINDOWS = {
    "London_SB":  (10, 0,  11, 0),   # 10:00 - 11:00 UTC
    "NY_Open_SB": (14, 0,  15, 0),   # 14:00 - 15:00 UTC
}

# Scalp-specific settings
SB_RISK_PCT  = 1.0    # 1% risk per scalp
SB_MIN_RR    = 1.5    # Minimum RR for scalp
SB_MAX_DAILY = 4      # Max scalp trades per day


def in_silver_bullet_window():
    """Check if current time is within any Silver Bullet window."""
    now = datetime.now(timezone.utc)
    for name, (sh, sm, eh, em) in SILVER_BULLET_WINDOWS.items():
        start = now.replace(hour=sh, minute=sm, second=0)
        end   = now.replace(hour=eh, minute=em, second=0)
        if start <= now <= end:
            return name
    return None


def get_m5_data(symbol, count=100):
    rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, 0, count)
    if rates is None:
        return None
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    df = df.set_index('time')
    df.columns = [c.lower() for c in df.columns]
    return df


def get_m1_data(symbol, count=60):
    rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M1, 0, count)
    if rates is None:
        return None
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    df = df.set_index('time')
    df.columns = [c.lower() for c in df.columns]
    return df


def calculate_scalp_lot(symbol, entry, sl):
    """Calculate lot size for scalp (1% risk)."""
    account  = mt5.account_info()
    sym_info = mt5.symbol_info(symbol)
    if not account or not sym_info:
        return MIN_LOT_SIZE

    risk_amount = account.balance * (SB_RISK_PCT / 100)
    sl_dist     = abs(entry - sl)
    if sl_dist == 0:
        return MIN_LOT_SIZE

    tick_value = sym_info.trade_tick_value
    tick_size  = sym_info.trade_tick_size
    if tick_size == 0:
        return MIN_LOT_SIZE

    value_per_lot = (sl_dist / tick_size) * tick_value
    if value_per_lot == 0:
        return MIN_LOT_SIZE

    lots = risk_amount / value_per_lot
    step = sym_info.volume_step
    lots = round(lots / step) * step
    return max(MIN_LOT_SIZE, min(round(lots, 2), MAX_LOT_SIZE))


def send_scalp_alert(symbol, direction, entry, sl, tp, lots, rr, window):
    dir_str = "📈 BUY ↑" if direction == 'bullish' else "📉 SELL ↓"
    _send(
        f"⚡ <b>【Silver Bullet 超短线】</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📌 品种: <b>{symbol}</b>\n"
        f"🧭 方向: <b>{dir_str}</b>\n"
        f"🕐 窗口: {window}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"💰 入场: <code>{entry:.5f}</code>\n"
        f"🛡️ 止损: <code>{sl:.5f}</code>\n"
        f"🎯 止盈: <code>{tp:.5f}</code>\n"
        f"📊 盈亏比: <b>1:{rr:.1f}</b>\n"
        f"📦 手数: <b>{lots}</b>\n"
        f"⚡ 模式: ICT Silver Bullet | 风险: {SB_RISK_PCT}%"
    )


def run_silver_bullet(symbol, window, daily_scalp_count):
    """
    Main Silver Bullet execution logic.
    Returns True if trade was placed.
    """
    # Daily scalp limit
    if daily_scalp_count >= SB_MAX_DAILY:
        return False

    # Guard: no duplicate positions
    if already_in_trade(symbol):
        return False

    if total_open_trades() >= MAX_OPEN_TRADES:
        return False

    # ── Get M5 data (sweep detection) ──
    df_m5 = get_m5_data(symbol, 60)
    df_m1 = get_m1_data(symbol, 60)
    if df_m5 is None or df_m1 is None:
        return False

    # ── Step 1: Liquidity Sweep on M5 ──
    sweep = smc.detect_liquidity_sweep(df_m5, lookback=20)
    if not sweep:
        return False

    direction = sweep  # 'bullish' or 'bearish'

    # ── Step 2: FVG on M1 after sweep ──
    fvgs = smc.detect_fvg(df_m1)
    # Only consider FVGs from last 10 candles
    recent_fvgs = [f for f in fvgs
                   if f['type'] == direction
                   and not f['mitigated']
                   and f['index'] >= len(df_m1) - 10]

    if not recent_fvgs:
        return False

    best_fvg = recent_fvgs[-1]

    # ── Step 3: Calculate Entry ──
    entry = best_fvg['mid']

    # SL: beyond the FVG + small buffer
    sym_info = mt5.symbol_info(symbol)
    if not sym_info:
        return False

    fvg_size = best_fvg['top'] - best_fvg['bottom']
    sl_buffer = fvg_size * 0.5 + sym_info.point * 10

    if direction == 'bullish':
        sl = best_fvg['bottom'] - sl_buffer
        tp = entry + abs(entry - sl) * SB_MIN_RR
    else:
        sl = best_fvg['top'] + sl_buffer
        tp = entry - abs(entry - sl) * SB_MIN_RR

    # ── Step 4: Validate RR ──
    rr = abs(tp - entry) / abs(entry - sl) if abs(entry - sl) > 0 else 0
    if rr < SB_MIN_RR:
        return False

    # ── Step 5: Calculate Lot ──
    lots = calculate_scalp_lot(symbol, entry, sl)

    # ── Step 6: Execute (Limit Order) ──
    order_type = mt5.ORDER_TYPE_BUY_LIMIT if direction == 'bullish' else mt5.ORDER_TYPE_SELL_LIMIT

    request = {
        "action":       mt5.TRADE_ACTION_PENDING,
        "symbol":       symbol,
        "volume":       lots,
        "type":         order_type,
        "price":        round(entry, 5),
        "sl":           round(sl, 5),
        "tp":           round(tp, 5),
        "deviation":    MT5_DEVIATION,
        "magic":        MAGIC + 1,        # +1 to distinguish scalp from swing
        "comment":      f"SB_V{VERSION}",
        "type_time":    mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }

    result = mt5.order_send(request)
    if result and result.retcode == mt5.TRADE_RETCODE_DONE:
        ticket = result.order
        log(f"⚡ SILVER BULLET | {symbol} {direction.upper()} | "
            f"Entry:{entry:.5f} SL:{sl:.5f} TP:{tp:.5f} | "
            f"Lots:{lots} RR:1:{rr:.1f} | Window:{window}")
        send_scalp_alert(symbol, direction, entry, sl, tp, lots, rr, window)
        record_trade_open(
            symbol, direction, entry, sl, tp, lots, rr,
            confidence=0.75, factors=["SilverBullet", "FVG", "Sweep"],
            session=window, ticket=ticket
        )
        return True
    else:
        err = result.comment if result else "unknown"
        log(f"⚡ SB FAILED | {symbol} | {err}", "ERROR")
        return False
