#!/usr/bin/env python3
"""
BatesAI — Fundamentals & Valuation layer

Fetches fundamental metrics (valuation, quality, growth, balance-sheet health,
and analyst view) and condenses them into a 0-1 fundamental score with a
human-readable breakdown. Local-first: results cached on disk for 12 hours.

This is the data foundation the Recommendation Engine blends with its technical
score so rankings reflect *what a company is worth*, not just price action.
"""

from __future__ import annotations

import json
import math
import time
from pathlib import Path

import yfinance as yf


def _clamp(x, lo=0.0, hi=1.0):
    return max(lo, min(hi, x))


def get_fundamentals(ticker: str, cache_dir=None, max_age=43200) -> dict:
    """Return a dict of raw fundamental fields for `ticker` (cached 12h)."""
    cache_path = Path(cache_dir) / f"fund_{ticker}.json" if cache_dir else None
    if cache_path and cache_path.exists():
        if time.time() - cache_path.stat().st_mtime < max_age:
            try:
                return json.loads(cache_path.read_text())
            except Exception:
                pass

    info = {}
    try:
        info = yf.Ticker(ticker).info or {}
    except Exception:
        info = {}

    fields = (
        "trailingPE", "forwardPE", "priceToBook", "pegRatio", "profitMargins",
        "returnOnEquity", "revenueGrowth", "earningsGrowth", "debtToEquity",
        "freeCashflow", "marketCap", "dividendYield", "recommendationKey",
        "targetMeanPrice", "currentPrice", "sector",
    )
    data = {k: info.get(k) for k in fields}
    if cache_path is not None:
        try:
            cache_path.write_text(json.dumps(data))
        except Exception:
            pass
    return data


def score_fundamentals(data: dict) -> dict:
    """Condense raw fundamentals into a 0-1 score with sub-scores.

    Sub-weights (relative): value 0.25, quality 0.25, growth 0.20,
    health 0.15, analyst 0.15. Missing inputs fall back to a neutral 0.5 so a
    data gap neither rewards nor punishes a name disproportionately.
    """
    def num(x):
        try:
            return float(x)
        except (TypeError, ValueError):
            return None

    # --- Value (cheaper = better, but reject negative/absurd multiples) ---
    pe = num(data.get("forwardPE")) or num(data.get("trailingPE"))
    pb = num(data.get("priceToBook"))
    peg = num(data.get("pegRatio"))
    value_parts = []
    if pe is not None and pe > 0:
        value_parts.append(_clamp(1.0 - (pe - 10) / 40))      # PE 10 great, 50 poor
    if pb is not None and pb > 0:
        value_parts.append(_clamp(1.0 - (pb - 1) / 9))        # PB 1 great, 10 poor
    if peg is not None and peg > 0:
        value_parts.append(_clamp(1.0 - (peg - 1) / 2))       # PEG 1 great, 3 poor
    value = sum(value_parts) / len(value_parts) if value_parts else 0.5

    # --- Quality (profitability) ---
    roe = num(data.get("returnOnEquity"))
    margin = num(data.get("profitMargins"))
    fcf = num(data.get("freeCashflow"))
    quality_parts = []
    if roe is not None:
        quality_parts.append(_clamp(roe / 0.30))              # 30% ROE -> full
    if margin is not None:
        quality_parts.append(_clamp(margin / 0.25))           # 25% margin -> full
    if fcf is not None:
        quality_parts.append(1.0 if fcf > 0 else 0.0)
    quality = sum(quality_parts) / len(quality_parts) if quality_parts else 0.5

    # --- Growth ---
    rev_g = num(data.get("revenueGrowth"))
    eps_g = num(data.get("earningsGrowth"))
    growth_parts = []
    if rev_g is not None:
        growth_parts.append(_clamp(0.5 + math.tanh(rev_g * 3) / 2))
    if eps_g is not None:
        growth_parts.append(_clamp(0.5 + math.tanh(eps_g * 3) / 2))
    growth = sum(growth_parts) / len(growth_parts) if growth_parts else 0.5

    # --- Balance-sheet health ---
    de = num(data.get("debtToEquity"))
    health = _clamp(1.0 - de / 200) if de is not None else 0.5  # D/E 0 great, 200 poor

    # --- Analyst view ---
    rec_map = {"strong_buy": 1.0, "buy": 0.8, "hold": 0.5, "underperform": 0.25, "sell": 0.0}
    analyst_parts = []
    rk = data.get("recommendationKey")
    if rk in rec_map:
        analyst_parts.append(rec_map[rk])
    tgt = num(data.get("targetMeanPrice"))
    cur = num(data.get("currentPrice"))
    if tgt and cur and cur > 0:
        upside = tgt / cur - 1.0
        analyst_parts.append(_clamp(0.5 + math.tanh(upside * 3) / 2))
    analyst = sum(analyst_parts) / len(analyst_parts) if analyst_parts else 0.5

    score = (0.25 * value + 0.25 * quality + 0.20 * growth
             + 0.15 * health + 0.15 * analyst)

    return {
        "score": round(_clamp(score), 3),
        "value": round(value, 3),
        "quality": round(quality, 3),
        "growth": round(growth, 3),
        "health": round(health, 3),
        "analyst": round(analyst, 3),
        "pe": round(pe, 1) if pe else None,
        "peg": peg,
        "roe": round(roe * 100, 1) if roe is not None else None,
        "rev_growth": round(rev_g * 100, 1) if rev_g is not None else None,
        "target_upside": round((tgt / cur - 1) * 100, 1) if (tgt and cur) else None,
        "sector": data.get("sector"),
        "recommendation": rk,
    }


def fundamentals_score(ticker: str, cache_dir=None) -> dict:
    """Convenience: fetch + score in one call."""
    return score_fundamentals(get_fundamentals(ticker, cache_dir=cache_dir))


if __name__ == "__main__":
    import sys
    for t in (sys.argv[1:] or ["AAPL", "MSFT", "KO"]):
        s = fundamentals_score(t)
        print(f"{t:6} score={s['score']:.2f}  value={s['value']:.2f} "
              f"quality={s['quality']:.2f} growth={s['growth']:.2f} "
              f"health={s['health']:.2f} analyst={s['analyst']:.2f}  "
              f"PE={s['pe']} ROE={s['roe']} upside={s['target_upside']}")
