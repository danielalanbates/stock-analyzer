import SwiftUI

@MainActor
final class BrokerageModel: ObservableObject {
    @Published var status: BrokerStatus?
    @Published var account: BrokerAccount?
    @Published var positions: [BrokerPosition] = []
    @Published var loading = false
    @Published var connecting = false

    private let engine = RecommendationEngine()

    var connected: Bool { status?.configured == true && status?.ok == true }

    func refresh() {
        guard !loading else { return }
        loading = true
        Task {
            do {
                let s = try await engine.brokerStatus()
                self.status = s
                if s.configured && (s.ok ?? false) {
                    self.account = try? await engine.brokerAccount()
                    self.positions = (try? await engine.brokerPositions()) ?? []
                }
            } catch { /* surfaced via status */ }
            self.loading = false
        }
    }

    func connect(keyId: String, secret: String, paper: Bool) {
        guard !connecting else { return }
        connecting = true
        Task {
            try? engine.saveBrokerKeys(keyId: keyId, secret: secret, paper: paper)
            self.connecting = false
            self.refresh()
        }
    }
}

struct BrokerageView: View {
    @StateObject private var model = BrokerageModel()
    @State private var keyId = ""
    @State private var secret = ""
    @State private var paper = true

    private func money(_ v: Double?) -> String {
        guard let v else { return "—" }
        return "$" + v.formatted(.number.precision(.fractionLength(2)).grouping(.automatic))
    }

    var body: some View {
        VStack(spacing: 0) {
            HStack {
                Text("BROKERAGE").font(.system(size: 14, weight: .bold))
                    .foregroundStyle(Color(red: 0.91, green: 0.27, blue: 0.38))
                if let s = model.status, s.configured {
                    Text(s.paper == true ? "PAPER" : "LIVE")
                        .font(.system(size: 14)).padding(.horizontal, 6).padding(.vertical, 2)
                        .background(.secondary.opacity(0.2)).clipShape(Capsule())
                }
                Spacer()
                Button(action: model.refresh) { Label("Refresh", systemImage: "arrow.clockwise") }
                    .disabled(model.loading)
            }.padding(12)
            Divider()

            if model.connected {
                connectedView
            } else {
                connectForm
            }
            Spacer()
        }
        .background(Color(red: 0.10, green: 0.10, blue: 0.18))
        .onAppear { model.refresh() }
    }

    private var connectedView: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack(spacing: 28) {
                stat("Equity", money(model.account?.equity))
                stat("Cash", money(model.account?.cash))
                stat("Buying Power", money(model.account?.buyingPower))
                stat("Long Value", money(model.account?.longMarketValue))
                Spacer()
            }.padding(12)
            Divider()
            if model.positions.isEmpty {
                Text("No open positions.").foregroundStyle(.secondary).padding(12)
            } else {
                Table(model.positions) {
                    TableColumn("Ticker") { Text($0.ticker).bold() }.width(70)
                    TableColumn("Qty") { Text($0.qty.formatted()) }.width(70)
                    TableColumn("Avg Cost") { Text(money($0.avgCost)) }.width(90)
                    TableColumn("Price") { Text(money($0.price)) }.width(90)
                    TableColumn("Value") { Text(money($0.value)) }.width(110)
                    TableColumn("P&L") { p in
                        Text(money(p.pnl)).foregroundStyle(p.pnl >= 0 ? .green : .red)
                    }.width(100)
                    TableColumn("P&L %") { p in
                        Text(String(format: "%+.1f%%", p.pnlPct))
                            .foregroundStyle(p.pnl >= 0 ? .green : .red)
                    }.width(80)
                }
                .scrollContentBackground(.hidden)
                .frame(minHeight: 260)
            }
        }
    }

    private var connectForm: some View {
        VStack(alignment: .leading, spacing: 14) {
            Text("Connect Alpaca for real-time quotes & live account sync")
                .font(.system(size: 14, weight: .semibold))
            Text("A free Alpaca paper-trading account unlocks real-time market data and your live positions. Create one at alpaca.markets → Paper Trading → API Keys, then paste them here.")
                .font(.system(size: 14)).foregroundStyle(.secondary)
                .fixedSize(horizontal: false, vertical: true)

            Grid(alignment: .leading, horizontalSpacing: 10, verticalSpacing: 8) {
                GridRow {
                    Text("Key ID").frame(width: 80, alignment: .trailing)
                    TextField("APCA-API-KEY-ID", text: $keyId).frame(width: 320)
                }
                GridRow {
                    Text("Secret").frame(width: 80, alignment: .trailing)
                    SecureField("APCA-API-SECRET-KEY", text: $secret).frame(width: 320)
                }
                GridRow {
                    Text("")
                    Toggle("Paper trading (recommended)", isOn: $paper)
                }
            }

            HStack {
                Button {
                    model.connect(keyId: keyId, secret: secret, paper: paper)
                } label: {
                    if model.connecting { ProgressView().controlSize(.small) }
                    else { Text("Connect") }
                }
                .buttonStyle(.borderedProminent)
                .disabled(keyId.isEmpty || secret.isEmpty || model.connecting)

                if let s = model.status, s.configured, s.ok == false, let e = s.error {
                    Label(e, systemImage: "exclamationmark.triangle")
                        .font(.system(size: 14)).foregroundStyle(.orange)
                }
            }
            Text("Keys are stored locally in ~/Library/Application Support/StockAnalyzer/broker.json and never leave your machine.")
                .font(.system(size: 14)).foregroundStyle(.secondary)
        }
        .padding(16)
        .frame(maxWidth: 560, alignment: .leading)
    }

    private func stat(_ label: String, _ value: String) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(label).font(.system(size: 14)).foregroundStyle(.secondary)
            Text(value).font(.title3.weight(.semibold))
        }
    }
}
