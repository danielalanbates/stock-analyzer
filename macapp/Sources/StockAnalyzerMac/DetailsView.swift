import SwiftUI

@MainActor
final class DetailsModel: ObservableObject {
    @Published var ticker = "AAPL"
    @Published var info: StockInfo?
    @Published var loading = false
    @Published var error: String?
    private let engine = RecommendationEngine()

    func load() {
        guard !loading else { return }
        loading = true; error = nil
        let t = ticker.trimmingCharacters(in: .whitespaces).uppercased()
        Task {
            do { self.info = try await engine.info(t) }
            catch { self.error = error.localizedDescription }
            self.loading = false
        }
    }
}

/// Comprehensive financials for any stock / ETF / crypto, with a plain-English
/// tip on every metric. Fields the instrument doesn't have show "—".
struct DetailsView: View {
    @StateObject private var model = DetailsModel()
    var initialTicker: String?

    var body: some View {
        VStack(spacing: 0) {
            HStack {
                Text("STOCK DETAILS").font(.system(size: 14, weight: .bold))
                    .foregroundStyle(Color(red: 0.91, green: 0.27, blue: 0.38))
                TextField("Ticker", text: $model.ticker)
                    .textFieldStyle(.roundedBorder).frame(width: 110)
                    .onSubmit { model.load() }
                Button("Look up", action: model.load).disabled(model.loading)
                Spacer()
            }.padding(12)
            Divider()
            if model.loading {
                Spacer(); ProgressView("Loading \(model.ticker)…"); Spacer()
            } else if let i = model.info {
                ScrollView { content(i).padding(14) }
            } else {
                Spacer()
                Text(model.error ?? "Enter a ticker to see its full financials.")
                    .foregroundStyle(.secondary)
                Spacer()
            }
        }
        .background(Color(red: 0.10, green: 0.10, blue: 0.18))
        .onAppear { if let t = initialTicker { model.ticker = t }; if model.info == nil { model.load() } }
    }

    @ViewBuilder private func content(_ i: StockInfo) -> some View {
        VStack(alignment: .leading, spacing: 16) {
            // Header
            VStack(alignment: .leading, spacing: 2) {
                Text(i.name ?? i.ticker).font(.system(size: 20, weight: .bold))
                HStack(spacing: 8) {
                    Text(i.ticker).bold()
                    if let t = i.type { tag(t) }
                    if let s = i.sector { tag(s) }
                    if let e = i.exchange { Text(e).foregroundStyle(.secondary) }
                }.font(.system(size: 14))
            }

            group("Price", [
                metric("Price", money(i.price, i.currency), "The most recent traded price."),
                metric("Previous Close", money(i.previousClose, i.currency), "Yesterday's final price — the baseline for today's % change."),
                metric("Open", money(i.open, i.currency), "The first traded price when the market opened today."),
                metric("Day Range", range(i.dayLow, i.dayHigh, i.currency), "The lowest and highest prices traded so far today."),
                metric("52-Week Range", range(i.fiftyTwoWeekLow, i.fiftyTwoWeekHigh, i.currency), "The lowest and highest prices over the past year — shows where today's price sits in its yearly span."),
            ])

            group("Size & Volume", [
                metric("Market Cap", bigNum(i.marketCap), "Total value of all shares (price × shares outstanding). How big the company is."),
                metric("Shares Outstanding", bigNum(i.sharesOutstanding), "Total number of shares that exist."),
                metric("Volume", bigNum(i.volume), "How many shares traded today. High volume = lots of activity/interest."),
                metric("Avg Volume", bigNum(i.avgVolume), "Typical daily share volume — compare to today's volume to spot unusual activity."),
            ])

            group("Valuation", [
                metric("P/E (trailing)", num(i.trailingPE), "Price ÷ last 12 months earnings. Lower can mean cheaper; very high means investors expect big growth."),
                metric("P/E (forward)", num(i.forwardPE), "Price ÷ expected next-year earnings. A forward-looking version of P/E."),
                metric("PEG Ratio", num(i.pegRatio), "P/E adjusted for growth. Around 1 is often considered fair value."),
                metric("Price/Book", num(i.priceToBook), "Price vs. the company's net asset value. Under ~1 can signal a bargain (or trouble)."),
                metric("EPS (trailing)", money(i.eps, i.currency), "Earnings per share over the last 12 months — profit attributable to each share."),
                metric("EPS (forward)", money(i.forwardEps, i.currency), "Expected earnings per share next year."),
            ])

            group("Profitability & Growth", [
                metric("Profit Margin", pct(i.profitMargin), "Share of revenue kept as profit. Higher = more efficient."),
                metric("Return on Equity", pct(i.roe), "Profit generated per dollar of shareholder equity. Higher = better use of capital."),
                metric("Revenue Growth", pct(i.revenueGrowth), "Year-over-year sales growth."),
                metric("Total Revenue", bigNum(i.totalRevenue), "Total sales over the last year."),
                metric("Free Cash Flow", bigNum(i.freeCashflow), "Cash left after running and investing in the business — fuel for dividends/buybacks."),
                metric("Debt/Equity", num(i.debtToEquity), "Debt relative to equity. Lower = less financial risk."),
            ])

            group("Income & Risk", [
                metric("Dividend Yield", pctRaw(i.dividendYield), "Annual dividend as a % of price — income you earn just for holding."),
                metric("Beta", num(i.beta), "Volatility vs. the overall market. 1 = moves with the market; >1 = more volatile; <1 = calmer."),
            ])

            group("Analyst View", [
                metric("Mean Target", money(i.targetMeanPrice, i.currency), "Average price analysts expect over the next year."),
                metric("Recommendation", (i.recommendation ?? "—").capitalized, "Analysts' consensus: strong buy / buy / hold / sell."),
                metric("# Analysts", num(i.numAnalysts), "How many analysts cover this stock — more coverage = more reliable consensus."),
            ])

            if let s = i.summary {
                VStack(alignment: .leading, spacing: 4) {
                    Text("About").font(.system(size: 14, weight: .semibold))
                    Text(s).font(.system(size: 14)).foregroundStyle(.secondary)
                        .fixedSize(horizontal: false, vertical: true)
                }
            }
        }
    }

