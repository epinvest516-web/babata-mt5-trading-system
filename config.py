import MetaTrader5 as mt5

# --- Babata V6.0 Ultimate Configuration ---
PROJECT_NAME = "Babata_V6_Ultimate"
MAGIC_NUMBER = 20260606

# Symbols (EBC Suffix)
SYMBOLS = ["XAUUSD.s", "XAGUSD.s"]

# Telegram (Provided by User)
TG_TOKEN = "7646402171:AAHnO_8NTRI9fWJL1RQTwGOwz_bM0A07uDs"
TG_CHAT_ID = "6685908307"

# Risk Management
MAX_DAILY_DD_PCT = 0.05
LOT_PER_1000 = 0.05
ENABLE_COMPOUNDING = True

# Reporting
DAILY_REPORT_HHMM = "23:50"
JOURNAL_PATH = r"C:\TradingBot_v3\smc_v3_core\journal.csv"
LOCAL_TZ = "Asia/Phnom_Penh"

# Technicals
ATR_PERIOD = 14
EMA_LONG_PERIOD = 200
EMA_VEGAS_1 = 144
EMA_VEGAS_2 = 169

# MT5 Settings
FILLING_MODE = mt5.ORDER_FILLING_FOK
DEVIATION = 30
POLL_SECONDS = 10
