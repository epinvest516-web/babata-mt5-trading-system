---
name: mt5-trading
description: "Automated trading system management using Python and MetaTrader 5 API. Optimized for 24/7 VPS operation, including risk control, pyramid entries, and daily flat logic."
metadata:
  {
    "openclaw": { "emoji": "📈", "requires": { "os": "windows", "apps": ["MetaTrader 5"] } }
  }
---

# MT5 Trading System Management (Babata Edition)

This skill consolidates the hard-learned experience from deploying gold/silver trading bots on Windows Server 2022 VPS.

## 🛠️ Environment Wisdom

1.  **OS Requirement**: The `MetaTrader5` Python package is **Windows-only**. Never attempt to run it natively on macOS for execution.
2.  **User Context (Critical)**: Always run the bot as the **Logged-in User (e.g., Administrator)**, not as `SYSTEM`. Otherwise, the IPC bridge will fail with error `-10003` (Terminal not found).
3.  **Filling Mode**: Most brokers for Spot Gold/Silver require **`ORDER_FILLING_FOK`**. If orders fail with `10030`, use the `filling_test.py` script to detect the correct mode.

## 🚀 24/7 Stability Pattern

- **Supervisor Loop**: Use a `.cmd` wrapper with a `:loop` and `timeout /t 5` to automatically restart the Python process if it crashes.
- **Scheduled Task**: Register the task with `AtLogOn` trigger and `Highest` privileges. Ensure it runs as the user who is logged into the MT5 terminal.
- **Log Redirection**: Always redirect stdout and stderr to separate files (`bot.log`, `bot.err.log`) for remote monitoring.

## 📈 Strategy Execution Best Practices

1.  **Bar-Close Gating**: Evaluate signals only at the close of a candle (using index `-2`) to prevent "flickering" signals and excessive trading during a single bar.
2.  **Pyramiding (Scheme A)**: Add positions only when in profit by a distance of `0.6 * ATR(14)`. This prevents amplifying losing trades.
3.  **Partial TP**: Split entries (e.g., 50/30/20). Move remaining SL to Breakeven (BE) after TP1 hits (+1R) to lock in safety.
4.  **Daily Flat**: Implement a hard-coded time-based liquidation (e.g., 23:55 GMT+7) to avoid overnight swap risk and unexpected gaps.

## 🔍 Verification Checklist

- `tasklist /FI "IMAGENAME eq python.exe"`: Check if alive.
- `Get-Content bot.log -Tail 50`: Monitor signals and entry execution.
- `Get-Content bot.err.log`: Check for IPC timeouts or order errors.
