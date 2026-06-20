#!/usr/bin/env python3
"""
BatesAI — Unified engine CLI (for bundling into the native macOS app).

Dispatches to the recommendation engine or the data CLI so the whole Python
side ships as a single PyInstaller binary:

    engine_cli rec  -n 10 --json --fast --cache <dir>
    engine_cli data history AAPL --period 1y
    engine_cli data quotes AAPL MSFT
"""

import sys


def main():
    if len(sys.argv) < 2:
        print("usage: engine_cli {rec|data} ...", file=sys.stderr)
        sys.exit(2)
    mode = sys.argv[1]
    # Re-shape argv so the delegated module sees a normal argument vector.
    sys.argv = [sys.argv[0]] + sys.argv[2:]
    if mode == "rec":
        import recommendation_engine as m
        m._cli()
    elif mode == "data":
        import data_cli as m
        m.main()
    elif mode == "broker":
        import broker_cli as m
        m.main()
    else:
        print(f"unknown mode: {mode}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
