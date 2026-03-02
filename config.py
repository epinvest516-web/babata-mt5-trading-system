import MetaTrader5 as mt5

# --- Babata V5.0 Ultimate Configuration (暴利进化版) ---
PROJECT_NAME = "Babata_V5_Ultimate"
MAGIC_SCALP = 1001
MAGIC_SWING = 2001
MAGIC_NUMBER = 20260505

# 交易品种 (EBC后缀)
SYMBOLS = ["XAUUSD.s", "XAGUSD.s", "USDIDX"]

# Telegram 机器人配置 (已注入)
TG_TOKEN = "7646402171:AAHnO_8NTRI9fWJL1RQTwGOwz_bM0A07uDs"
TG_CHAT_ID = "6685908307"

# --- 核心风控与资金管理 ---
# 1. 激进复利模式
# 计算公式: Lot = (Balance / 1000) * LOT_PER_1000
# 例如: $1000 -> 0.05手, $5000 -> 0.25手
ENABLE_COMPOUNDING = True
LOT_PER_1000 = 0.05 
MAX_LOT_SIZE = 5.0  # 单笔上限，防止流动性不足

# 2. 动态 ATR 止损 (替代固定点数)
ATR_PERIOD = 14
ATR_MULTIPLIER_SL = 2.0  # 止损 = 2倍 ATR
ATR_MULTIPLIER_TP = 4.0  # 止盈 = 4倍 ATR (盈亏比 1:2)

# 3. 每日硬性风控
MAX_DAILY_DD_PCT = 0.05 # 5% 强制止损
DAILY_FLAT_HHMM = "23:55"
LOCAL_TZ = "Asia/Phnom_Penh"

# 执行设置
FILLING_MODE = mt5.ORDER_FILLING_FOK
DEVIATION = 30
POLL_SECONDS = 10

# 路径 (保持 V3 结构)
LOG_PATH = r"C:\TradingBot_v3\smc_v3_core\bot.log"
