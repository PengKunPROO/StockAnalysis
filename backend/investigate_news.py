import akshare as ak
from datetime import date, timedelta

# Check staleness
df = ak.stock_news_em(symbol='600519')
time_col = df.columns[3]
title_col = df.columns[1]

print(f"=== stock_news_em('600519') ===")
print(f"Total: {len(df)} items")
latest_date = df[time_col].max()
print(f"Latest date: {latest_date}")
print(f"Today: {date.today()}")

print("\nRecent (last 7 days):")
cutoff = date.today() - timedelta(days=7)
recent_count = 0
for _, row in df.iterrows():
    pub_str = str(row[time_col])[:10]
    try:
        pub_date = date.fromisoformat(pub_str)
        if pub_date >= cutoff:
            print(f"  {pub_str} | {str(row[title_col])[:60]}")
            recent_count += 1
    except:
        pass
print(f"Recent count: {recent_count}")

# Try other stocks with more activity
for sym in ['000858', '000001', '300750']:
    df2 = ak.stock_news_em(symbol=sym)
    latest = df2[time_col].max()
    print(f"\n{sym}: latest={latest}, total={len(df2)}")
