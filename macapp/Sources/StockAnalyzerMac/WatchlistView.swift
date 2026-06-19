import SwiftUI

struct WatchlistView: View {
    @EnvironmentObject var store: Store
    var onPick: ((String) -> Void)?
    @State private var newTicker = ""

    var body: some View {
        VStack(spacing: 0) {
            HStack {
                Text("WATCHLIST").font(.system(size: 14, weight: .bold))
                    .foregroundStyle(Color(red: 0.91, green: 0.27, blue: 0.38))
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
                        HStack {
                            Text(t).bold().frame(width: 80, alignment: .leading)
                            if let q = store.watchQuotes[t] {
                                Text(String(format: "$%.2f", q.price)).frame(width: 90, alignment: .trailing)
                                Text(String(format: "%+.2f%%", q.change))
                                    .foregroundStyle(q.change >= 0 ? .green : .red)
                                    .frame(width: 80, alignment: .trailing)
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
                }
                .scrollContentBackground(.hidden)
            }
        }
        .background(Color(red: 0.10, green: 0.10, blue: 0.18))
    }

    private func add() {
        store.addToWatchlist(newTicker); newTicker = ""
    }
}
