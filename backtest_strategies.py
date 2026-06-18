import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime

def run_backtest(ticker="^GSPC"):
    print(f"Fetching data for {ticker}...")
    # Get max history for S&P 500
    df = yf.download(ticker, period="max")
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    
    # Calculate years in dataset
    start_date = df.index[0]
    end_date = df.index[-1]
    total_years = (end_date - start_date).days / 365.25
    
    results = {}

    # --- 1. BUY AND HOLD (Benchmark) ---
    initial_investment = 10000
    final_value = (df['Close'].iloc[-1] / df['Close'].iloc[0]) * initial_investment
    total_return = (final_value - initial_investment) / initial_investment
    avg_yearly = (1 + total_return) ** (1 / total_years) - 1
    
    results["Buy & Hold"] = {
        "Total Return": f"{total_return*100:.2f}%",
        "Avg Yearly Return": f"{avg_yearly*100:.2f}%",
        "Raw": avg_yearly
    }

    # --- 2. CFO STRATEGY (50/200 SMA) ---
    df['SMA50'] = df['Close'].rolling(window=50).mean()
    df['SMA200'] = df['Close'].rolling(window=200).mean()
    
    df['CFO_Signal'] = np.where(df['SMA50'] > df['SMA200'], 1, 0)
    df['CFO_Returns'] = df['CFO_Signal'].shift(1) * df['Close'].pct_change()
    
    total_return_cfo = (1 + df['CFO_Returns']).prod() - 1
    avg_yearly_cfo = (1 + total_return_cfo) ** (1 / total_years) - 1
    
    results["CFO Strategy"] = {
        "Total Return": f"{total_return_cfo*100:.2f}%",
        "Avg Yearly Return": f"{avg_yearly_cfo*100:.2f}%",
        "Raw": avg_yearly_cfo
    }

    # --- 3. ATMS STRATEGY (Adaptive MA + Momentum + ATR) ---
    # KAMA Calculation
    n = 2
    fast = 2
    slow = 10
    change = (df["Close"] - df["Close"].shift(n)).abs()
    volatility = df["Close"].diff().abs().rolling(n).sum()
    er = change / volatility
    sc = (er * (2/(fast+1) - 2/(slow+1)) + 2/(slow+1))**2
    sc = sc.fillna(0) # Fix NaN propagation
    
    kama = [df["Close"].iloc[0]]
    for i in range(1, len(df)):
        kama.append(kama[-1] + sc.iloc[i] * (df["Close"].iloc[i] - kama[-1]))
    df['KAMA'] = kama

    # Momentum (RSI + MACD Slope)
    delta = df["Close"].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    rsi = rsi.fillna(50)
    norm_rsi = (rsi - 50) / 50
    
    ema12 = df["Close"].ewm(span=12).mean()
    ema26 = df["Close"].ewm(span=26).mean()
    macd = ema12 - ema26
    macd_slope = macd.diff().fillna(0)
    norm_macd_slope = (macd_slope / macd_slope.rolling(20).std().replace(0, np.nan)).fillna(0).clip(-1, 1)
    
    momentum_score = (norm_rsi + norm_macd_slope) / 2
    adjusted_ma = df['KAMA'] * (1 - momentum_score * 0.01)
    
    # 4. Volatility Adjustment (ATR Band)
    high_low = df['High'] - df['Low']
    high_close = (df['High'] - df['Close'].shift()).abs()
    low_close = (df['Low'] - df['Close'].shift()).abs()
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = ranges.max(axis=1)
    atr = true_range.rolling(14).mean()

    multiplier = 0.1 # Reduced from 1.0 for index sensitivity
    upper = adjusted_ma + (multiplier * atr)
    lower = adjusted_ma - (multiplier * atr)

    
    # Signals
    df['ATMS_Pos'] = 0
    pos = 0
    print(f"DEBUG: upper mean: {upper.mean()}, lower mean: {lower.mean()}, price mean: {df['Close'].mean()}")
    for i in range(200, len(df)):
        # Loosened volume confirm for broad index
        vol_confirm = df['Volume'].iloc[i] >= df['Volume'].iloc[i-20:i].mean() * 1.05
        
        # Trend filter (Close > Adjusted MA)
        if pos == 0 and df['Close'].iloc[i] > upper.iloc[i] and vol_confirm:
            pos = 1
        elif pos == 1 and df['Close'].iloc[i] < lower.iloc[i]:
            pos = 0
        df.iloc[i, df.columns.get_loc('ATMS_Pos')] = pos
        
    df['ATMS_Returns'] = df['ATMS_Pos'].shift(1) * df['Close'].pct_change()
    total_return_atms = (1 + df['ATMS_Returns'].fillna(0)).prod() - 1
    avg_yearly_atms = (1 + total_return_atms) ** (1 / total_years) - 1

    results["ATMS Strategy"] = {
        "Total Return": f"{total_return_atms*100:.2f}%",
        "Avg Yearly Return": f"{avg_yearly_atms*100:.2f}%",
        "Raw": avg_yearly_atms
    }

    # --- 4. RSI Mean Reversion (Buy < 30, Sell > 70) ---
    df['RSI_Pos'] = 0
    pos = 0
    for i in range(1, len(df)):
        if rsi.iloc[i] < 30:
            pos = 1
        elif rsi.iloc[i] > 70:
            pos = 0
        df.iloc[i, df.columns.get_loc('RSI_Pos')] = pos
        
    df['RSI_Returns'] = df['RSI_Pos'].shift(1) * df['Close'].pct_change()
    total_return_rsi = (1 + df['RSI_Returns'].fillna(0)).prod() - 1
    avg_yearly_rsi = (1 + total_return_rsi) ** (1 / total_years) - 1

    results["RSI Strategy"] = {
        "Total Return": f"{total_return_rsi*100:.2f}%",
        "Avg Yearly Return": f"{avg_yearly_rsi*100:.2f}%",
        "Raw": avg_yearly_rsi
    }

    return results

if __name__ == "__main__":
    res = run_backtest()
    print("\n" + "="*50)
    print(f"{'STRATEGY':<20} | {'YEARLY RETURN':<15} | {'TOTAL RETURN'}")
    print("-"*50)
    # Sort by Yearly Return
    sorted_res = sorted(res.items(), key=lambda x: x[1]['Raw'], reverse=True)
    for name, data in sorted_res:
        print(f"{name:<20} | {data['Avg Yearly Return']:<15} | {data['Total Return']}")
    print("="*50)
