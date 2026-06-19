#!/usr/bin/env python3
"""
BatesAI — Recommendation Validation Harness

Answers the only question that makes a scoring system credible:
**does a high Recommendation Points score actually predict better forward returns?**

Method (point-in-time, no look-ahead):
  1. Pull multi-year daily history once per ticker.
  2. At each monthly rebalance date T (leaving a forward buffer), slice each
     ticker's data to <= T and compute the *technical* Recommendation score using
     only information available at T.
  3. Record the realized forward return from T to T + horizon.
  4. Aggregate across all (ticker, date) pairs:
       - Information Coefficient (Spearman rank corr of score vs forward return)
       - Quintile spread (avg forward return of top-20% scores minus bottom-20%)
       - Hit rate (share of top-quintile names that beat the cross-sectional median)

Only the technical score is validated here: yfinance does not expose
point-in-time historical fundamentals, so blending those in would leak
look-ahead bias. The technical score is the backtestable core.
"""

from __future__ import annotations

import gc
from datetime import datetime

import numpy as np
import pandas as pd
import yfinance as yf

import recommendation_engine as eng


def _spearman(a, b):
    """Spearman rank correlation without scipy."""
    a = pd.Series(a).rank()
    b = pd.Series(b).rank()
    if a.std() == 0 or b.std() == 0:
        return 0.0
    return float(np.corrcoef(a, b)[0, 1])


