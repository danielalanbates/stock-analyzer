import SwiftUI

@MainActor
final class ScreenerModel: ObservableObject {
    @Published var rows: [ScreenRow] = []
    @Published var loading = false
    @Published var error: String?
    private let engine = RecommendationEngine()

    func load() {
        guard !loading else { return }
        loading = true; error = nil
        Task {
            do { self.rows = try await engine.screen(fast: true, count: 40) }
            catch { self.error = error.localizedDescription }
            self.loading = false
        }
    }
}

struct ScreenerView: View {
    @StateObject private var model = ScreenerModel()
    var onPick: ((String) -> Void)?

    var body: some View {
        VStack(spacing: 0) {
            HStack {
                Text("SYSTEMATIC MOMENTUM SCREENER")
                    .font(.system(size: 14, weight: .bold))
                    .foregroundStyle(Color(red: 0.91, green: 0.27, blue: 0.38))
                Spacer()
                Button(action: model.load) { Label("Run", systemImage: "play.fill") }
                    .disabled(model.loading)
            }.padding(12)
            Divider()
            if model.loading && model.rows.isEmpty {
                Spacer(); ProgressView("Scanning market…"); Spacer()
            } else {
                Table(model.rows) {
                    TableColumn("Ticker") { Text($0.ticker).bold() }.width(80)
                    TableColumn("12-1 Momentum") {
                        Text(String(format: "%+.2f%%", $0.momentum))
                            .foregroundStyle($0.momentum >= 0 ? .green : .red)
                    }
                    TableColumn("Price") { Text(String(format: "$%.2f", $0.price)) }
                    TableColumn("Day") {
                        Text(String(format: "%+.2f%%", $0.change))
                            .foregroundStyle($0.change >= 0 ? .green : .red)
                    }
                }
                .scrollContentBackground(.hidden)
            }
        }
        .background(Color(red: 0.10, green: 0.10, blue: 0.18))
        .onAppear { if model.rows.isEmpty { model.load() } }
    }
}
