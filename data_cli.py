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
import ssl
import sys
import urllib.request

import numpy as np
import pandas as pd
import yfinance as yf

import recommendation_engine as eng

# Use certifi's CA bundle when available so HTTPS works inside a frozen
# (PyInstaller) app, where the system cert path isn't found.
try:
    import certifi
    _SSL_CTX = ssl.create_default_context(cafile=certifi.where())
except Exception:  # pragma: no cover
    _SSL_CTX = ssl.create_default_context()


def _yahoo_chart(symbol: str, rng: str, interval: str) -> dict:
    """Hit Yahoo's chart endpoint directly (stdlib, no key).

    More reliable than yfinance.download() for intraday in some environments,
    which is why intraday/real-time quotes go through here.
    """
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
           f"?range={rng}&interval={interval}")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15, context=_SSL_CTX) as resp:
        data = json.load(resp)
    return data["chart"]["result"][0]


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


def intraday(ticker: str, interval: str = "1m") -> dict:
    """Today's intraday bars (near-real-time via Yahoo's chart endpoint, free)."""
    rng = "1d" if interval in ("1m", "2m", "5m") else "5d"
    try:
        r = _yahoo_chart(ticker, rng, interval)
    except Exception:
        return {"ticker": ticker, "interval": interval, "bars": []}
    ts = r.get("timestamp", []) or []
    q = r["indicators"]["quote"][0]
    closes, vols = q.get("close", []), q.get("volume", [])
    import datetime as _dt
    bars = []
    for i, t in enumerate(ts):
        c = closes[i] if i < len(closes) else None
        if c is None:
            continue
        bars.append({
            "time": _dt.datetime.fromtimestamp(t).strftime("%Y-%m-%d %H:%M"),
            "close": round(float(c), 4),
            "volume": int(vols[i]) if i < len(vols) and vols[i] else 0,
        })
    last = bars[-1]["close"] if bars else None
    first = bars[0]["close"] if bars else None
    meta = r.get("meta", {})
    # Prefer Yahoo's official previous close for the % change anchor.
    prev = meta.get("chartPreviousClose") or first
    return {
        "ticker": ticker, "interval": interval, "bars": bars,
        "last": round(last, 2) if last else None,
        "open": round(first, 2) if first else None,
        "change": round((last / prev - 1) * 100, 2) if (last and prev) else 0.0,
    }


def info(ticker: str) -> dict:
    """Comprehensive financials for one ticker (equity / ETF / crypto).

    Returns every common field Yahoo exposes; missing fields come back null so
    the UI can show "—" for instruments that don't have them (ETFs, crypto).
    """
    try:
        raw = yf.Ticker(ticker).info or {}
    except Exception:
        raw = {}

    def g(*keys):
        for k in keys:
            v = raw.get(k)
            if v not in (None, ""):
                return v
        return None

    fmt_pct = lambda v: round(v * 100, 2) if isinstance(v, (int, float)) else None
    return {
        "ticker": ticker,
        "name": g("longName", "shortName"),
        "type": g("quoteType"),
        "sector": g("sector"),
        "industry": g("industry"),
        "currency": g("currency"),
        "exchange": g("fullExchangeName", "exchange"),
        # Price / range
        "price": g("currentPrice", "regularMarketPrice", "previousClose"),
        "previousClose": g("previousClose", "regularMarketPreviousClose"),
        "open": g("open", "regularMarketOpen"),
        "dayLow": g("dayLow", "regularMarketDayLow"),
        "dayHigh": g("dayHigh", "regularMarketDayHigh"),
        "fiftyTwoWeekLow": g("fiftyTwoWeekLow"),
        "fiftyTwoWeekHigh": g("fiftyTwoWeekHigh"),
        # Size / volume
        "marketCap": g("marketCap"),
        "sharesOutstanding": g("sharesOutstanding"),
        "volume": g("volume", "regularMarketVolume"),
        "avgVolume": g("averageVolume", "averageDailyVolume10Day"),
        # Valuation
        "trailingPE": g("trailingPE"),
        "forwardPE": g("forwardPE"),
        "pegRatio": g("pegRatio", "trailingPegRatio"),
        "priceToBook": g("priceToBook"),
        "eps": g("trailingEps", "epsTrailingTwelveMonths"),
        "forwardEps": g("forwardEps"),
        # Profitability / growth
        "profitMargin": fmt_pct(g("profitMargins")),
        "roe": fmt_pct(g("returnOnEquity")),
        "revenueGrowth": fmt_pct(g("revenueGrowth")),
        "totalRevenue": g("totalRevenue"),
        "freeCashflow": g("freeCashflow"),
        "debtToEquity": g("debtToEquity"),
        # Income / risk
        "dividendYield": g("dividendYield"),
        "beta": g("beta"),
        # Analyst
        "targetMeanPrice": g("targetMeanPrice"),
        "recommendation": g("recommendationKey"),
        "numAnalysts": g("numberOfAnalystOpinions"),
        "summary": g("longBusinessSummary"),
    }


def quotes(tickers: list) -> dict:
    """Near-real-time price + intraday change via Yahoo's chart endpoint (free)."""
    out = {}
    for t in tickers:
        try:
            r = _yahoo_chart(t, "1d", "1m")
            meta = r.get("meta", {})
            price = meta.get("regularMarketPrice")
            prev = meta.get("chartPreviousClose") or meta.get("previousClose")
            if price is None:
                closes = [c for c in r["indicators"]["quote"][0].get("close", []) if c is not None]
                price = closes[-1] if closes else None
            if price is not None:
                chg = ((price / prev - 1) * 100) if prev else 0.0
                out[t] = {"price": round(float(price), 2), "change": round(float(chg), 2)}
        except Exception:
            # Fall back to daily close via yfinance if the chart endpoint fails.
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
    intr = sub.add_parser("intraday")
    intr.add_argument("ticker")
    intr.add_argument("--interval", default="1m")
    inf = sub.add_parser("info")
    inf.add_argument("ticker")
    args = p.parse_args()

    if args.cmd == "history":
        print(json.dumps(history(args.ticker.upper(), args.period)))
    elif args.cmd == "screen":
        print(json.dumps(screen(args.fast, args.n)))
    elif args.cmd == "quotes":
        print(json.dumps(quotes([t.upper() for t in args.tickers])))
    elif args.cmd == "intraday":
        print(json.dumps(intraday(args.ticker.upper(), args.interval)))
    elif args.cmd == "info":
        print(json.dumps(info(args.ticker.upper())))
    else:
        p.print_help(sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