def validate(universe=None, period="5y", horizon=63, step=21,
             min_history=220, log=print):
    """Run the walk-forward validation. `horizon`/`step` are in trading days."""
    universe = universe or eng.FAST_UNIVERSE

    # Download all histories once.
    histories = {}
    for i, t in enumerate(universe):
        log(f"Downloading {t} ({i+1}/{len(universe)})…")
        try:
            df = yf.download(t, period=period, interval="1d",
                             progress=False, timeout=20, auto_adjust=True)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            if not df.empty and len(df) > min_history + horizon:
                histories[t] = df["Close"].dropna()
        except Exception as e:  # noqa: BLE001
            log(f"  skip {t}: {e}")
        gc.collect()

    if len(histories) < 5:
        log("Not enough data to validate.")
        return None

    # Common trading calendar = the longest history's index.
    ref = max(histories.values(), key=len)
    idx = ref.index
    # Rebalance points: every `step` days, leaving `horizon` days of forward room.
    points = range(min_history, len(idx) - horizon, step)

    samples = []  # (date, ticker, score, forward_return)
    for p in points:
        date = idx[p]
        cross = []
        for t, close in histories.items():
            window = close[close.index <= date]
            if len(window) < min_history:
                continue
            fwd = close[close.index > date]
            if len(fwd) < horizon:
                continue
            scored = eng.score_ticker(t, pd.DataFrame({"Close": window}))
            if not scored:
                continue
            entry = float(window.iloc[-1])
            future = float(fwd.iloc[horizon - 1])
            fwd_ret = future / entry - 1.0
            comp = scored.get("components", {})
            cross.append({
                "date": date, "ticker": t, "score": scored["score"], "fwd_ret": fwd_ret,
                "momentum": scored["momentum_12_1"], "rsi": scored["rsi"],
                "vol": scored["annual_vol"], "bt": scored["strategy_return"],
                "c_Momentum": comp.get("Momentum"), "c_Trend": comp.get("Trend"),
                "c_Backtest": comp.get("Backtest"), "c_RSI": comp.get("RSI/Entry"),
                "c_MACD": comp.get("MACD"), "c_Risk": comp.get("Risk"),
            })
        if len(cross) >= 5:
            samples.extend(cross)
    log(f"Collected {len(samples)} point-in-time samples across {len(list(points))} dates.")

    df = pd.DataFrame(samples)
    if df.empty:
        return None

    # Overall IC.
    ic = _spearman(df["score"], df["fwd_ret"])

    # Per-date IC, then average (cross-sectional, the standard quant measure).
    per_date_ic = []
    for _, g in df.groupby("date"):
        if len(g) >= 5:
            per_date_ic.append(_spearman(g["score"], g["fwd_ret"]))
    mean_ic = float(np.mean(per_date_ic)) if per_date_ic else 0.0
    ic_hit = float(np.mean([1 if x > 0 else 0 for x in per_date_ic])) if per_date_ic else 0.0

    # Per-component mean cross-sectional IC (which raw factors actually predict?).
    comp_cols = ["momentum", "rsi", "vol", "bt", "c_Momentum", "c_Trend",
                 "c_Backtest", "c_RSI", "c_MACD", "c_Risk"]
    component_ic = {}
    for col in comp_cols:
        if col not in df:
            continue
        ics = []
        for _, g in df.groupby("date"):
            sub = g[[col, "fwd_ret"]].dropna()
            if len(sub) >= 5:
                ics.append(_spearman(sub[col], sub["fwd_ret"]))
        if ics:
            component_ic[col] = round(float(np.mean(ics)), 4)

    # Quintile spread (top 20% score vs bottom 20%), computed per date then averaged.
    top_rets, bot_rets, hit = [], [], []
    for _, g in df.groupby("date"):
        if len(g) < 5:
            continue
        g = g.sort_values("score")
        n = max(1, len(g) // 5)
        bot = g.head(n)["fwd_ret"].mean()
        top = g.tail(n)["fwd_ret"].mean()
        med = g["fwd_ret"].median()
        top_rets.append(top)
        bot_rets.append(bot)
        hit.append((g.tail(n)["fwd_ret"] > med).mean())

    result = {
        "samples": len(df),
        "dates": int(df["date"].nunique()),
        "horizon_days": horizon,
        "overall_ic": round(ic, 4),
        "mean_cross_sectional_ic": round(mean_ic, 4),
        "ic_positive_rate": round(ic_hit, 3),
        "top_quintile_fwd_ret": round(float(np.mean(top_rets)) * 100, 2),
        "bottom_quintile_fwd_ret": round(float(np.mean(bot_rets)) * 100, 2),
        "quintile_spread_pct": round((np.mean(top_rets) - np.mean(bot_rets)) * 100, 2),
        "top_quintile_hit_rate": round(float(np.mean(hit)), 3),
        "component_ic": dict(sorted(component_ic.items(), key=lambda kv: kv[1], reverse=True)),
    }
    return result


def main():
    log = print
    log("=" * 64)
    log("BatesAI — Recommendation Points Validation (point-in-time)")
    log("=" * 64)
    res = validate(log=log)
    if not res:
        log("Validation could not run.")
        return
    log("\n--- RESULTS ---")
    log(f"Samples: {res['samples']} across {res['dates']} monthly dates "
        f"(forward horizon: {res['horizon_days']} trading days ≈ 3 months)")
    log(f"Information Coefficient (overall):        {res['overall_ic']:+.4f}")
    log(f"Mean cross-sectional IC:                  {res['mean_cross_sectional_ic']:+.4f}")
    log(f"  (share of dates with positive IC:       {res['ic_positive_rate']:.0%})")
    log(f"Top-quintile avg forward return:          {res['top_quintile_fwd_ret']:+.2f}%")
    log(f"Bottom-quintile avg forward return:       {res['bottom_quintile_fwd_ret']:+.2f}%")
    log(f"Long-top / short-bottom spread:           {res['quintile_spread_pct']:+.2f}%")
    log(f"Top-quintile hit rate (beat median):      {res['top_quintile_hit_rate']:.0%}")
    log("\n--- PER-FACTOR mean cross-sectional IC (which factors predict?) ---")
    for k, v in res["component_ic"].items():
        log(f"  {k:<14} {v:+.4f}")
    log("\nInterpretation: IC > 0 and a positive quintile spread mean higher")
    log("Recommendation Points have historically preceded higher forward returns.")
    log("An IC of 0.03-0.06 is already meaningful in cross-sectional equity ranking.")


if __name__ == "__main__":
    main()
