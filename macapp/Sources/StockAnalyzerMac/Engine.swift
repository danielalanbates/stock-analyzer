import Foundation

/// Bridges to the validated Python recommendation engine by running its JSON CLI.
///
/// Resolution order for the engine + interpreter (first existing wins), all
/// overridable via environment variables so the bundled app can point at its
/// embedded copy:
///   STOCKANALYZER_PYTHON   - python interpreter
///   STOCKANALYZER_ENGINE   - directory containing recommendation_engine.py
@MainActor
final class RecommendationEngine {
    static let defaultEngineDir =
        "\(NSHomeDirectory())/Library/Mobile Documents/com~apple~CloudDocs/Code/BatesAI/data/operations/stock-manager"
    static let pythonCandidates = [
        "/Library/Frameworks/Python.framework/Versions/3.14/bin/python3.14",
        "/opt/homebrew/bin/python3",
        "/usr/bin/python3",
    ]

    /// The bundled standalone engine binary, if this is a packaged .app.
    private var bundledEngine: String? {
        if let env = ProcessInfo.processInfo.environment["STOCKANALYZER_CLI"] { return env }
        if let res = Bundle.main.resourceURL?
            .appendingPathComponent("engine/engine_cli").path,
           FileManager.default.isExecutableFile(atPath: res) {
            return res
        }
        return nil
    }

    private func python() -> String {
        if let env = ProcessInfo.processInfo.environment["STOCKANALYZER_PYTHON"] {
            return env
        }
        return Self.pythonCandidates.first { FileManager.default.isExecutableFile(atPath: $0) }
            ?? "/usr/bin/python3"
    }

    private func engineDir() -> String {
        ProcessInfo.processInfo.environment["STOCKANALYZER_ENGINE"] ?? Self.defaultEngineDir
    }

    /// Writable support directory for cache + portfolio (works in a sandboxed app).
    static func supportDir() -> String {
        let dir = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
            .appendingPathComponent("StockAnalyzer", isDirectory: true)
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        return dir.path
    }

    private func cacheDir() -> String {
        let c = "\(Self.supportDir())/cache"
        try? FileManager.default.createDirectory(atPath: c, withIntermediateDirectories: true)
        return c
    }

    /// Runs the engine for one tool ("rec" or "data") and returns stdout JSON.
    /// Prefers the bundled standalone binary; falls back to python + scripts in dev.
    private func runJSON(tool: String, _ toolArgs: [String]) async throws -> Data {
        let dir = engineDir()
        let bundled = bundledEngine
        let py = python()
        let script = tool == "rec" ? "recommendation_engine.py" : "data_cli.py"
        return try await withCheckedThrowingContinuation { cont in
            DispatchQueue.global().async {
                let proc = Process()
                if let bin = bundled {
                    proc.executableURL = URL(fileURLWithPath: bin)
                    proc.arguments = [tool] + toolArgs
                } else {
                    proc.executableURL = URL(fileURLWithPath: py)
                    proc.arguments = [script] + toolArgs
                    proc.currentDirectoryURL = URL(fileURLWithPath: dir)
                }
                let out = Pipe()
                proc.standardOutput = out
                proc.standardError = Pipe()  // discard progress noise
                do {
                    try proc.run()
                    let data = out.fileHandleForReading.readDataToEndOfFile()
                    proc.waitUntilExit()
                    if proc.terminationStatus != 0 {
                        cont.resume(throwing: NSError(
                            domain: "StockAnalyzer", code: Int(proc.terminationStatus),
                            userInfo: [NSLocalizedDescriptionKey:
                                "engine (\(tool)) exited with status \(proc.terminationStatus)"]))
                    } else {
                        cont.resume(returning: data)
                    }
                } catch {
                    cont.resume(throwing: error)
                }
            }
        }
    }

    /// Top recommendations.
    func fetch(count: Int = 10, fast: Bool = true) async throws -> [Recommendation] {
        var args = ["-n", "\(count)", "--json", "--cache", cacheDir()]
        if fast { args.append("--fast") }
        let data = try await runJSON(tool: "rec", args)
        return try JSONDecoder().decode([Recommendation].self, from: data)
    }

