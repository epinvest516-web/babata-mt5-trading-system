import pandas as pd
import json
import os
import config
from datetime import datetime

def analyze_and_evolve():
    if not os.path.exists(config.JOURNAL_PATH):
        print("No journal found yet.")
        return

    try:
        df = pd.read_csv(config.JOURNAL_PATH)
        if len(df) < 10: return # Need statistical significance
        
        # Convert Time to datetime objects
        df['Time'] = pd.to_datetime(df['Time'])
        df['Hour'] = df['Time'].dt.hour
        df['Day'] = df['Time'].dt.day_name()
        
        # Identify failure patterns
        # Example: Group by Hour and see Win Rate
        stats = df.groupby(['Day', 'Hour']).agg({'Success': ['count', lambda x: (x == 'WIN').sum()]})
        stats.columns = ['Total', 'Wins']
        stats['WinRate'] = stats['Wins'] / stats['Total']
        
        # Find 'Kill Zones' (Total > 3 and WinRate < 10%)
        kill_zones = stats[(stats['Total'] >= 3) & (stats['WinRate'] < 0.10)].index.tolist()
        
        blacklist = []
        for day, hour in kill_zones:
            blacklist.append({"day": day, "hour": hour})
            
        with open(config.BLACKLIST_PATH, 'w') as f:
            json.dump(blacklist, f)
            
        print(f"🧠 Evolution Complete. {len(blacklist)} zones added to blacklist.")
        return len(blacklist)
    except Exception as e:
        print(f"Evolution Error: {e}")
        return 0

if __name__ == "__main__":
    analyze_and_evolve()
