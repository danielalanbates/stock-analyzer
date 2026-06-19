import Foundation
import SwiftUI
import UserNotifications

/// A user-defined price alert.
struct PriceAlert: Identifiable, Codable, Equatable {
    var id = UUID()
    var ticker: String
    var above: Bool        // true = notify when price rises above target
    var target: Double
    var enabled: Bool = true
    var triggered: Bool = false
    var lastPrice: Double? = nil
}

/// App-wide persistent state: the watchlist and price alerts, saved to
/// ~/Library/Application Support/StockAnalyzer/state.json. Also runs the
/// background alert monitor that polls quotes and fires notifications.
@MainActor
final class Store: ObservableObject {
    @Published var watchlist: [String] = []
    @Published var alerts: [PriceAlert] = []
    @Published var watchQuotes: [String: Quote] = [:]
    @Published var monitorActive = false

    private let engine = RecommendationEngine()
    private var timer: Timer?

    private var stateURL: URL {
        let dir = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
            .appendingPathComponent("StockAnalyzer", isDirectory: true)
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        return dir.appendingPathComponent("state.json")
    }

    struct Persisted: Codable { var watchlist: [String]; var alerts: [PriceAlert] }

    func load() {
        if let data = try? Data(contentsOf: stateURL),
           let p = try? JSONDecoder().decode(Persisted.self, from: data) {
            watchlist = p.watchlist
            alerts = p.alerts
        }
        requestNotificationAuth()
        startMonitor()
        refreshWatchQuotes()
    }

    func save() {
        let p = Persisted(watchlist: watchlist, alerts: alerts)
        if let data = try? JSONEncoder().encode(p) { try? data.write(to: stateURL) }
    }

    // MARK: Watchlist

    func addToWatchlist(_ raw: String) {
        let t = raw.trimmingCharacters(in: .whitespaces).uppercased()
        guard !t.isEmpty, !watchlist.contains(t) else { return }
        watchlist.append(t); save(); refreshWatchQuotes()
    }

    func removeFromWatchlist(_ t: String) {
        watchlist.removeAll { $0 == t }; save()
    }

    func refreshWatchQuotes() {
        let symbols = Array(Set(watchlist + alerts.map(\.ticker)))
        guard !symbols.isEmpty else { return }
        Task {
            if let q = try? await engine.quotes(symbols) {
                self.watchQuotes.merge(q) { _, new in new }
                self.evaluateAlerts(using: q)
            }
        }
    }

    // MARK: Alerts

    func addAlert(_ a: PriceAlert) { alerts.append(a); save(); refreshWatchQuotes() }
    func removeAlert(_ a: PriceAlert) { alerts.removeAll { $0.id == a.id }; save() }
    func toggleAlert(_ a: PriceAlert) {
        if let i = alerts.firstIndex(where: { $0.id == a.id }) {
            alerts[i].enabled.toggle(); save()
        }
    }

    private func evaluateAlerts(using quotes: [String: Quote]) {
        for i in alerts.indices {
            guard alerts[i].enabled, !alerts[i].triggered,
                  let price = quotes[alerts[i].ticker]?.price else { continue }
            alerts[i].lastPrice = price
            let hit = alerts[i].above ? price >= alerts[i].target : price <= alerts[i].target
            if hit {
                alerts[i].triggered = true
                fireNotification(alerts[i], price: price)
            }
        }
        save()
    }

    // MARK: Monitor

    func startMonitor() {
        guard timer == nil else { return }
        monitorActive = true
        let t = Timer(timeInterval: 60, repeats: true) { [weak self] _ in
            Task { @MainActor in self?.refreshWatchQuotes() }
        }
        RunLoop.main.add(t, forMode: .common)
        timer = t
    }

    // MARK: Notifications

    private func requestNotificationAuth() {
        // Only valid inside a bundled .app; harmless no-op otherwise.
        guard Bundle.main.bundleIdentifier != nil else { return }
        UNUserNotificationCenter.current()
            .requestAuthorization(options: [.alert, .sound]) { _, _ in }
    }

    private func fireNotification(_ a: PriceAlert, price: Double) {
        guard Bundle.main.bundleIdentifier != nil else { return }
        let content = UNMutableNotificationContent()
        content.title = "\(a.ticker) \(a.above ? "rose above" : "fell below") \(a.target)"
        content.body = String(format: "%@ is now $%.2f", a.ticker, price)
        content.sound = .default
        let req = UNNotificationRequest(identifier: a.id.uuidString, content: content, trigger: nil)
        UNUserNotificationCenter.current().add(req)
    }
}
