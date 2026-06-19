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
