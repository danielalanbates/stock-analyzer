#!/usr/bin/env python3
"""
BatesAI — Recommendation Engine
Computes "Recommendation Points" (0-100) for a universe of tickers and returns
the top ranked choices.

Scoring philosophy
------------------
100  = the best deal imaginable (strong uptrend, healthy pullback entry,
       confirmed momentum, low risk, and a strategy that historically worked).
  0  = guaranteed to tank (broken trend, falling knife, negative momentum,
       high risk, and a strategy that historically lost money).

The score is a transparent weighted blend of six sub-scores (max points shown):

    Momentum        25   12-1 month total return (skips the most recent month)
    Trend           20   price vs SMA50/SMA200 structure + golden/death cross
    Backtest        20   walk-forward edge of a SMA20>SMA50 long/flat strategy
    RSI / Entry     15   rewards healthy momentum & oversold-in-uptrend dips
    MACD            10   histogram sign & slope (momentum confirmation)
    Risk (Vol/DD)   10   lower annualized volatility & shallower drawdown

Everything is local-first: data via yfinance, cached on disk for an hour.
"""

from __future__ import annotations

import math
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

# Default universe: S&P 100-ish large caps + a few popular ETFs.
DEFAULT_UNIVERSE = [
    "AAPL", "MSFT", "AMZN", "NVDA", "GOOGL", "META", "BRK-B", "TSLA", "UNH", "LLY",
    "V", "JPM", "XOM", "MA", "AVGO", "HD", "PG", "JNJ", "COST", "ADBE",
    "ABBV", "MRK", "CRM", "BAC", "CVX", "PEP", "WMT", "KO", "TMO", "NFLX",
    "CSCO", "ACN", "ABT", "LIN", "MCD", "DIS", "ORCL", "INTC", "WFC", "INTU",
    "AMD", "VZ", "PM", "IBM", "CMCSA", "TXN", "QCOM", "UNP", "AMGN", "GE",
    "CAT", "SPGI", "LOW", "HON", "ISRG", "AMAT", "BKNG", "AXP", "RTX", "TJX",
    "ADP", "SYK", "GILD", "VRTX", "C", "LRCX", "ADI", "ELV", "ETN", "MU",
    "LMT", "BSX", "REGN", "MMC", "PANW", "CB", "PGR", "DE", "BMY", "CI",
    "BA", "MDT", "SCHW", "CDNS", "SNPS", "ICE", "WM", "ZTS", "KLAC", "SO",
    "EOG", "SHW", "CL", "TGT", "MO", "SPY", "QQQ", "DIA", "IWM", "SMH",
]


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def backtest_sma_strategy(close: pd.Series) -> dict:
    """Walk-forward backtest of a long/flat SMA20>SMA50 strategy.

    Returns total strategy return, buy & hold return, and annualized Sharpe.
    The position for day t is decided by the crossover state at day t-1, so
    there is no look-ahead bias.
    """
    sma_fast = close.rolling(20).mean()
    sma_slow = close.rolling(50).mean()
    position = (sma_fast > sma_slow).astype(float).shift(1).fillna(0.0)

    daily_ret = close.pct_change().fillna(0.0)
    strat_ret = position * daily_ret

    total = float((1.0 + strat_ret).prod() - 1.0)
    hold = float((1.0 + daily_ret).prod() - 1.0)
    std = float(strat_ret.std())
    sharpe = float(strat_ret.mean() / std * math.sqrt(252)) if std > 0 else 0.0
    return {"strategy_return": total, "hold_return": hold, "sharpe": sharpe}


