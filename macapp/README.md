# Stock Analyzer — Native macOS UI (SwiftUI)

A native SwiftUI front-end for the BatesAI Stock Analyzer. It drives the same
validated Python recommendation engine (`../recommendation_engine.py`) but
renders natively — ~100MB RAM vs ~350MB for the Tkinter/matplotlib GUI, so it
runs comfortably on 8GB machines.

## Build & run
```bash
swift build
.build/debug/StockAnalyzerMac
```

The app auto-runs the engine on launch and shows the Top 10 Recommendations.
Override the interpreter/engine location with `STOCKANALYZER_PYTHON` and
`STOCKANALYZER_ENGINE` environment variables.

Status: v0 foundation — Top Recommendations view. Charting, screener, and
portfolio views are the next milestones in the native UI.
