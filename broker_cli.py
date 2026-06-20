#!/usr/bin/env python3
"""
BatesAI — Brokerage / real-time adapter (Alpaca)

Provides real-time quotes, account summary, and live positions from Alpaca.
One free Alpaca paper-trading account unlocks BOTH real-time market data and
brokerage sync, which is why it backs the app's real-time + portfolio features.

Credentials (never hard-coded) are read, in order, from:
  1. env vars APCA_API_KEY_ID / APCA_API_SECRET_KEY
  2. ~/Library/Application Support/StockAnalyzer/broker.json
       {"key_id": "...", "secret": "...", "paper": true}

Without credentials every command returns {"configured": false, ...} so the UI
can show a "Connect Alpaca" state instead of failing. Uses only the Python
standard library so it bundles into the app with no extra dependencies.

Commands (all emit JSON):
  status                      -> {configured, paper, ok, error?}
  account                     -> cash, equity, buying_power, ...
  positions                   -> [{ticker, qty, avg_cost, price, value, pnl, pnl_pct}]
  quotes  T1 T2 ...           -> {T: {price, change}}  (real-time)
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path


def _config_path() -> Path:
    return (Path.home() / "Library" / "Application Support" / "StockAnalyzer"
            / "broker.json")


def _credentials():
    key = os.environ.get("APCA_API_KEY_ID")
    secret = os.environ.get("APCA_API_SECRET_KEY")
    paper = os.environ.get("APCA_PAPER", "1") not in ("0", "false", "False")
    if key and secret:
        return key, secret, paper
    p = _config_path()
    if p.exists():
        try:
            cfg = json.loads(p.read_text())
            if cfg.get("key_id") and cfg.get("secret"):
                return cfg["key_id"], cfg["secret"], bool(cfg.get("paper", True))
        except Exception:
            pass
    return None, None, True


def _request(url: str, key: str, secret: str) -> dict | list:
    req = urllib.request.Request(url, headers={
        "APCA-API-KEY-ID": key,
        "APCA-API-SECRET-KEY": secret,
        "Accept": "application/json",
    })
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode())


def _trading_base(paper: bool) -> str:
    return "https://paper-api.alpaca.markets" if paper else "https://api.alpaca.markets"


def status() -> dict:
    key, secret, paper = _credentials()
    if not key:
        return {"configured": False, "paper": paper,
                "message": "No Alpaca credentials. Add them to connect real-time data & brokerage."}
    try:
        acct = _request(f"{_trading_base(paper)}/v2/account", key, secret)
        return {"configured": True, "paper": paper, "ok": True,
                "account_number": acct.get("account_number"),
                "status": acct.get("status")}
    except urllib.error.HTTPError as e:
        return {"configured": True, "paper": paper, "ok": False,
                "error": f"HTTP {e.code}: check your keys / paper flag"}
    except Exception as e:  # noqa: BLE001
        return {"configured": True, "paper": paper, "ok": False, "error": str(e)}


def account() -> dict:
    key, secret, paper = _credentials()
    if not key:
        return {"configured": False}
    a = _request(f"{_trading_base(paper)}/v2/account", key, secret)
    return {
        "configured": True,
        "cash": float(a.get("cash", 0)),
        "equity": float(a.get("equity", 0)),
        "buying_power": float(a.get("buying_power", 0)),
        "long_market_value": float(a.get("long_market_value", 0)),
        "currency": a.get("currency", "USD"),
    }


def positions() -> dict:
    key, secret, paper = _credentials()
    if not key:
        return {"configured": False, "positions": []}
    rows = _request(f"{_trading_base(paper)}/v2/positions", key, secret)
    out = []
    for p in rows:
        qty = float(p.get("qty", 0))
        avg = float(p.get("avg_entry_price", 0))
        price = float(p.get("current_price", 0) or 0)
        out.append({
            "ticker": p.get("symbol"),
            "qty": qty,
            "avg_cost": avg,
            "price": price,
            "value": float(p.get("market_value", 0) or 0),
            "pnl": float(p.get("unrealized_pl", 0) or 0),
            "pnl_pct": float(p.get("unrealized_plpc", 0) or 0) * 100,
        })
    return {"configured": True, "positions": out}


def quotes(tickers: list) -> dict:
    """Real-time latest trade prices + intraday change via Alpaca market data."""
    key, secret, _ = _credentials()
    if not key:
        return {"configured": False, "quotes": {}}
    syms = ",".join(t.upper() for t in tickers)
    base = "https://data.alpaca.markets/v2/stocks"
    trades = _request(f"{base}/trades/latest?symbols={syms}", key, secret).get("trades", {})
    bars = _request(f"{base}/bars/latest?symbols={syms}", key, secret).get("bars", {})
    out = {}
    for t in (x.upper() for x in tickers):
        price = trades.get(t, {}).get("p")
        openp = bars.get(t, {}).get("o")
        if price is not None:
            chg = ((price / openp - 1) * 100) if openp else 0.0
            out[t] = {"price": round(float(price), 2), "change": round(float(chg), 2)}
    return {"configured": True, "quotes": out}


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    try:
        if cmd == "status":
            print(json.dumps(status()))
        elif cmd == "account":
            print(json.dumps(account()))
        elif cmd == "positions":
            print(json.dumps(positions()))
        elif cmd == "quotes":
            print(json.dumps(quotes(sys.argv[2:])))
        else:
            print(json.dumps({"error": f"unknown command: {cmd}"}))
            sys.exit(2)
    except urllib.error.HTTPError as e:
        print(json.dumps({"configured": True, "ok": False,
                          "error": f"HTTP {e.code}"}))
    except Exception as e:  # noqa: BLE001
        print(json.dumps({"configured": True, "ok": False, "error": str(e)}))


if __name__ == "__main__":
    main()