    /// Price history with indicator overlays.
    func history(_ ticker: String, period: String = "1y") async throws -> PriceHistory {
        let data = try await runJSON(tool: "data", ["history", ticker, "--period", period])
        return try JSONDecoder().decode(PriceHistory.self, from: data)
    }

    /// Near-real-time intraday bars for today.
    func intraday(_ ticker: String, interval: String = "1m") async throws -> IntradayData {
        let data = try await runJSON(tool: "data", ["intraday", ticker, "--interval", interval])
        return try JSONDecoder().decode(IntradayData.self, from: data)
    }

    /// Momentum screen.
    func screen(fast: Bool = true, count: Int = 40) async throws -> [ScreenRow] {
        var args = ["screen", "-n", "\(count)"]
        if fast { args.append("--fast") }
        let data = try await runJSON(tool: "data", args)
        return try JSONDecoder().decode([ScreenRow].self, from: data)
    }

    // MARK: Brokerage (Alpaca)

    func brokerStatus() async throws -> BrokerStatus {
        let data = try await runJSON(tool: "broker", ["status"])
        return try JSONDecoder().decode(BrokerStatus.self, from: data)
    }

    func brokerAccount() async throws -> BrokerAccount {
        let data = try await runJSON(tool: "broker", ["account"])
        return try JSONDecoder().decode(BrokerAccount.self, from: data)
    }

    func brokerPositions() async throws -> [BrokerPosition] {
        let data = try await runJSON(tool: "broker", ["positions"])
        return try JSONDecoder().decode(BrokerPositionsResponse.self, from: data).positions
    }

    /// Writes Alpaca credentials to App Support/StockAnalyzer/broker.json.
    func saveBrokerKeys(keyId: String, secret: String, paper: Bool) throws {
        let path = "\(Self.supportDir())/broker.json"
        let obj: [String: Any] = ["key_id": keyId, "secret": secret, "paper": paper]
        let data = try JSONSerialization.data(withJSONObject: obj, options: [.prettyPrinted])
        try data.write(to: URL(fileURLWithPath: path))
    }

    func brokerConfigured() -> Bool {
        FileManager.default.fileExists(atPath: "\(Self.supportDir())/broker.json")
    }

    /// Reads portfolio.json from the writable support dir, seeding a default if absent.
    func portfolioFile() throws -> PortfolioFile {
        let path = "\(Self.supportDir())/portfolio.json"
        if !FileManager.default.fileExists(atPath: path) {
            // Seed from a bundled default or the dev engine dir, else an empty book.
            let seed = Bundle.main.resourceURL?.appendingPathComponent("engine/portfolio.json").path
                ?? "\(engineDir())/portfolio.json"
            if FileManager.default.fileExists(atPath: seed) {
                try? FileManager.default.copyItem(atPath: seed, toPath: path)
            } else {
                let empty = #"{"holdings":{},"cash":0}"#
                try? empty.write(toFile: path, atomically: true, encoding: .utf8)
            }
        }
        let data = try Data(contentsOf: URL(fileURLWithPath: path))
        return try JSONDecoder().decode(PortfolioFile.self, from: data)
    }

    /// Latest quotes for the given tickers.
    func quotes(_ tickers: [String]) async throws -> [String: Quote] {
        guard !tickers.isEmpty else { return [:] }
        let data = try await runJSON(tool: "data", ["quotes"] + tickers)
        return try JSONDecoder().decode([String: Quote].self, from: data)
    }

    /// Joins local holdings with live quotes into displayable rows.
    func portfolio() async throws -> (rows: [PortfolioRow], cash: Double) {
        let file = try portfolioFile()
        let tickers = Array(file.holdings.keys)
        let q = try await quotes(tickers)
        let rows = file.holdings.map { (t, h) -> PortfolioRow in
            let quote = q[t]
            return PortfolioRow(ticker: t, shares: h.shares, avgCost: h.avgCost,
                                price: quote?.price ?? h.avgCost,
                                dayChange: quote?.change ?? 0)
        }.sorted { $0.value > $1.value }
        return (rows, file.cash ?? 0)
    }
}
