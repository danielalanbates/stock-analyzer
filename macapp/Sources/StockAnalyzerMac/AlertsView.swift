import SwiftUI

struct AlertsView: View {
    @EnvironmentObject var store: Store
    @State private var ticker = ""
    @State private var target = ""
    @State private var above = true

    var body: some View {
        VStack(spacing: 0) {
            HStack {
                Text("PRICE ALERTS").font(.system(size: 14, weight: .bold))
                    .foregroundStyle(Color(red: 0.91, green: 0.27, blue: 0.38))
                Spacer()
                if store.monitorActive {
                    Label("Monitoring", systemImage: "dot.radiowaves.left.and.right")
                        .font(.system(size: 14)).foregroundStyle(.green)
                }
            }.padding(12)

            HStack {
                TextField("Ticker", text: $ticker).textFieldStyle(.roundedBorder).frame(width: 90)
                Picker("", selection: $above) {
                    Text("rises above").tag(true)
                    Text("falls below").tag(false)
                }.frame(width: 130)
                TextField("Price", text: $target).textFieldStyle(.roundedBorder).frame(width: 90)
                Button("Add Alert", action: add)
                    .disabled(ticker.isEmpty || Double(target) == nil)
                Spacer()
            }.padding(.horizontal, 12).padding(.bottom, 8)
            Divider()

            if store.alerts.isEmpty {
                Spacer()
                Text("No alerts yet. Get notified when a price crosses your target.")
                    .foregroundStyle(.secondary)
                Spacer()
            } else {
                List {
                    ForEach(store.alerts) { a in
                        HStack {
                            Image(systemName: a.triggered ? "checkmark.circle.fill" :
                                    (a.enabled ? "bell.fill" : "bell.slash"))
                                .foregroundStyle(a.triggered ? .green : (a.enabled ? .yellow : .gray))
                            Text(a.ticker).bold().frame(width: 70, alignment: .leading)
                            Text("\(a.above ? "≥" : "≤") $\(a.target, specifier: "%.2f")")
                                .frame(width: 90, alignment: .leading)
                            if let p = a.lastPrice {
                                Text(String(format: "now $%.2f", p)).foregroundStyle(.secondary)
                            }
                            if a.triggered { Text("TRIGGERED").font(.system(size: 14)).foregroundStyle(.green) }
                            Spacer()
                            Button { store.toggleAlert(a) } label: {
                                Image(systemName: a.enabled ? "pause" : "play")
                            }.buttonStyle(.borderless)
                            Button(role: .destructive) { store.removeAlert(a) } label: {
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
        guard let t = Double(target) else { return }
        store.addAlert(PriceAlert(ticker: ticker.uppercased(), above: above, target: t))
        ticker = ""; target = ""
    }
}
