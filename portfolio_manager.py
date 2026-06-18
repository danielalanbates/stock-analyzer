#!/usr/bin/env python3
"""
BatesAI — AI Portfolio Manager
Balances portfolio based on input, market conditions, and signals.
Local-first, privacy-preserving, no external data storage.
"""

import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

# Try to import yfinance; if not available, install it
try:
    import yfinance as yf
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "yfinance", "-q"])
    import yf

import numpy as np
import pandas as pd


class PortfolioManager:
    """AI-driven portfolio balancer with market signal integration."""

    def __init__(self, portfolio_path: str = "portfolio.json"):
        self.portfolio_path = Path(portfolio_path)
        self.portfolio = self._load_portfolio()
        self.cache_dir = self.portfolio_path.parent / "cache"
        self.cache_dir.mkdir(exist_ok=True)

    def _load_portfolio(self) -> dict:
        """Load portfolio from JSON file or create default."""
        if self.portfolio_path.exists():
            with open(self.portfolio_path) as f:
                return json.load(f)
        return {
            "holdings": {},
            "cash": 10000.0,
            "target_allocation": {},
            "risk_tolerance": 0.5,
            "rebalance_threshold": 0.05,
            "last_updated": None,
        }

    def save_portfolio(self):
        """Save current portfolio state."""
        self.portfolio["last_updated"] = datetime.now().isoformat()
        with open(self.portfolio_path, "w") as f:
            json.dump(self.portfolio, f, indent=2)

    def add_holding(self, ticker: str, shares: float, avg_cost: float = None):
        """Add or update a holding."""
        if avg_cost is None:
            current = self.get_current_price(ticker)
            avg_cost = current
        self.portfolio["holdings"][ticker] = {
            "shares": shares,
            "avg_cost": avg_cost,
            "added": datetime.now().isoformat(),
        }
        self.save_portfolio()

    def set_target_allocation(self, allocation: dict):
        """Set target allocation percentages (must sum to 1.0)."""
        total = sum(allocation.values())
        if abs(total - 1.0) > 0.01:
            print(f"Warning: Allocation sums to {total:.2f}, normalizing to 1.0")
            allocation = {k: v / total for k, v in allocation.items()}
        self.portfolio["target_allocation"] = allocation
        self.save_portfolio()

    def set_risk_tolerance(self, risk: float):
        """Set risk tolerance (0.0 = conservative, 1.0 = aggressive)."""
        self.portfolio["risk_tolerance"] = max(0.0, min(1.0, risk))
        self.save_portfolio()

    def get_current_price(self, ticker: str) -> float:
        """Fetch current price for a ticker."""
        try:
            ticker_obj = yf.Ticker(ticker)
            hist = ticker_obj.history(period="1d")
            if hist.empty:
                print(f"Warning: Could not fetch price for {ticker}")
                return 0.0
            return float(hist["Close"].iloc[-1])
        except Exception as e:
            print(f"Error fetching {ticker}: {e}")
            return 0.0

    def get_historical_data(self, ticker: str, period: str = "6mo") -> pd.DataFrame:
        """Fetch historical data with caching."""
        cache_file = self.cache_dir / f"{ticker}_{period}.csv"
        if cache_file.exists():
            age = datetime.now().timestamp() - cache_file.stat().st_mtime
            if age < 3600:  # Cache for 1 hour
                return pd.read_csv(cache_file, index_col=0, parse_dates=True)

        try:
            ticker_obj = yf.Ticker(ticker)
            df = ticker_obj.history(period=period)
            df.to_csv(cache_file)
            return df
        except Exception as e:
            print(f"Error fetching history for {ticker}: {e}")
            return pd.DataFrame()

    def calculate_rsi(self, prices: pd.Series, period: int = 14) -> float:
        """Calculate RSI (Relative Strength Index)."""
        delta = prices.diff()
        gain = delta.where(delta > 0, 0.0).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0.0)).rolling(window=period).mean()
        rs = gain / loss
        return float(100 - (100 / (1 + rs.iloc[-1])))

    def calculate_macd(self, prices: pd.Series) -> dict:
        """Calculate MACD signal."""
        ema12 = prices.ewm(span=12, adjust=False).mean()
        ema26 = prices.ewm(span=26, adjust=False).mean()
        macd_line = ema12 - ema26
        signal_line = macd_line.ewm(span=9, adjust=False).mean()
        histogram = macd_line - signal_line
        return {
            "macd": float(macd_line.iloc[-1]),
            "signal": float(signal_line.iloc[-1]),
            "histogram": float(histogram.iloc[-1]),
        }

    def calculate_volatility(self, prices: pd.Series, period: int = 20) -> float:
        """Calculate annualized volatility."""
        returns = prices.pct_change().dropna()
        return float(returns.rolling(window=period).std().iloc[-1] * np.sqrt(252))

    def analyze_signals(self, ticker: str) -> dict:
        """Analyze market signals for a ticker."""
        df = self.get_historical_data(ticker)
        if df.empty:
            return {"error": "No data available"}

        close = df["Close"]
        rsi = self.calculate_rsi(close)
        macd = self.calculate_macd(close)
        vol = self.calculate_volatility(close)

        # Simple moving averages
        sma_50 = float(close.rolling(window=50).mean().iloc[-1]) if len(close) >= 50 else None
        sma_200 = float(close.rolling(window=200).mean().iloc[-1]) if len(close) >= 200 else None
        current_price = float(close.iloc[-1])

        # Generate signals
        signals = []
        if rsi < 30:
            signals.append("OVERSOLD_BUY")
        elif rsi > 70:
            signals.append("OVERBOUGHT_SELL")

        if sma_50 and sma_200:
            if sma_50 > sma_200:
                signals.append("GOLDEN_CROSS_BULLISH")
            else:
                signals.append("DEATH_CROSS_BEARISH")

        if macd["histogram"] > 0:
            signals.append("MACD_BULLISH")
        else:
            signals.append("MACD_BEARISH")

        return {
            "ticker": ticker,
            "current_price": current_price,
            "rsi": round(rsi, 2),
            "macd": {k: round(v, 4) for k, v in macd.items()},
            "volatility": round(vol, 4),
            "sma_50": round(sma_50, 2) if sma_50 else None,
            "sma_200": round(sma_200, 2) if sma_200 else None,
            "signals": signals,
            "timestamp": datetime.now().isoformat(),
        }

    def calculate_portfolio_value(self) -> dict:
        """Calculate current portfolio value and allocation."""
        holdings_value = 0.0
        allocation = {}

        for ticker, data in self.portfolio["holdings"].items():
            price = self.get_current_price(ticker)
            value = price * data["shares"]
            holdings_value += value
            allocation[ticker] = {
                "shares": data["shares"],
                "avg_cost": data["avg_cost"],
                "current_price": price,
                "value": round(value, 2),
                "pnl": round(value - (data["avg_cost"] * data["shares"]), 2),
                "pnl_pct": round((value / (data["avg_cost"] * data["shares"]) - 1) * 100, 2) if data["avg_cost"] > 0 else 0,
            }

        total_value = holdings_value + self.portfolio["cash"]
        for ticker in allocation:
            allocation[ticker]["weight"] = round(allocation[ticker]["value"] / total_value * 100, 2) if total_value > 0 else 0

        return {
            "holdings": allocation,
            "cash": self.portfolio["cash"],
            "total_value": round(total_value, 2),
            "timestamp": datetime.now().isoformat(),
        }

    def generate_rebalance_recommendations(self) -> list:
        """Generate AI-driven rebalance recommendations."""
        current = self.calculate_portfolio_value()
        target = self.portfolio["target_allocation"]
        threshold = self.portfolio["rebalance_threshold"]
        risk = self.portfolio["risk_tolerance"]
        total = current["total_value"]

        if not target:
            return [{"action": "SET_TARGET_ALLOCATION", "message": "No target allocation set. Run set_target_allocation() first."}]

        recommendations = []

        for ticker, target_pct in target.items():
            current_weight = current["holdings"].get(ticker, {}).get("weight", 0) / 100
            deviation = current_weight - target_pct

            # Analyze signals
            signals = self.analyze_signals(ticker)
            signal_strength = 0
            if "signals" in signals:
                bullish = sum(1 for s in signals["signals"] if "BULLISH" in s or "BUY" in s)
                bearish = sum(1 for s in signals["signals"] if "BEARISH" in s or "SELL" in s)
                signal_strength = bullish - bearish

            # Adjust recommendation based on signals and risk tolerance
            if abs(deviation) > threshold:
                if deviation > 0:
                    # Overweight - consider selling
                    if signal_strength < 0 or signals.get("rsi", 50) > 70:
                        action = "SELL"
                        urgency = "HIGH"
                    else:
                        action = "SELL"
                        urgency = "MEDIUM"
                    shares_to_sell = int((deviation * total) / signals.get("current_price", 1))
                    recommendations.append({
                        "ticker": ticker,
                        "action": action,
                        "urgency": urgency,
                        "current_weight": round(current_weight * 100, 2),
                        "target_weight": round(target_pct * 100, 2),
                        "deviation": round(deviation * 100, 2),
                        "shares_to_adjust": shares_to_sell,
                        "estimated_value": round(shares_to_sell * signals.get("current_price", 0), 2),
                        "signals": signals.get("signals", []),
                        "rsi": signals.get("rsi"),
                    })
                else:
                    # Underweight - consider buying
                    if signal_strength > 0 or signals.get("rsi", 50) < 30:
                        action = "BUY"
                        urgency = "HIGH"
                    else:
                        action = "BUY"
                        urgency = "MEDIUM"
                    shares_to_buy = int((abs(deviation) * total) / signals.get("current_price", 1))
                    recommendations.append({
                        "ticker": ticker,
                        "action": action,
                        "urgency": urgency,
                        "current_weight": round(current_weight * 100, 2),
                        "target_weight": round(target_pct * 100, 2),
                        "deviation": round(deviation * 100, 2),
                        "shares_to_adjust": shares_to_buy,
                        "estimated_value": round(shares_to_buy * signals.get("current_price", 0), 2),
                        "signals": signals.get("signals", []),
                        "rsi": signals.get("rsi"),
                    })

        # Cash management based on risk tolerance
        cash_pct = current["cash"] / total if total > 0 else 0
        target_cash = 1.0 - risk  # Higher risk = lower cash target
        if abs(cash_pct - target_cash) > 0.1:
            recommendations.append({
                "action": "ADJUST_CASH",
                "current_cash_pct": round(cash_pct * 100, 2),
                "target_cash_pct": round(target_cash * 100, 2),
                "message": f"Consider {'deploying' if cash_pct > target_cash else 'raising'} cash to align with risk tolerance",
            })

        return recommendations

    def run_analysis(self) -> dict:
        """Run full portfolio analysis and return report."""
        print("=" * 60)
        print("BATESAI — AI PORTFOLIO MANAGER")
        print(f"Analysis Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60)

        # Portfolio value
        current = self.calculate_portfolio_value()
        print(f"\nTotal Portfolio Value: ${current['total_value']:,.2f}")
        print(f"Cash: ${current['cash']:,.2f}")

        # Holdings
        print("\n--- HOLDINGS ---")
        for ticker, data in current["holdings"].items():
            print(f"  {ticker}: {data['shares']} shares @ ${data['current_price']:.2f} = ${data['value']:,.2f} ({data['weight']:.1f}%) | P&L: {data['pnl_pct']:+.1f}%")

        # Signal analysis
        print("\n--- MARKET SIGNALS ---")
        for ticker in self.portfolio["holdings"]:
            signals = self.analyze_signals(ticker)
            if "error" not in signals:
                print(f"  {ticker}: RSI={signals['rsi']:.1f} | Signals: {', '.join(signals['signals'])}")

        # Rebalance recommendations
        print("\n--- REBALANCE RECOMMENDATIONS ---")
        recs = self.generate_rebalance_recommendations()
        if recs:
            for rec in recs:
                if "message" in rec:
                    print(f"  {rec['message']}")
                else:
                    print(f"  {rec['action']} {rec.get('ticker', '')}: {rec.get('urgency', '')} urgency | {rec.get('shares_to_adjust', 0)} shares (~${rec.get('estimated_value', 0):,.2f})")
        else:
            print("  Portfolio is within target allocation.")

        print("\n" + "=" * 60)
        return {
            "portfolio": current,
            "recommendations": recs,
            "timestamp": datetime.now().isoformat(),
        }


def main():
    """CLI interface for portfolio management."""
    import argparse

    parser = argparse.ArgumentParser(description="BatesAI AI Portfolio Manager")
    parser.add_argument("--portfolio", default="portfolio.json", help="Path to portfolio JSON")
    subparsers = parser.add_subparsers(dest="command")

    # Add holding
    add = subparsers.add_parser("add", help="Add a holding")
    add.add_argument("ticker", help="Stock ticker")
    add.add_argument("shares", type=float, help="Number of shares")
    add.add_argument("--cost", type=float, default=None, help="Average cost per share")

    # Set allocation
    alloc = subparsers.add_parser("allocation", help="Set target allocation")
    alloc.add_argument("allocations", nargs="+", help="TICKER=PCT pairs (e.g., AAPL=0.3 MSFT=0.3 CASH=0.4)")

    # Set risk
    risk = subparsers.add_parser("risk", help="Set risk tolerance")
    risk.add_argument("level", type=float, help="Risk level 0.0-1.0")

    # Analyze
    subparsers.add_parser("analyze", help="Run full analysis")

    # Signals
    signals = subparsers.add_parser("signals", help="Analyze signals for a ticker")
    signals.add_argument("ticker", help="Stock ticker")

    # Value
    subparsers.add_parser("value", help="Show current portfolio value")

    # Rebalance
    subparsers.add_parser("rebalance", help="Show rebalance recommendations")

    args = parser.parse_args()
    pm = PortfolioManager(args.portfolio)

    if args.command == "add":
        pm.add_holding(args.ticker, args.shares, args.cost)
        print(f"Added {args.shares} shares of {args.ticker}")
    elif args.command == "allocation":
        alloc_dict = {}
        for item in args.allocations:
            ticker, pct = item.split("=")
            alloc_dict[ticker.upper()] = float(pct)
        pm.set_target_allocation(alloc_dict)
        print(f"Set target allocation: {alloc_dict}")
    elif args.command == "risk":
        pm.set_risk_tolerance(args.level)
        print(f"Set risk tolerance to {args.level}")
    elif args.command == "analyze":
        pm.run_analysis()
    elif args.command == "signals":
        signals = pm.analyze_signals(args.ticker)
        print(json.dumps(signals, indent=2))
    elif args.command == "value":
        value = pm.calculate_portfolio_value()
        print(json.dumps(value, indent=2))
    elif args.command == "rebalance":
        recs = pm.generate_rebalance_recommendations()
        print(json.dumps(recs, indent=2))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
