# BatesAI — AI Portfolio Manager & Stock Analyzer

Balances your portfolio based on holdings, market conditions, and technical signals. Ships with a CLI (`portfolio_manager.py`) and a desktop GUI (`stock_manager_gui.py`) featuring charting and a Systematic Momentum Screener.

## Install

```bash
pip install -r requirements.txt
cp portfolio.example.json portfolio.json   # seed your portfolio state
```

Launch the GUI with `python stock_manager_gui.py`, or use the CLI below.

## Quick Start (CLI)

```bash
# Add holdings
python portfolio_manager.py add AAPL 50 --cost 175.50
python portfolio_manager.py add MSFT 30 --cost 380.00
python portfolio_manager.py add CASH 0

# Set target allocation (percentages must sum to ~1.0)
python portfolio_manager.py allocation AAPL=0.3 MSFT=0.3 CASH=0.4

# Set risk tolerance (0.0 = conservative, 1.0 = aggressive)
python portfolio_manager.py risk 0.6

# Run full analysis
python portfolio_manager.py analyze

# Check signals for a specific ticker
python portfolio_manager.py signals AAPL

# View current value
python portfolio_manager.py value

# Get rebalance recommendations
python portfolio_manager.py rebalance
```

## Features

- **Current Most Recommended Stocks**: on every launch the app backtests a universe of large caps and ranks the top 10 by a transparent **Recommendation Points** score (0-100, where 100 = the best deal imaginable and 0 = guaranteed to tank). The score blends 12-1 momentum, trend structure, a walk-forward SMA backtest, RSI/entry quality, MACD, and risk (volatility + drawdown). See `recommendation_engine.py`.
- **Technical Analysis**: RSI, MACD, Moving Averages, Volatility
- **Signal Detection**: Golden/Death Cross, Overbought/Oversold, MACD crossovers
- **Smart Rebalancing**: Considers both allocation deviation AND market signals
- **Risk-Adjusted**: Cash targets adjust based on your risk tolerance
- **Local-First**: All data stored locally, no cloud dependencies
- **Cached Data**: Historical data cached for 1 hour to minimize API calls

## How Rebalancing Works

1. Compares current allocation vs target allocation
2. Analyzes market signals (RSI, MACD, SMA crossovers)
3. Adjusts urgency based on signal strength
4. Recommends BUY/SELL with share counts and estimated values
5. Factors in your risk tolerance for cash management

## Files

- `portfolio_manager.py` — CLI program (analysis, signals, rebalancing)
- `stock_manager_gui.py` — Desktop GUI (charts + momentum screener)
- `backtest_strategies.py` — Strategy backtesting
- `portfolio.example.json` — Template; copy to `portfolio.json` (gitignored)
- `cache/` — Cached historical data (auto-created)
