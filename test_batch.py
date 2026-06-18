import yfinance as yf
import pandas as pd

tickers = ["AAPL", "MSFT", "AMZN", "NVDA", "GOOGL"]
try:
    print(f"Testing batch download for: {tickers}")
    data = yf.download(tickers, period="1y", interval="1d", group_by='ticker', progress=False)
    print(f"Columns returned: {data.columns[:10]}")
    for t in tickers:
        if t in data:
            print(f"{t}: data found, length {len(data[t])}")
            if "Adj Close" in data[t]:
                print(f"  {t} Adj Close found")
            else:
                print(f"  {t} Adj Close NOT found. Columns: {data[t].columns}")
        else:
            print(f"{t}: NOT found in data")
except Exception as e:
    print(f"Error: {e}")
