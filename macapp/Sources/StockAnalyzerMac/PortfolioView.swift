import SwiftUI

@MainActor
final class PortfolioModel: ObservableObject {
    @Published var rows: [PortfolioRow] = []
    @Published var cash = 0.0
    @Published var loading = false
    @Published var error: String?
    private let engine = RecommendationEngine()

    var totalValue: Double { rows.reduce(0) { $0 + $1.value } + cash }
    var totalPnL: Double { rows.reduce(0) { $0 + $1.pnl } }
    var totalCost: Double { rows.reduce(0) { $0 + $1.costBasis } }
    var totalPnLPct: Double { totalCost > 0 ? (totalPnL / totalCost) * 100 : 0 }

    func load() {
        guard !loading else { return }
        loading = true; error = nil
        Task {
            do { let r = try await engine.portfolio(); self.rows = r.rows; self.cash = r.cash }
            catch { self.error = error.localizedDescription }
            self.loading = false
        }
    }
}

struct PortfolioView: View {
    @StateObject private var model = PortfolioModel()
    var onPick: ((String) -> Void)?

    private func money(_ v: Double) -> String {
        "$" + v.formatted(.number.precision(.fractionLength(2)).grouping(.automatic))
    }

    var body: some View {
        VStack(spacing: 0) {
            HStack {
                Text("PORTFOLIO").font(.system(size: 14, weight: .bold))
                    .foregroundStyle(Color(red: 0.91, green: 0.27, blue: 0.38))
                Spacer()
                Button(action: model.load) { Label("Refresh", systemImage: "arrow.clockwise") }
                    .disabled(model.loading)
            }.padding(12)

            summary
            Divider()

            if model.loading && model.rows.isEmpty {
                Spacer(); ProgressView("Pricing holdings…"); Spacer()
            } else if let e = model.error {
                Spacer()
                VStack(spacing: 6) {
                    Text("Couldn't load portfolio").font(.system(size: 14, weight: .semibold))
                    Text(e).font(.system(size: 14)).foregroundStyle(.secondary)
                }
                Spacer()
            } else {
                Table(model.rows) {
                    TableColumn("Ticker") { Text($0.ticker).bold() }.width(70)
                    TableColumn("Shares") { Text($0.shares.formatted()) }.width(70)
                    TableColumn("Avg Cost") { Text(money($0.avgCost)) }.width(90)
                    TableColumn("Price") { Text(money($0.price)) }.width(90)
                    TableColumn("Day") { r in
                        Text(String(format: "%+.2f%%", r.dayChange))
                            .foregroundStyle(r.dayChange >= 0 ? .green : .red)
                    }.width(70)
                    TableColumn("Value") { Text(money($0.value)) }.width(110)
                    TableColumn("P&L") { r in
                        Text(money(r.pnl)).foregroundStyle(r.pnl >= 0 ? .green : .red)
                    }.width(110)
                    TableColumn("P&L %") { r in
                        Text(String(format: "%+.1f%%", r.pnlPct))
                            .foregroundStyle(r.pnl >= 0 ? .green : .red)
                    }.width(80)
                    TableColumn("") { r in
                        Button { onPick?(r.ticker) } label: { Image(systemName: "chart.xyaxis.line") }
                            .buttonStyle(.borderless)
                    }.width(36)
                }
                .scrollContentBackground(.hidden)
            }
        }
        .background(Color(red: 0.10, green: 0.10, blue: 0.18))
        .onAppear { if model.rows.isEmpty { model.load() } }
    }

    private var summary: some View {
        HStack(spacing: 28) {
            stat("Total Value", money(model.totalValue), .primary)
            stat("Cash", money(model.cash), .secondary)
            stat("Unrealized P&L", money(model.totalPnL), model.totalPnL >= 0 ? .green : .red)
            stat("Return", String(format: "%+.2f%%", model.totalPnLPct),
                 model.totalPnL >= 0 ? .green : .red)
            Spacer()
        }.padding(.horizontal, 12).padding(.bottom, 10)
    }

    private func stat(_ label: String, _ value: String, _ color: Color) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(label).font(.system(size: 14)).foregroundStyle(.secondary)
            Text(value).font(.title3.weight(.semibold)).foregroundStyle(color)
        }
    }
}
