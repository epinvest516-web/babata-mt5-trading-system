# ============================================================
# Risk Management - Dynamic Position Sizing V3.0
# ============================================================
import MetaTrader5 as mt5
from config import *


def calculate_lot_size(symbol, entry, sl, confidence=0.6, use_compound=False):
    """
    Dynamic lot sizing based on:
    - Account balance (compound mode)
    - Confidence score (scale risk up/down)
    - Symbol contract specs (precise calculation)
    """
    account  = mt5.account_info()
    sym_info = mt5.symbol_info(symbol)
    if not account or not sym_info:
        return MIN_LOT_SIZE

    balance = account.equity if use_compound else account.balance

    # Dynamic risk based on confidence
    if confidence >= HIGH_CONFIDENCE:
        risk_pct = MAX_RISK_PCT
    elif confidence >= MIN_CONFIDENCE:
        # Linear scale between MIN and MAX
        ratio    = (confidence - MIN_CONFIDENCE) / (HIGH_CONFIDENCE - MIN_CONFIDENCE)
        risk_pct = MIN_RISK_PCT + ratio * (MAX_RISK_PCT - MIN_RISK_PCT)
    else:
        return None  # Below threshold, no trade

    # Compound boost
    if use_compound and balance >= COMPOUND_THRESHOLD:
        risk_pct = COMPOUND_RISK_PCT

    risk_amount = balance * (risk_pct / 100)
    sl_distance = abs(entry - sl)

    if sl_distance == 0:
        return MIN_LOT_SIZE

    # Precise lot calc using MT5 symbol data
    tick_value = sym_info.trade_tick_value
    tick_size  = sym_info.trade_tick_size

    if tick_size == 0:
        return MIN_LOT_SIZE

    value_per_lot = (sl_distance / tick_size) * tick_value
    if value_per_lot == 0:
        return MIN_LOT_SIZE

    raw_lots = risk_amount / value_per_lot
    step     = sym_info.volume_step
    lots     = round(raw_lots / step) * step
    lots     = max(MIN_LOT_SIZE, min(lots, MAX_LOT_SIZE))

    return round(lots, 2)


def check_daily_drawdown(daily_start_balance):
    """
    Returns True if daily drawdown limit is hit.
    """
    account = mt5.account_info()
    if not account or not daily_start_balance:
        return False
    dd_pct = (daily_start_balance - account.equity) / daily_start_balance * 100
    return dd_pct >= MAX_DAILY_LOSS_PCT


def check_weekly_drawdown(weekly_start_balance):
    account = mt5.account_info()
    if not account or not weekly_start_balance:
        return False
    dd_pct = (weekly_start_balance - account.equity) / weekly_start_balance * 100
    return dd_pct >= MAX_WEEKLY_LOSS_PCT


def already_in_trade(symbol):
    """Check if we already have an active position/order for this symbol."""
    positions = mt5.positions_get(symbol=symbol)
    orders    = mt5.orders_get(symbol=symbol)
    pos_count = len(positions) if positions else 0
    ord_count = len(orders) if orders else 0
    return (pos_count + ord_count) >= MAX_OPEN_PER_SYMBOL


def total_open_trades():
    positions = mt5.positions_get()
    return len(positions) if positions else 0
