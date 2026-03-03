import MetaTrader5 as mt5

# --- Babata V6.6 Predator Configuration ---
PROJECT_NAME = "Babata_V6_6_Predator"
MAGIC_NUMBER = 20260606

SYMBOLS = ["XAUUSD.s", "XAGUSD.s"]

# Telegram
TG_TOKEN = "7646402171:AAHnO_8NTRI9fWJL1RQTwGOwz_bM0A07uDs"
TG_CHAT_ID = "6685908307"

# Aggressive Compounding
LOT_PER_1000 = 0.05
ENABLE_COMPOUNDING = True

# Risk & Trailing
MAX_DAILY_DD_PCT = 0.05
BE_RR_LEVEL = 2.0        # Move to BE when profit is 2x Risk
DAILY_FLAT_HHMM = "23:55"
LOCAL_TZ = "Asia/Phnom_Penh"

# Sniper Filters
ADX_THRESHOLD = 20
VOL_MULTIPLIER = 0.8

# Paths
JOURNAL_PATH = r"C:\TradingBot_v3\smc_v3_core\journal.csv"
BLACKLIST_PATH = r"C:\TradingBot_v3\smc_v3_core\blacklist.json"

# Execution
FILLING_MODE = mt5.ORDER_FILLING_FOK
DEVIATION = 30
POLL_SECONDS = 10
