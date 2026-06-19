#!/usr/bin/env python3
"""
BatesAI — Data CLI

A thin JSON interface over yfinance + the technical helpers so native / web
front-ends can pull chart and screener data without embedding Python logic.

Commands:
  history TICKER [--period 1y]   -> OHLC series + SMA50/SMA200/RSI overlays
  screen   [--fast] [-n N]       -> momentum-ranked list (lightweight)
"""

from __future__ import annotations

import argparse
import json
import sys

import numpy as np
import pandas as pd
import yfinance as yf

import recommendation_engine as eng


def _rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0).rolling(period).mean()
    loss = (-delta.where(delta < 0, 0.0)).rolling(period).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def history(ticker: str, period: str = "1y") -> dict:
    df = yf.download(ticker, period=period, interval="1d",
                     progress=False, timeout=20, auto_adjust=True)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    if df.empty:
        return {"ticker": ticker, "period": period, "bars": []}

    close = df["Close"]
    sma50 = close.rolling(50).mean()
    sma200 = close.rolling(200).mean()
    rsi = _rsi(close)

    # Bollinger Bands (20, 2σ)
    bb_mid = close.rolling(20).mean()
    bb_std = close.rolling(20).std()
    bb_up = bb_mid + 2 * bb_std
    bb_lo = bb_mid - 2 * bb_std

    # MACD (12/26/9)
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    macd_sig = macd.ewm(span=9, adjust=False).mean()
    macd_hist = macd - macd_sig

    bars = []
    for i, (idx, row) in enumerate(df.iterrows()):
        def g(series):
            v = series.iloc[i]
            return None if pd.isna(v) else round(float(v), 4)
        bars.append({
            "date": idx.strftime("%Y-%m-%d"),
            "open": g(df["Open"]), "high": g(df["High"]),
            "low": g(df["Low"]), "close": g(close),
            "volume": int(row["Volume"]) if not pd.isna(row["Volume"]) else 0,
            "sma50": g(sma50), "sma200": g(sma200), "rsi": g(rsi),
            "ema12": g(ema12), "ema26": g(ema26),
            "bbUpper": g(bb_up), "bbLower": g(bb_lo), "bbMid": g(bb_mid),
            "macd": g(macd), "macdSignal": g(macd_sig), "macdHist": g(macd_hist),
        })
    return {"ticker": ticker, "period": period, "bars": bars}


def quotes(tickers: list) -> dict:
    """Latest price + daily change for a set of tickers (for the portfolio view)."""
    out = {}
    for t in tickers:
        try:
            df = yf.download(t, period="5d", interval="1d",
                             progress=False, timeout=12, auto_adjust=True)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            c = df["Close"].dropna()
            if len(c) >= 1:
                price = float(c.iloc[-1])
                chg = float(c.iloc[-1] / c.iloc[-2] - 1) * 100 if len(c) >= 2 else 0.0
                out[t] = {"price": round(price, 2), "change": round(chg, 2)}
        except Exception:
            continue
    return out


def screen(fast: bool, n: int) -> list:
    universe = eng.FAST_UNIVERSE if fast else eng.DEFAULT_UNIVERSE
    out = []
    for t in universe:
        try:
            df = yf.download(t, period="1y", interval="1d",
                             progress=False, timeout=12, auto_adjust=True)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            if df.empty or len(df) < 60:
                continue
            c = df["Close"]
            mom = float(c.iloc[-22] / c.iloc[0] - 1) * 100
            chg = float(c.iloc[-1] / c.iloc[-2] - 1) * 100
            out.append({"ticker": t, "momentum": round(mom, 2),
                        "price": round(float(c.iloc[-1]), 2), "change": round(chg, 2)})
        except Exception:
            continue
    out.sort(key=lambda x: x["momentum"], reverse=True)
    return out[:n]


def main():
    p = argparse.ArgumentParser(description="BatesAI Data CLI")
    sub = p.add_subparsers(dest="cmd")
    h = sub.add_parser("history")
    h.add_argument("ticker")
    h.add_argument("--period", default="1y")
    s = sub.add_parser("screen")
    s.add_argument("--fast", action="store_true")
    s.add_argument("-n", type=int, default=50)
    q = sub.add_parser("quotes")
    q.add_argument("tickers", nargs="+")
    args = p.parse_args()

    if args.cmd == "history":
        print(json.dumps(history(args.ticker.upper(), args.period)))
    elif args.cmd == "screen":
        print(json.dumps(screen(args.fast, args.n)))
    elif args.cmd == "quotes":
        print(json.dumps(quotes([t.upper() for t in args.tickers])))
    else:
        p.print_help(sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
