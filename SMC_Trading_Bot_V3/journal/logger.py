# ============================================================
# Trade Journal & Analytics V3.0
# ============================================================
import os
import csv
import json
from datetime import datetime, timezone

LOG_DIR     = os.path.join(os.path.dirname(__file__), '..', 'logs')
JOURNAL_CSV = os.path.join(LOG_DIR, 'journal.csv')
os.makedirs(LOG_DIR, exist_ok=True)

JOURNAL_HEADERS = [
    'date', 'time', 'symbol', 'direction', 'entry', 'sl', 'tp',
    'lots', 'rr', 'confidence', 'factors', 'session',
    'result', 'profit', 'pips', 'ticket', 'close_price', 'close_time'
]


def log(msg, level="INFO"):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] [{level}] {msg}"
    print(line)
    log_file = os.path.join(LOG_DIR, datetime.now(timezone.utc).strftime("%Y-%m-%d") + ".log")
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def record_trade_open(symbol, direction, entry, sl, tp, lots, rr, confidence, factors, session, ticket):
    """Record trade open to journal CSV."""
    now = datetime.now(timezone.utc)
    row = {
        'date':       now.strftime("%Y-%m-%d"),
        'time':       now.strftime("%H:%M:%S"),
        'symbol':     symbol,
        'direction':  direction,
        'entry':      round(entry, 5),
        'sl':         round(sl, 5),
        'tp':         round(tp, 5),
        'lots':       lots,
        'rr':         round(rr, 2),
        'confidence': round(confidence, 3),
        'factors':    '|'.join(factors) if factors else '',
        'session':    session,
        'result':     'OPEN',
        'profit':     '',
        'pips':       '',
        'ticket':     ticket,
        'close_price': '',
        'close_time':  '',
    }
    _write_row(row)
    log(f"TRADE OPEN | {symbol} {direction} | Entry:{entry:.5f} SL:{sl:.5f} TP:{tp:.5f} | Lots:{lots} | Conf:{confidence*100:.1f}%")


def record_trade_close(ticket, close_price, profit, pips):
    """Update journal CSV when trade closes."""
    rows = _read_all()
    for row in rows:
        if str(row.get('ticket')) == str(ticket) and row.get('result') == 'OPEN':
            row['result']      = 'WIN' if profit > 0 else 'LOSS'
            row['profit']      = round(profit, 2)
            row['pips']        = round(pips, 1)
            row['close_price'] = round(close_price, 5)
            row['close_time']  = datetime.now(timezone.utc).strftime("%H:%M:%S")
            break
    _write_all(rows)
    log(f"TRADE CLOSE | Ticket:{ticket} | {'WIN' if profit > 0 else 'LOSS'} | P&L: ${profit:+.2f}")


def get_daily_stats():
    """Return today's trading statistics."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    rows  = [r for r in _read_all() if r.get('date') == today and r.get('result') != 'OPEN']
    total  = len(rows)
    wins   = sum(1 for r in rows if r.get('result') == 'WIN')
    pnl    = sum(float(r.get('profit', 0) or 0) for r in rows)
    return {'total': total, 'wins': wins, 'pnl': round(pnl, 2)}


def _write_row(row):
    file_exists = os.path.isfile(JOURNAL_CSV)
    with open(JOURNAL_CSV, 'a', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=JOURNAL_HEADERS)
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)


def _read_all():
    if not os.path.isfile(JOURNAL_CSV):
        return []
    with open(JOURNAL_CSV, 'r', encoding='utf-8') as f:
        return list(csv.DictReader(f))


def _write_all(rows):
    with open(JOURNAL_CSV, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=JOURNAL_HEADERS)
        writer.writeheader()
        writer.writerows(rows)
