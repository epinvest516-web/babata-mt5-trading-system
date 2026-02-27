import MetaTrader5 as mt5

PROJECT_NAME = "Babata_MT5_Bot_v2_Pyramid"
MAGIC_NUMBER = 20260226

SYMBOLS = ["XAUUSD.s", "XAGUSD.s"]

# Timeframe for validation: M30
TIMEFRAME = mt5.TIMEFRAME_M30

# Execution mode
FILLING_MODE = mt5.ORDER_FILLING_FOK
DEVIATION = 30

# ---- Validation risk caps (per symbol) ----
# Max total volume per symbol during validation
MAX_VOLUME_PER_SYMBOL = 0.03
VOLUME_STEP = 0.01
MIN_VOLUME = 0.01

# Split ratio 50/30/20
ENTRY_WEIGHTS = (0.50, 0.30, 0.20)

# Daily max drawdown
MAX_DAILY_DD_PCT = 0.02

# SL/TP points baseline (used to define R)
SL_POINTS = 500
TP1_R = 1.0
TP2_R = 2.0

# Pyramid spacing: X = 0.6 * ATR(14)
ATR_PERIOD = 14
PYRAMID_ATR_MULT = 0.6

# Strategy parameters
RSI_PERIOD = 14
RSI_LOWER = 30
RSI_UPPER = 70
BB_PERIOD = 20
BB_DEV = 2.0
BAND_BUFFER_POINTS = 0

# Runner trailing stop uses last closed candle low/high

# Polling
POLL_SECONDS = 10

# Daily flat (no overnight)
LOCAL_TZ = "Asia/Phnom_Penh"  # GMT+7
DAILY_FLAT_HHMM = "23:55"
NO_TRADE_MINUTES_AFTER_FLAT = 10

LOG_PATH = r"C:\TradingBot\bot.log"
ERROR_LOG_PATH = r"C:\TradingBot\bot.err.log"
