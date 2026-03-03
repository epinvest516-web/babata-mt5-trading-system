import requests
import pandas as pd
import os
import config
from datetime import datetime

class Reporter:
    def __init__(self):
        self.journal_path = config.JOURNAL_PATH
        if not os.path.exists(self.journal_path):
            df = pd.DataFrame(columns=["Time", "Symbol", "Magic", "Action", "Price", "Lot", "SL", "TP", "Reason", "Success"])
            df.to_csv(self.journal_path, index=False)

    def send_tg(self, message):
        try:
            url = f"https://api.telegram.org/bot{config.TG_TOKEN}/sendMessage"
            requests.post(url, data={"chat_id": config.TG_CHAT_ID, "text": message}, timeout=5)
        except: pass

    def log_trade(self, symbol, magic, action, price, lot, sl, tp, reason):
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        data = [[now, symbol, magic, action, price, lot, sl, tp, reason, "PENDING"]]
        df = pd.DataFrame(data)
        df.to_csv(self.journal_path, mode='a', header=False, index=False)

    def generate_daily_report(self):
        # Read journal and summarize
        try:
            df = pd.read_csv(self.journal_path)
            # Filter for today's trades
            today = datetime.now().strftime("%Y-%m-%d")
            df_today = df[df['Time'].str.contains(today)]
            count = len(df_today)
            if count == 0: return "今日无交易记录。"
            
            summary = f"📊 **Babata 每日战报 ({today})**\n"
            summary += f"总计交易: {count} 次\n"
            # In a real system, we'd fetch actual PnL from MT5 history
            return summary
        except:
            return "生成报告失败。"
