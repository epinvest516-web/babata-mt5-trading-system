# ============================================================
# Telegram Notification System V3.0
# Categorized alerts for SMC Phantom
# ============================================================
import requests
from datetime import datetime, timezone
from config import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, BOT_NAME


def _send(msg, parse_mode="HTML"):
    if not TELEGRAM_TOKEN:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": msg,
            "parse_mode": parse_mode
        }, timeout=10)
    except Exception as e:
        print(f"[Telegram Error] {e}")


def ts():
    return datetime.now(timezone.utc).strftime("%H:%M UTC")


# ── System Alerts ──────────────────────────────────────────
def alert_startup(account_info):
    _send(
        f"🟢 <b>[{BOT_NAME}] 系统启动</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"⏰ 时间: {ts()}\n"
        f"🏦 账户: <code>{account_info.login}</code>\n"
        f"💰 余额: <b>${account_info.balance:,.2f}</b>\n"
        f"📊 净值: <b>${account_info.equity:,.2f}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"✅ 监控品种: 黄金 | 白银 | 外汇\n"
        f"🕐 时段: 亚盘 + 欧盘 + 美盘"
    )


def alert_trade_open(symbol, direction, entry, sl, tp, lots, rr, confidence, factors, session, order_type):
    dir_emoji = "📈 BUY" if direction == 'bullish' else "📉 SELL"
    dir_cn    = "做多 ↑" if direction == 'bullish' else "做空 ↓"
    _send(
        f"🚀 <b>【入场信号】SMC幽灵开单</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📌 品种: <b>{symbol}</b>\n"
        f"🧭 方向: <b>{dir_emoji} {dir_cn}</b>\n"
        f"🏛️ 盘口: {session}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"💰 入场价: <code>{entry:.5f}</code>\n"
        f"🛡️ 止损价: <code>{sl:.5f}</code>\n"
        f"🎯 止盈价: <code>{tp:.5f}</code>\n"
        f"📊 盈亏比: <b>1:{rr:.1f}</b>\n"
        f"📦 手数: <b>{lots}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🧠 胜率推演: <b>{confidence*100:.1f}%</b>\n"
        f"🔗 信号因素: {' | '.join(factors)}\n"
        f"⚙️ 模式: {'限价单' if order_type == 'limit' else '市价单'}\n"
        f"⏰ 时间: {ts()}"
    )


def alert_trade_close(symbol, direction, entry, close_price, profit, pips, ticket):
    result = "✅ 盈利" if profit > 0 else "❌ 亏损"
    _send(
        f"💼 <b>【平仓通知】</b> {result}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📌 品种: <b>{symbol}</b>\n"
        f"🎫 单号: <code>{ticket}</code>\n"
        f"💰 入场: <code>{entry:.5f}</code> → 出场: <code>{close_price:.5f}</code>\n"
        f"📈 点数: {'+' if pips > 0 else ''}{pips:.1f} pips\n"
        f"💵 盈亏: <b>${'+' if profit > 0 else ''}{profit:.2f}</b>\n"
        f"⏰ 时间: {ts()}"
    )


def alert_trailing_stop(symbol, ticket, new_sl):
    _send(
        f"🔒 <b>【追踪止损】移至保本</b>\n"
        f"📌 {symbol} | 单号: <code>{ticket}</code>\n"
        f"🛡️ 新止损: <code>{new_sl:.5f}</code>\n"
        f"⏰ {ts()}"
    )


def alert_daily_limit(drawdown_pct, balance):
    _send(
        f"🛑 <b>【风控警报】日亏损触发！</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📉 今日亏损: <b>{drawdown_pct:.2f}%</b>\n"
        f"💰 当前余额: <b>${balance:,.2f}</b>\n"
        f"⚠️ 系统已暂停，明日 UTC 00:00 自动恢复\n"
        f"⏰ {ts()}"
    )


def alert_daily_report(balance, equity, daily_pnl, total_trades, win_trades):
    win_rate = (win_trades / total_trades * 100) if total_trades > 0 else 0
    pnl_sign = "+" if daily_pnl >= 0 else ""
    _send(
        f"📊 <b>【每日报告】{datetime.now(timezone.utc).strftime('%Y-%m-%d')}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"💰 余额: <b>${balance:,.2f}</b>\n"
        f"📊 净值: <b>${equity:,.2f}</b>\n"
        f"💵 今日盈亏: <b>{pnl_sign}${daily_pnl:,.2f}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📈 总交易: {total_trades} 笔\n"
        f"✅ 盈利: {win_trades} 笔\n"
        f"🎯 胜率: <b>{win_rate:.1f}%</b>\n"
        f"⏰ {ts()}"
    )


def alert_signal_skipped(symbol, reason, confidence):
    _send(
        f"⏭️ <b>【信号跳过】</b>\n"
        f"📌 {symbol} | 置信度: {confidence*100:.1f}%\n"
        f"📝 原因: {reason}\n"
        f"⏰ {ts()}"
    )