    // MARK: building blocks

    private func group(_ title: String, _ rows: [AnyView]) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(title.uppercased()).font(.system(size: 14, weight: .bold))
                .foregroundStyle(Color(red: 0, green: 0.74, blue: 0.83))
            VStack(spacing: 0) { ForEach(0..<rows.count, id: \.self) { rows[$0] } }
                .padding(10)
                .background(Color(red: 0.086, green: 0.13, blue: 0.24))
                .clipShape(RoundedRectangle(cornerRadius: 8))
        }
    }

    private func metric(_ label: String, _ value: String, _ tip: String) -> AnyView {
        AnyView(
            HStack {
                HStack(spacing: 4) {
                    Text(label).foregroundStyle(.secondary)
                    Image(systemName: "questionmark.circle")
                        .font(.system(size: 11)).foregroundStyle(.secondary.opacity(0.6))
                        .help(tip)            // hover tooltip — a tip on every metric
                }
                Spacer()
                Text(value).fontWeight(.medium)
            }
            .font(.system(size: 14))
            .padding(.vertical, 4)
            .help(tip)
        )
    }

    private func tag(_ s: String) -> some View {
        Text(s).font(.system(size: 14)).padding(.horizontal, 6).padding(.vertical, 1)
            .background(.secondary.opacity(0.2)).clipShape(Capsule())
    }

    // MARK: formatting

    private func num(_ v: Double?) -> String { v.map { String(format: "%.2f", $0) } ?? "—" }
    private func pct(_ v: Double?) -> String { v.map { String(format: "%.2f%%", $0) } ?? "—" }
    private func pctRaw(_ v: Double?) -> String { v.map { String(format: "%.2f%%", $0) } ?? "—" }
    private func money(_ v: Double?, _ cur: String?) -> String {
        guard let v else { return "—" }
        let sym = (cur == nil || cur == "USD") ? "$" : "\(cur!) "
        return sym + v.formatted(.number.precision(.fractionLength(2)).grouping(.automatic))
    }
    private func range(_ lo: Double?, _ hi: Double?, _ cur: String?) -> String {
        guard lo != nil || hi != nil else { return "—" }
        return "\(money(lo, cur)) – \(money(hi, cur))"
    }
    private func bigNum(_ v: Double?) -> String {
        guard let v else { return "—" }
        let a = abs(v)
        if a >= 1e12 { return String(format: "%.2fT", v / 1e12) }
        if a >= 1e9  { return String(format: "%.2fB", v / 1e9) }
        if a >= 1e6  { return String(format: "%.2fM", v / 1e6) }
        if a >= 1e3  { return String(format: "%.2fK", v / 1e3) }
        return String(format: "%.0f", v)
    }
}
