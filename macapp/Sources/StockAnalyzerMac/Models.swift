import Foundation

/// One ranked pick decoded from the Python recommendation engine's JSON.
struct Recommendation: Identifiable, Decodable {
    var id: String { ticker }
    let ticker: String
    let score: Double
    let technicalScore: Double?
    let fundamentalScore: Double?
    let price: Double
    let dailyChange: Double
    let momentum121: Double
    let rsi: Double
    let pe: Double?
    let targetUpside: Double?
    let drivers: String

    enum CodingKeys: String, CodingKey {
        case ticker, score, price, drivers, rsi, pe
        case technicalScore = "technical_score"
        case fundamentalScore = "fundamental_score"
        case dailyChange = "daily_change"
        case momentum121 = "momentum_12_1"
        case targetUpside = "target_upside"
    }
}

/// One daily OHLC bar with overlay indicators, from `data_cli.py history`.
struct PriceBar: Identifiable, Decodable {
    var id: String { date }
    let date: String
    let open: Double?
    let high: Double?
    let low: Double?
    let close: Double?
    let volume: Int
    let sma50: Double?
    let sma200: Double?
    let rsi: Double?
    let ema12: Double?
    let ema26: Double?
    let bbUpper: Double?
    let bbLower: Double?
    let bbMid: Double?
    let macd: Double?
    let macdSignal: Double?
    let macdHist: Double?

    var isUp: Bool { (close ?? 0) >= (open ?? 0) }

    var day: Date {
        ISO8601DateFormatter.justDate.date(from: date) ?? Date()
    }
}

struct PriceHistory: Decodable {
    let ticker: String
    let period: String
    let bars: [PriceBar]
}

/// One row from `data_cli.py screen`.
struct ScreenRow: Identifiable, Decodable {
    var id: String { ticker }
    let ticker: String
    let momentum: Double
    let price: Double
    let change: Double
}

extension ISO8601DateFormatter {
    static let justDate: DateFormatter = {
        let f = DateFormatter()
        f.dateFormat = "yyyy-MM-dd"
        f.locale = Locale(identifier: "en_US_POSIX")
        return f
    }()
}

// MARK: - Portfolio

struct Quote: Decodable { let price: Double; let change: Double }

struct PortfolioHolding: Decodable {
    let shares: Double
    let avgCost: Double
    enum CodingKeys: String, CodingKey { case shares; case avgCost = "avg_cost" }
}

struct PortfolioFile: Decodable {
    let holdings: [String: PortfolioHolding]
    let cash: Double?
}

/// A holding joined with its live quote, for display.
struct PortfolioRow: Identifiable {
    var id: String { ticker }
    let ticker: String
    let shares: Double
    let avgCost: Double
    let price: Double
    let dayChange: Double
    var value: Double { shares * price }
    var costBasis: Double { shares * avgCost }
    var pnl: Double { value - costBasis }
    var pnlPct: Double { costBasis > 0 ? (value / costBasis - 1) * 100 : 0 }
}

enum ScoreBand {
    case elite, strong, fair, weak, avoid
    init(_ score: Double) {
        switch score {
        case 80...: self = .elite
        case 65..<80: self = .strong
        case 50..<65: self = .fair
        case 35..<50: self = .weak
        default: self = .avoid
        }
    }
}
