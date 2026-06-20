import SwiftUI

struct WatchlistView: View {
    @EnvironmentObject var store: Store
    @StateObject private var stream = StreamEngine()
    var onPick: ((String) -> Void)?
    @State private var newTicker = ""

    var body: some View {
        VStack(spacing: 0) {
            HStack {
                Text("WATCHLIST").font(.system(size: 14, weight: .bold))
                    .foregroundStyle(Color(red: 0.91, green: 0.27, blue: 0.38))
                if stream.streaming {
                    Label("LIVE", systemImage: "dot.radiowaves.left.and.right")
                        .font(.caption).foregroundStyle(.green)
                }
                Spacer()
                TextField("Add ticker", text: $newTicker)
                    .textFieldStyle(.roundedBorder).frame(width: 130)
                    .onSubmit(add)
                Button("Add", action: add)
                Button { store.refreshWatchQuotes() } label: {
                    Image(systemName: "arrow.clockwise")
                }
            }.padding(12)
            Divider()
            if store.watchlist.isEmpty {
                Spacer()
                Text("Add tickers to track them live.").foregroundStyle(.secondary)
                Spacer()
            } else {
                List {
                    ForEach(store.watchlist, id: \.self) { t in
                        row(for: t)
                    }
                }
                .scrollContentBackground(.hidden)
            }
        }
        .background(Color(red: 0.10, green: 0.10, blue: 0.18))
        .onAppear { stream.start(symbols: store.watchlist) }
        .onDisappear { stream.stop() }
        .onChange(of: store.watchlist) { new in stream.start(symbols: new) }
    }

    @ViewBuilder private func row(for t: String) -> some View {
        // Prefer the live streaming tick; fall back to the polled quote.
        let live = stream.ticks[t]
        let price = live?.price ?? store.watchQuotes[t]?.price
        let chg = live?.changePercent ?? store.watchQuotes[t]?.change
        HStack {
            Text(t).bold().frame(width: 80, alignment: .leading)
            if let price {
                Text(String(format: "$%.2f", price)).frame(width: 90, alignment: .trailing)
                    .foregroundStyle(live != nil ? .primary : .secondary)
                Text(String(format: "%+.2f%%", chg ?? 0))
                    .foregroundStyle((chg ?? 0) >= 0 ? .green : .red)
                    .frame(width: 80, alignment: .trailing)
                if live != nil {
                    Circle().fill(.green).frame(width: 6, height: 6)  // live dot
                }
            } else {
                Text("…").foregroundStyle(.secondary)
            }
            Spacer()
            Button { onPick?(t) } label: { Image(systemName: "chart.xyaxis.line") }
                .buttonStyle(.borderless)
            Button(role: .destructive) { store.removeFromWatchlist(t) } label: {
                Image(systemName: "trash")
            }.buttonStyle(.borderless)
        }
    }

    private func add() {
        store.addToWatchlist(newTicker); newTicker = ""
    }
}
