import SwiftUI
import Charts

@MainActor
final class ChartModel: ObservableObject {
    @Published var ticker = "SPY"
    @Published var period = "LIVE"
    @Published var bars: [PriceBar] = []
    @Published var intraday: [IntradayBar] = []
    @Published var liveLast: Double?
    @Published var liveChange: Double?
    @Published var loading = false
    @Published var error: String?

    let periods = ["LIVE", "6mo", "1y", "5y", "MAX"]
    var isLive: Bool { period == "LIVE" }
    private let engine = RecommendationEngine()
    private var liveTimer: Timer?

    func load() {
        guard !loading else { return }
        loading = true; error = nil
        let t = ticker.trimmingCharacters(in: .whitespaces).uppercased()
        let p = period
        Task {
            do {
                if p == "LIVE" {
                    let d = try await engine.intraday(t, interval: "1m")
                    self.intraday = d.bars; self.liveLast = d.last; self.liveChange = d.change
                    self.startLiveTimer()
                } else {
                    self.stopLiveTimer()
                    // "MAX" (inception) maps to yfinance's lowercase "max".
                    let yp = p == "MAX" ? "max" : p
                    self.bars = try await engine.history(t, period: yp).bars
                }
            } catch { self.error = error.localizedDescription }
            self.loading = false
        }
    }

    private func startLiveTimer() {
        guard liveTimer == nil else { return }
        let t = Timer(timeInterval: 30, repeats: true) { [weak self] _ in
            Task { @MainActor in self?.refreshLive() }
        }
        RunLoop.main.add(t, forMode: .common); liveTimer = t
    }

    func stopLiveTimer() { liveTimer?.invalidate(); liveTimer = nil }

    private func refreshLive() {
        guard isLive else { stopLiveTimer(); return }
        let t = ticker.trimmingCharacters(in: .whitespaces).uppercased()
        Task {
            if let d = try? await engine.intraday(t, interval: "1m") {
                self.intraday = d.bars; self.liveLast = d.last; self.liveChange = d.change
            }
        }
    }
}

private let upColor = Color(red: 0.31, green: 0.80, blue: 0.64)
private let downColor = Color(red: 0.91, green: 0.27, blue: 0.38)

struct ChartView: View {
    @StateObject private var model = ChartModel()
    var initialTicker: String?

    @State private var candles = true
    @State private var showSMA = true
    @State private var showBollinger = false
    @State private var showEMA = false

    var body: some View {
        VStack(spacing: 0) {
            controls
            Divider()
            if model.loading && model.bars.isEmpty && model.intraday.isEmpty {
                Spacer(); ProgressView("Loading \(model.ticker)…"); Spacer()
            } else if let e = model.error {
                Spacer(); Text(e).foregroundStyle(.secondary); Spacer()
            } else if model.isLive {
                liveHeader.padding(.horizontal, 12).padding(.top, 6)
                liveChart.padding(12)
                Spacer()
            } else {
                ScrollView {
                    priceChart.frame(height: 360).padding(12)
                    volumeChart.frame(height: 90).padding(.horizontal, 12)
                    macdChart.frame(height: 110).padding(12)
                    rsiChart.frame(height: 110).padding([.horizontal, .bottom], 12)
                }
            }
        }
        .background(Color(red: 0.10, green: 0.10, blue: 0.18))
        .onAppear {
            if let t = initialTicker { model.ticker = t }
            if model.bars.isEmpty { model.load() }
        }
    }

    private var controls: some View {
        VStack(spacing: 8) {
            HStack {
                TextField("Ticker", text: $model.ticker)
                    .textFieldStyle(.roundedBorder).frame(width: 110)
                    .onSubmit { model.load() }
                Picker("", selection: $model.period) {
                    ForEach(model.periods, id: \.self) { Text($0) }
                }.pickerStyle(.segmented).frame(width: 260)
                Button("Load", action: model.load).disabled(model.loading)
                Spacer()
                Text(model.ticker).font(.system(size: 14, weight: .semibold))
            }
            HStack(spacing: 14) {
                Picker("", selection: $candles) {
                    Text("Candles").tag(true); Text("Line").tag(false)
                }.pickerStyle(.segmented).frame(width: 150)
                Toggle("SMA 50/200", isOn: $showSMA)
                Toggle("Bollinger", isOn: $showBollinger)
                Toggle("EMA 12/26", isOn: $showEMA)
                Spacer()
            }.toggleStyle(.checkbox).font(.system(size: 14))
        }.padding(12)
    }