def score_ticker(ticker: str, df: pd.DataFrame) -> dict | None:
    """Compute Recommendation Points (0-100) for one ticker.

    `df` must contain a 'Close' column with >= ~200 daily rows. Returns None if
    there is not enough data to score reliably.
    """
    if df is None or df.empty or "Close" not in df or len(df) < 160:
        return None

    close = df["Close"].dropna()
    if len(close) < 160:
        return None

    price = float(close.iloc[-1])

    # --- Momentum (25): 12-1 month total return, squashed by tanh ---
    lookback = min(252, len(close) - 1)
    skip = 21  # skip most recent month (classic 12-1 momentum)
    start = close.iloc[-lookback]
    recent = close.iloc[-skip]
    mom_12_1 = float(recent / start - 1.0) if start > 0 else 0.0
    momentum_score = _clamp(0.5 + math.tanh(mom_12_1 * 2.0) / 2.0) * 25.0

    # --- Trend (20): price vs SMA50/SMA200 + cross state ---
    sma50 = float(close.rolling(50).mean().iloc[-1])
    sma200 = float(close.rolling(200).mean().iloc[-1]) if len(close) >= 200 else sma50
    t = 0.0
    t += 0.35 if price > sma50 else 0.0
    t += 0.35 if price > sma200 else 0.0
    t += 0.30 if sma50 > sma200 else 0.0       # golden-cross structure
    trend_score = t * 20.0

    # --- Backtest edge (20) ---
    bt = backtest_sma_strategy(close)
    edge = bt["strategy_return"] - bt["hold_return"]
    bt_component = (
        0.45 * _clamp(0.5 + math.tanh(bt["sharpe"]) / 2.0)        # risk-adj quality
        + 0.35 * _clamp(0.5 + math.tanh(bt["strategy_return"] * 3) / 2.0)  # profitable
        + 0.20 * _clamp(0.5 + math.tanh(edge * 5) / 2.0)          # beats buy & hold
    )
    backtest_score = bt_component * 20.0

    # --- RSI / entry quality (15) ---
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0.0)).rolling(14).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi = float(100 - (100 / (1 + rs.iloc[-1]))) if pd.notna(rs.iloc[-1]) else 50.0
    uptrend = price > sma200
    if uptrend and rsi < 35:
        rsi_q = 1.0                       # healthy pullback in an uptrend = a deal
    elif rsi > 78:
        rsi_q = 0.15                      # blow-off / overbought
    else:
        rsi_q = _clamp(1.0 - abs(rsi - 58) / 45.0)  # peak reward ~58
    rsi_score = rsi_q * 15.0

    # --- MACD (10): histogram sign & slope ---
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd_line = ema12 - ema26
    signal_line = macd_line.ewm(span=9, adjust=False).mean()
    hist = macd_line - signal_line
    hist_now = float(hist.iloc[-1])
    hist_prev = float(hist.iloc[-5]) if len(hist) >= 5 else hist_now
    norm = float(close.iloc[-1]) or 1.0
    macd_q = 0.6 * (1.0 if hist_now > 0 else 0.0) + 0.4 * (1.0 if hist_now > hist_prev else 0.0)
    macd_score = macd_q * 10.0

    # --- Risk (10): annualized volatility + max drawdown over the year ---
    rets = close.pct_change().dropna()
    vol = float(rets.tail(63).std() * math.sqrt(252)) if len(rets) >= 63 else 0.5
    roll_max = close.cummax()
    max_dd = float(((close - roll_max) / roll_max).min())  # negative
    vol_q = _clamp(1.0 - (vol - 0.12) / 0.55)        # ~12% vol great, ~67% awful
    dd_q = _clamp(1.0 + max_dd / 0.6)                # -60% dd -> 0
    risk_score = (0.6 * vol_q + 0.4 * dd_q) * 10.0

    total_score = (
        momentum_score + trend_score + backtest_score
        + rsi_score + macd_score + risk_score
    )
    total_score = round(_clamp(total_score, 0.0, 100.0), 1)

    # Human-readable primary drivers (top contributing factors)
    factors = {
        "Momentum": momentum_score, "Trend": trend_score, "Backtest": backtest_score,
        "RSI/Entry": rsi_score, "MACD": macd_score, "Risk": risk_score,
    }
    top = sorted(factors.items(), key=lambda kv: kv[1], reverse=True)[:2]
    drivers = ", ".join(name for name, _ in top)

    daily_chg = float(close.iloc[-1] / close.iloc[-2] - 1.0) * 100 if len(close) >= 2 else 0.0

    return {
        "ticker": ticker,
        "score": total_score,
        "price": price,
        "daily_change": daily_chg,
        "momentum_12_1": round(mom_12_1 * 100, 1),
        "rsi": round(rsi, 1),
        "annual_vol": round(vol * 100, 1),
        "max_drawdown": round(max_dd * 100, 1),
        "strategy_return": round(bt["strategy_return"] * 100, 1),
        "drivers": drivers,
        "components": {k: round(v, 1) for k, v in factors.items()},
    }


def rank_recommendations(universe=None, top_n=10, period="2y",
                         cache_dir=None, log=lambda m: None):
    """Score every ticker in `universe`, return the top `top_n` by score.

    `log` is an optional callback for progress messages.
    """
    universe = universe or DEFAULT_UNIVERSE
    cache_path = Path(cache_dir) if cache_dir else None
    if cache_path:
        cache_path.mkdir(exist_ok=True)

    results = []
    total = len(universe)
    for i, t in enumerate(universe):
        log(f"Scoring {t} ({i + 1}/{total})...")
        try:
            df = None
            cfile = cache_path / f"rec_{t}_{period}.csv" if cache_path else None
            if cfile and cfile.exists():
                age = datetime.now().timestamp() - cfile.stat().st_mtime
                if age < 3600:
                    df = pd.read_csv(cfile, index_col=0, parse_dates=True)
            if df is None:
                df = yf.download(t, period=period, interval="1d",
                                 progress=False, timeout=15, auto_adjust=True)
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)
                if cfile is not None and not df.empty:
                    df.to_csv(cfile)
            scored = score_ticker(t, df)
            if scored:
                results.append(scored)
        except Exception as e:  # noqa: BLE001 - never let one ticker kill the run
            log(f"  skip {t}: {e}")

    results.sort(key=lambda r: r["score"], reverse=True)
    return results[:top_n]


if __name__ == "__main__":
    top = rank_recommendations(top_n=10, log=print)
    print("\n=== TOP 10 RECOMMENDATIONS ===")
    print(f"{'Rank':<5}{'Ticker':<8}{'Points':<8}{'Price':<10}{'12-1 Mom':<10}{'Drivers'}")
    for i, r in enumerate(top, 1):
        print(f"{i:<5}{r['ticker']:<8}{r['score']:<8}${r['price']:<9.2f}"
              f"{r['momentum_12_1']:<10}{r['drivers']}")
