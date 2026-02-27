Babata MT5 Bot v2 (Pyramid + Partial TP) — Validation Pack
=========================================================

Key
- Timeframe: M30
- Pyramiding: add only when in profit by X = 0.6 * ATR(14)
- Max total volume per symbol (validation): 0.03
- Split: 50% / 30% / 20% (rounded to 0.01 step)
- TP1 at +1R closes one leg and moves SL to breakeven
- TP2 at +2R closes another leg
- Runner trails SL by last closed candle low/high
- Daily flat 23:55 GMT+7; blocks entries for 10 minutes
- Filling mode: FOK

Install clean
1) Stop old bot:
   taskkill /F /IM python.exe
2) Replace folder:
   delete C:\TradingBot and recreate
3) Copy all files from this zip to C:\TradingBot
4) Install deps:
   cd C:\TradingBot
   pip install -r requirements.txt
5) Install task (admin PowerShell):
   powershell -ExecutionPolicy Bypass -File .\INSTALL_24X7_TASK.ps1
6) Start now:
   Start-ScheduledTask -TaskName BabataMT5Bot

Logs
- C:\TradingBot\bot.log
- C:\TradingBot\bot.err.log

After validation
- Increase MAX_VOLUME_PER_SYMBOL up to 0.05
- Tune ATR multiplier and SL points