    @ChartContentBuilder private var overlays: some ChartContent {
        if showSMA {
            ForEach(model.bars) { b in
                if let s = b.sma50 {
                    LineMark(x: .value("Date", b.day), y: .value("SMA50", s), series: .value("s", "SMA50"))
                        .foregroundStyle(Color(red: 0, green: 0.74, blue: 0.83)).lineStyle(.init(lineWidth: 1))
                }
                if let s = b.sma200 {
                    LineMark(x: .value("Date", b.day), y: .value("SMA200", s), series: .value("s", "SMA200"))
                        .foregroundStyle(Color(red: 1, green: 0.84, blue: 0)).lineStyle(.init(lineWidth: 1))
                }
            }
        }
        if showEMA {
            ForEach(model.bars) { b in
                if let e = b.ema12 {
                    LineMark(x: .value("Date", b.day), y: .value("EMA12", e), series: .value("s", "EMA12"))
                        .foregroundStyle(.purple).lineStyle(.init(lineWidth: 1))
                }
                if let e = b.ema26 {
                    LineMark(x: .value("Date", b.day), y: .value("EMA26", e), series: .value("s", "EMA26"))
                        .foregroundStyle(.orange).lineStyle(.init(lineWidth: 1))
                }
            }
        }
        if showBollinger {
            ForEach(model.bars) { b in
                if let u = b.bbUpper {
                    LineMark(x: .value("Date", b.day), y: .value("BBU", u), series: .value("s", "BBU"))
                        .foregroundStyle(.gray.opacity(0.6)).lineStyle(.init(lineWidth: 0.5, dash: [3]))
                }
                if let l = b.bbLower {
                    LineMark(x: .value("Date", b.day), y: .value("BBL", l), series: .value("s", "BBL"))
                        .foregroundStyle(.gray.opacity(0.6)).lineStyle(.init(lineWidth: 0.5, dash: [3]))
                }
            }
        }
    }

    private var liveHeader: some View {
        HStack(alignment: .firstTextBaseline, spacing: 10) {
            if let last = model.liveLast {
                Text(String(format: "$%.2f", last)).font(.system(size: 26, weight: .bold))
            }
            if let chg = model.liveChange {
                Text(String(format: "%+.2f%% today", chg))
                    .font(.system(size: 14, weight: .semibold)).foregroundStyle(chg >= 0 ? upColor : downColor)
            }
            Label("LIVE", systemImage: "dot.radiowaves.left.and.right")
                .font(.system(size: 14)).foregroundStyle(.green)
            Spacer()
            Text("\(model.intraday.count) one-minute bars · auto-refreshes")
                .font(.system(size: 14)).foregroundStyle(.secondary)
        }
    }

    private var liveChart: some View {
        let up = (model.liveChange ?? 0) >= 0
        return Chart(model.intraday) { b in
            LineMark(x: .value("Time", b.minute), y: .value("Price", b.close))
                .foregroundStyle(up ? upColor : downColor)
            AreaMark(x: .value("Time", b.minute), y: .value("Price", b.close))
                .foregroundStyle(.linearGradient(
                    colors: [(up ? upColor : downColor).opacity(0.25), .clear],
                    startPoint: .top, endPoint: .bottom))
        }
        .chartYScale(domain: .automatic(includesZero: false))
        .frame(minHeight: 400)
    }

    private var priceChart: some View {
        Chart {
            if candles {
                ForEach(model.bars) { b in
                    if let l = b.low, let h = b.high, let o = b.open, let c = b.close {
                        RuleMark(x: .value("Date", b.day),
                                 yStart: .value("Low", l), yEnd: .value("High", h))
                            .foregroundStyle(b.isUp ? upColor : downColor)
                            .lineStyle(.init(lineWidth: 1))
                        RectangleMark(x: .value("Date", b.day),
                                      yStart: .value("Open", min(o, c)),
                                      yEnd: .value("Close", max(o, c)), width: 3)
                            .foregroundStyle(b.isUp ? upColor : downColor)
                    }
                }
            } else {
                ForEach(model.bars) { b in
                    if let c = b.close {
                        LineMark(x: .value("Date", b.day), y: .value("Close", c))
                            .foregroundStyle(downColor)
                    }
                }
            }
            overlays
        }
        .chartYScale(domain: .automatic(includesZero: false))
    }

    private var volumeChart: some View {
        Chart(model.bars) { b in
            BarMark(x: .value("Date", b.day), y: .value("Vol", b.volume))
                .foregroundStyle((b.isUp ? upColor : downColor).opacity(0.5))
        }
        .chartYAxis { AxisMarks(values: .automatic(desiredCount: 2)) }
    }

    private var macdChart: some View {
        Chart {
            ForEach(model.bars) { b in
                if let h = b.macdHist {
                    BarMark(x: .value("Date", b.day), y: .value("Hist", h))
                        .foregroundStyle((h >= 0 ? upColor : downColor).opacity(0.5))
                }
                if let m = b.macd {
                    LineMark(x: .value("Date", b.day), y: .value("MACD", m), series: .value("s", "MACD"))
                        .foregroundStyle(downColor)
                }
                if let s = b.macdSignal {
                    LineMark(x: .value("Date", b.day), y: .value("Signal", s), series: .value("s", "Signal"))
                        .foregroundStyle(upColor)
                }
            }
        }
    }

    private var rsiChart: some View {
        Chart {
            ForEach(model.bars) { b in
                if let r = b.rsi {
                    LineMark(x: .value("Date", b.day), y: .value("RSI", r))
                        .foregroundStyle(upColor)
                }
            }
            RuleMark(y: .value("OB", 70)).foregroundStyle(.red.opacity(0.4)).lineStyle(.init(dash: [4]))
            RuleMark(y: .value("OS", 30)).foregroundStyle(.green.opacity(0.4)).lineStyle(.init(dash: [4]))
        }
        .chartYScale(domain: 0...100)
    }
}
