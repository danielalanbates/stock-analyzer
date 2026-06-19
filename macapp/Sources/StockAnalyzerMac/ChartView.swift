import SwiftUI
import Charts

@MainActor
final class ChartModel: ObservableObject {
    @Published var ticker = "SPY"
    @Published var period = "1y"
    @Published var bars: [PriceBar] = []
    @Published var loading = false
    @Published var error: String?

    let periods = ["3mo", "6mo", "1y", "2y", "5y"]
    private let engine = RecommendationEngine()

    func load() {
        guard !loading else { return }
        loading = true; error = nil
        let t = ticker.trimmingCharacters(in: .whitespaces).uppercased()
        let p = period
        Task {
            do { self.bars = try await engine.history(t, period: p).bars }
            catch { self.error = error.localizedDescription }
            self.loading = false
        }
    }
}

struct ChartView: View {
    @StateObject private var model = ChartModel()
    var initialTicker: String?

    var body: some View {
        VStack(spacing: 0) {
            controls
            Divider()
            if model.loading && model.bars.isEmpty {
                Spacer(); ProgressView("Loading \(model.ticker)…"); Spacer()
            } else if let e = model.error {
                Spacer(); Text(e).foregroundStyle(.secondary); Spacer()
            } else {
                priceChart
                rsiChart.frame(height: 120)
            }
        }
        .background(Color(red: 0.10, green: 0.10, blue: 0.18))
        .onAppear {
            if let t = initialTicker { model.ticker = t }
            if model.bars.isEmpty { model.load() }
        }
    }

    private var controls: some View {
        HStack {
            TextField("Ticker", text: $model.ticker)
                .textFieldStyle(.roundedBorder).frame(width: 110)
                .onSubmit { model.load() }
            Picker("", selection: $model.period) {
                ForEach(model.periods, id: \.self) { Text($0) }
            }.pickerStyle(.segmented).frame(width: 280)
            Button("Load", action: model.load).disabled(model.loading)
            Spacer()
            Text(model.ticker).font(.headline)
        }.padding(12)
    }

    private var priceChart: some View {
        Chart {
            ForEach(model.bars) { b in
                if let c = b.close {
                    LineMark(x: .value("Date", b.day), y: .value("Close", c))
                        .foregroundStyle(Color(red: 0.91, green: 0.27, blue: 0.38))
                }
                if let s = b.sma50 {
                    LineMark(x: .value("Date", b.day), y: .value("SMA50", s),
                             series: .value("s", "SMA50"))
                        .foregroundStyle(Color(red: 0.0, green: 0.74, blue: 0.83))
                        .lineStyle(.init(lineWidth: 1))
                }
                if let s = b.sma200 {
                    LineMark(x: .value("Date", b.day), y: .value("SMA200", s),
                             series: .value("s", "SMA200"))
                        .foregroundStyle(Color(red: 1.0, green: 0.84, blue: 0.0))
                        .lineStyle(.init(lineWidth: 1))
                }
            }
        }
        .chartForegroundStyleScale([
            "Close": Color(red: 0.91, green: 0.27, blue: 0.38),
            "SMA50": Color(red: 0.0, green: 0.74, blue: 0.83),
            "SMA200": Color(red: 1.0, green: 0.84, blue: 0.0),
        ])
        .padding(12)
    }

    private var rsiChart: some View {
        Chart {
            ForEach(model.bars) { b in
                if let r = b.rsi {
                    LineMark(x: .value("Date", b.day), y: .value("RSI", r))
                        .foregroundStyle(Color(red: 0.31, green: 0.80, blue: 0.64))
                }
            }
            RuleMark(y: .value("OB", 70)).foregroundStyle(.red.opacity(0.4))
                .lineStyle(.init(dash: [4]))
            RuleMark(y: .value("OS", 30)).foregroundStyle(.green.opacity(0.4))
                .lineStyle(.init(dash: [4]))
        }
        .chartYScale(domain: 0...100)
        .padding([.horizontal, .bottom], 12)
    }
}
