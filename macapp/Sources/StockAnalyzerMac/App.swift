import SwiftUI

@main
struct StockAnalyzerMacApp: App {
    @StateObject private var store = Store()
    var body: some Scene {
        WindowGroup("BatesAI — Stock Analyzer") {
            RootView()
                .frame(minWidth: 980, minHeight: 640)
                .environmentObject(store)
                .onAppear { store.load() }
        }
        .windowStyle(.titleBar)
    }
}

enum Section: String, CaseIterable, Identifiable {
    case recommendations = "Top Recommendations"
    case chart = "Chart Analyzer"
    case screener = "Momentum Screener"
    case watchlist = "Watchlist"
    case alerts = "Price Alerts"
    case portfolio = "Portfolio"
    var id: String { rawValue }
    var symbol: String {
        switch self {
        case .recommendations: return "star.fill"
        case .chart: return "chart.xyaxis.line"
        case .screener: return "list.number"
        case .watchlist: return "eye.fill"
        case .alerts: return "bell.fill"
        case .portfolio: return "briefcase.fill"
        }
    }
}

struct RootView: View {
    @State private var section: Section? = .recommendations
    @State private var chartTicker: String?

    var body: some View {
        NavigationSplitView {
            List(Section.allCases, selection: $section) { s in
                Label(s.rawValue, systemImage: s.symbol).tag(s)
            }
            .navigationSplitViewColumnWidth(min: 190, ideal: 210)
        } detail: {
            switch section ?? .recommendations {
            case .recommendations:
                RecommendationsView { ticker in
                    chartTicker = ticker
                    section = .chart
                }
            case .chart:
                ChartView(initialTicker: chartTicker)
                    .id(chartTicker ?? "default")
            case .screener:
                ScreenerView { ticker in
                    chartTicker = ticker
                    section = .chart
                }
            case .watchlist:
                WatchlistView { ticker in
                    chartTicker = ticker
                    section = .chart
                }
            case .alerts:
                AlertsView()
            case .portfolio:
                PortfolioView { ticker in
                    chartTicker = ticker
                    section = .chart
                }
            }
        }
    }
}

@MainActor
final class RecommendationsModel: ObservableObject {
    @Published var picks: [Recommendation] = []
    @Published var loading = false
    @Published var error: String?
    @Published var lastUpdated: Date?

    private let engine = RecommendationEngine()

    func refresh() {
        guard !loading else { return }
        loading = true
        error = nil
        Task {
            do {
                let result = try await engine.fetch(count: 10, fast: true)
                self.picks = result
                self.lastUpdated = Date()
            } catch {
                self.error = error.localizedDescription
            }
            self.loading = false
        }
    }
}

struct RecommendationsView: View {
    @StateObject private var model = RecommendationsModel()
    var onPick: ((String) -> Void)?

    var body: some View {
        VStack(spacing: 0) {
            header
            Divider()
            if model.loading && model.picks.isEmpty {
                Spacer()
                ProgressView("Backtesting the market…")
                Spacer()
            } else if let err = model.error, model.picks.isEmpty {
                Spacer()
                VStack(spacing: 8) {
                    Image(systemName: "exclamationmark.triangle").font(.largeTitle)
                    Text("Couldn't run the engine").font(.headline)
                    Text(err).font(.caption).foregroundStyle(.secondary)
                        .multilineTextAlignment(.center).padding(.horizontal)
                }
                Spacer()
            } else {
                table
            }
        }
        .background(Color(red: 0.10, green: 0.10, blue: 0.18))
        .onAppear { model.refresh() }   // auto-backtest on launch
    }

    private var header: some View {
        HStack(alignment: .firstTextBaseline) {
            VStack(alignment: .leading, spacing: 2) {
                Text("CURRENT MOST RECOMMENDED STOCKS")
                    .font(.system(size: 15, weight: .bold))
                    .foregroundStyle(Color(red: 0.91, green: 0.27, blue: 0.38))
                Text("Recommendation Points 0–100 · 100 = best deal imaginable, 0 = guaranteed to tank")
                    .font(.caption).foregroundStyle(.secondary)
            }
            Spacer()
            if let d = model.lastUpdated {
                Text(d.formatted(date: .abbreviated, time: .shortened))
                    .font(.caption).foregroundStyle(.secondary)
            }
            Button(action: model.refresh) {
                Label("Re-run", systemImage: "arrow.clockwise")
            }
            .disabled(model.loading)
        }
        .padding(12)
    }

    private var table: some View {
        Table(model.picks) {
            TableColumn("Ticker") { r in
                Text(r.ticker).bold()
            }.width(70)
            TableColumn("Rec. Points") { r in
                HStack {
                    Text(String(format: "%.1f", r.score))
                        .bold().foregroundStyle(color(for: r.score))
                    ProgressView(value: max(0, min(1, r.score / 100)))
                        .tint(color(for: r.score)).frame(width: 80)
                }
            }.width(160)
            TableColumn("Tech") { r in
                Text(r.technicalScore.map { String(format: "%.0f", $0) } ?? "—")
            }.width(50)
            TableColumn("Fund.") { r in
                Text(r.fundamentalScore.map { String(format: "%.0f", $0) } ?? "—")
            }.width(50)
            TableColumn("Price") { r in
                Text(String(format: "$%.2f", r.price))
            }.width(90)
            TableColumn("12-1 Mom") { r in
                Text(String(format: "%+.1f%%", r.momentum121))
            }.width(80)
            TableColumn("P/E") { r in
                Text(r.pe.map { String(format: "%.1f", $0) } ?? "—")
            }.width(60)
            TableColumn("Tgt Upside") { r in
                Text(r.targetUpside.map { String(format: "%+.0f%%", $0) } ?? "—")
            }.width(90)
            TableColumn("Top Drivers") { r in
                Text(r.drivers).foregroundStyle(.secondary)
            }
            TableColumn("") { r in
                Button {
                    onPick?(r.ticker)
                } label: {
                    Image(systemName: "chart.xyaxis.line")
                }
                .buttonStyle(.borderless)
                .help("Open \(r.ticker) in the chart")
            }.width(36)
        }
        .scrollContentBackground(.hidden)
    }

    private func color(for score: Double) -> Color {
        switch ScoreBand(score) {
        case .elite:  return Color(red: 0.31, green: 0.80, blue: 0.64)
        case .strong: return Color(red: 0.61, green: 0.91, blue: 0.77)
        case .fair:   return Color(white: 0.85)
        case .weak:   return Color(red: 0.91, green: 0.64, blue: 0.27)
        case .avoid:  return Color(red: 0.91, green: 0.27, blue: 0.38)
        }
    }
}
