import SwiftUI

/// Built-in user manual + about. Plain-language guide to every part of the app.
struct HelpView: View {
    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 18) {
                header

                section("Getting started", [
                    "This app helps you research stocks, ETFs, and crypto — find ideas, study charts, track holdings, and watch prices in real time. No account or login is required.",
                    "Pick a section from the left sidebar. Most views have a ticker box — type a symbol (e.g. AAPL, MSFT, SPY, BTC-USD) and press Return.",
                    "Hover the small “?” icons anywhere in the app for a plain-English explanation of that number or control.",
                ])

                manualItem("⭐︎ Top Recommendations",
                    "On launch the app backtests the market and ranks the top 10 by a 0–100 Recommendation Points score. 100 = the strongest setup, 0 = the weakest. The score blends price momentum, a walk-forward strategy backtest, and company fundamentals. Tech = the technical sub-score, Fund. = the fundamentals sub-score. Double-click a row to chart it. Tip: treat it as a starting shortlist for research, not a guarantee.")

                manualItem("📈 Chart Analyzer",
                    "View price history from LIVE (today, 1-minute, auto-refreshing) all the way to MAX (the stock's entire history, back to its IPO). Switch between Candles and Line, and toggle moving averages (SMA/EMA), Bollinger Bands, MACD, and RSI. Candles show open/high/low/close for each period; green = up, red = down.")

                manualItem("🔢 Momentum Screener",
                    "Ranks a universe of large stocks by recent momentum (how much they've climbed). A quick way to see what's moving. Click a row to chart it.")

                manualItem("👁 Watchlist",
                    "Add tickers to follow. When markets are open (crypto is 24/7), prices stream live with a green dot. This is your personal short list.")

                manualItem("🔔 Price Alerts",
                    "Set a target — “rises above” or “falls below” a price — and the app notifies you with a macOS notification when it's crossed. It checks in the background while the app is open.")

                manualItem("💼 Portfolio",
                    "Tracks holdings stored locally on your Mac. Shows live value, cost basis, and unrealized profit/loss per position and overall. No brokerage connection needed.")

                manualItem("📊 Stock Details",
                    "The full financial picture for any symbol: price and 52-week range, market cap, valuation (P/E, PEG, price/book, EPS), profitability (margins, ROE, growth), income (dividend yield), risk (beta), and the analyst consensus. Every metric has a “?” tip. Fields an instrument doesn't have (e.g. P/E for crypto) show “—”.")

                manualItem("🏦 Brokerage",
                    "Optional. Connect a free Alpaca paper-trading account to see your real broker positions and account balance, and to enable true tick-by-tick real-time quotes. Paste your API key and secret; they're stored only on your Mac and never sent anywhere else.")

                section("How the score is built (the rigor)", [
                    "Recommendation Points are not a black box. The weights were tuned against a point-in-time backtest that measures whether higher scores actually preceded higher forward returns. Momentum and the strategy backtest carry the most weight because they showed real predictive value; factors that didn't help were down-weighted. Volatility is reported but not chased, to avoid rewarding reckless risk.",
                    "No model can guarantee an outcome. Use this as rigorous, transparent research support — then make your own decision.",
                ])

                section("About", [
                    "BatesAI Stock Analyzer — a native macOS app. Market data is provided by public Yahoo Finance endpoints; brokerage features use Alpaca. All data and settings stay on your Mac.",
                    "Made by Bates LLC.",
                ])
            }
            .padding(18)
            .frame(maxWidth: 720, alignment: .leading)
        }
        .background(Color(red: 0.10, green: 0.10, blue: 0.18))
    }

    private var header: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text("HELP & USER MANUAL").font(.system(size: 14, weight: .bold))
                .foregroundStyle(Color(red: 0.91, green: 0.27, blue: 0.38))
            Text("A quick guide to every part of the app.")
                .font(.system(size: 14)).foregroundStyle(.secondary)
        }
    }

    private func manualItem(_ title: String, _ body: String) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(title).font(.system(size: 16, weight: .semibold))
                .foregroundStyle(Color(red: 0, green: 0.74, blue: 0.83))
            Text(body).font(.system(size: 14)).foregroundStyle(.primary.opacity(0.9))
                .fixedSize(horizontal: false, vertical: true)
        }
    }

    private func section(_ title: String, _ paragraphs: [String]) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(title).font(.system(size: 16, weight: .semibold))
            ForEach(paragraphs, id: \.self) { p in
                Text(p).font(.system(size: 14)).foregroundStyle(.primary.opacity(0.9))
                    .fixedSize(horizontal: false, vertical: true)
            }
        }
    }
}
