# SMC Phantom V3.0 — 安装指南

## 系统要求
- Windows 10/11 (64-bit)
- Python 3.10+ (推荐 3.14)
- MetaTrader 5 已安装并登录
- 稳定网络连接

---

## 一、安装步骤

### 1. 解压文件
将 `SMC_Trading_Bot` 文件夹解压到：
```
C:\SMC_Trading_Bot\
```

### 2. 安装依赖
打开 PowerShell，执行：
```powershell
cd C:\SMC_Trading_Bot
c:\python314\python.exe -m pip install -r requirements.txt
```

### 3. 配置 MT5
确保 MT5 终端已：
- 登录你的经纪商账户
- 允许自动交易（工具 → 选项 → 专家顾问 → 允许算法交易）
- 添加交易品种：XAUUSD.s, XAGUSD.s, EURUSD.s 等

### 4. 修改配置（可选）
编辑 `C:\SMC_Trading_Bot\config.py`：
```python
RISK_PER_TRADE_PCT = 2.0    # 每笔风险 %
MAX_DAILY_LOSS_PCT = 5.0    # 日亏损上限 %
TARGET_PAIRS = [...]        # 交易品种
```

---

## 二、启动系统

### 实盘运行
双击：`START_LIVE.cmd`

或 PowerShell：
```powershell
cd C:\SMC_Trading_Bot
c:\python314\python.exe main.py
```

### 运行回测
双击：`RUN_BACKTEST.cmd`

---

## 三、文件结构
```
C:\SMC_Trading_Bot\
├── main.py              # 主程序
├── config.py            # 配置文件
├── START_LIVE.cmd       # 启动脚本
├── RUN_BACKTEST.cmd     # 回测脚本
├── requirements.txt     # 依赖列表
├── engine\
│   └── smc_core.py      # SMC 核心引擎
├── risk\
│   └── position_sizing.py  # 风控系统
├── notifications\
│   └── telegram.py      # Telegram 通知
├── journal\
│   └── logger.py        # 交易日志
├── backtest\
│   └── engine.py        # 回测引擎
├── logs\                # 日志文件（自动生成）
│   ├── YYYY-MM-DD.log
│   └── journal.csv      # 交易记录
└── docs\
    └── INSTALL.md       # 本文件
```

---

## 四、Telegram 通知说明

系统会自动发送以下通知：
| 类型 | 触发条件 |
|------|---------|
| 🟢 系统启动 | 程序启动时 |
| 🚀 开单信号 | 每次入场 |
| 🔒 追踪止损 | 达到1:1盈亏比 |
| 🛑 风控警报 | 日亏损触发 |
| 📊 每日报告 | 每天 22:00 UTC |

---

## 五、注意事项

1. **MT5 必须保持开启**，系统通过 MT5 API 执行交易
2. **VPS 建议 24/7 运行**，避免错过信号
3. **首次运行**建议先用模拟账户测试 1-2 周
4. **风险提示**：所有交易均有亏损风险，请在承受范围内操作
