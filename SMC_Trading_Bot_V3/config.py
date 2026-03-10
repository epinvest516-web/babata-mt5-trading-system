# ============================================================
# SMC Phantom V3.0 - Configuration
# Smart Money Concepts Automated Trading System
# ============================================================

# --- System Identity ---
BOT_NAME    = "SMC_Phantom_V3.1_Hybrid"
VERSION     = "3.1.0"
MAGIC       = 20260310

# ============================================================
# TRADING PAIRS
# ============================================================
# Primary (Metals) - Highest priority
PRIMARY_PAIRS = ["XAUUSD.s", "XAGUSD.s"]

# Secondary (Major FX) - Active when metals have no setup
SECONDARY_PAIRS = ["EURUSD.s", "GBPUSD.s", "USDJPY.s"]

# All active pairs (can toggle secondary)
ENABLE_SECONDARY = True
TARGET_PAIRS = PRIMARY_PAIRS + (SECONDARY_PAIRS if ENABLE_SECONDARY else [])

# ============================================================
# TIMEFRAMES (Multi-TF Confluence)
# ============================================================
TF_DAILY  = "D1"     # Daily Bias (Macro direction)
TF_H4     = "H4"     # HTF Structure (Trend confirmation)
TF_H1     = "H1"     # Entry structure + liquidity zones
TF_M15    = "M15"    # Entry trigger
TF_M5     = "M5"     # Precision entry refinement

# ============================================================
# RISK MANAGEMENT
# ============================================================
INITIAL_BALANCE      = 5000.0
RISK_PER_TRADE_PCT   = 2.0       # Base risk per trade (%)
MAX_RISK_PCT         = 3.0       # Max risk when high confidence (%)
MIN_RISK_PCT         = 1.0       # Min risk when lower confidence (%)
MAX_DAILY_LOSS_PCT   = 5.0       # Daily hard stop (%)
MAX_WEEKLY_LOSS_PCT  = 10.0      # Weekly protection (%)
MAX_OPEN_TRADES      = 3         # Max simultaneous positions
MAX_OPEN_PER_SYMBOL  = 1         # Max per symbol
MIN_LOT_SIZE         = 0.01
MAX_LOT_SIZE         = 10.0
MT5_DEVIATION        = 30

# ============================================================
# COMPOUNDING MODE
# ============================================================
USE_COMPOUNDING      = True
# Activate full compound mode when balance reaches this level:
COMPOUND_THRESHOLD   = 10000.0   # At $10k, start aggressive compounding
COMPOUND_RISK_PCT    = 2.5       # Risk % in compound mode

# ============================================================
# SMC ENTRY LOGIC
# ============================================================
MIN_RR               = 2.5       # Minimum Risk:Reward ratio
HIGH_CONF_RR         = 2.0       # Allow 1:2 when confidence >85%
OTE_LOW              = 0.618     # OTE zone start (Fib)
OTE_HIGH             = 0.786     # OTE zone end (Fib)
SL_BUFFER_PCT        = 0.15      # SL buffer beyond swing
SWEEP_LOOKBACK       = 40        # Bars to look back for liquidity

# Confidence thresholds
MIN_CONFIDENCE       = 0.60      # Min to enter trade
HIGH_CONFIDENCE      = 0.80      # High conf → heavier position

# ============================================================
# ORDER TYPE
# ============================================================
USE_LIMIT_ORDER      = True      # Limit order at OTE (precision)

# ============================================================
# SILVER BULLET SCALP SETTINGS
# ============================================================
SB_RISK_PCT        = 1.0    # 1% risk per scalp trade
SB_MIN_RR          = 1.5    # Minimum RR for scalp entry
SB_MAX_DAILY       = 6      # Max scalp trades per day
SB_DAILY_TARGET    = 500.0  # 日盈利目标 $500 → 达到后暂停超短线

# ============================================================
# TRAILING STOP
# ============================================================
TRAIL_ENABLED        = True
TRAIL_AT_RR          = 1.0       # Start trailing at 1:1
TRAIL_LOCK_POINTS    = 10        # Lock this many points profit

# ============================================================
# KILLZONES (UTC Hours)
# ============================================================
KILLZONES = {
    "Tokyo":    (0,  3),
    "London":   (7, 11),
    "NY_Open":  (12, 16),
    "NY_Close": (19, 21),
}

# ============================================================
# TELEGRAM NOTIFICATIONS
# ============================================================
TELEGRAM_TOKEN   = "8712584283:AAG0z5L-1HYMM_QChDvXexfqFW3D84hd5Js"
TELEGRAM_CHAT_ID = "6685908307"

# ============================================================
# MONTHLY TARGET & COMPOUNDING PLAN
# ============================================================
# Realistic targets (compound at ~20% monthly):
# Month 1:  $5,000  →  $6,000   (+$1,000)
# Month 3:  $8,640  →  $10,368  (+$1,728)
# Month 6:  $14,930 →  $17,916  (+$2,986)
# Month 9:  $25,795 →  $30,958  (+$5,163)
# Month 12: $44,598 →  $53,517  (+$8,919)
# Month 18: $133,174 → $15k-20k+/month achievable
MONTHLY_TARGET_PCT = 20.0
