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

    /// Runs a Python script in the engine dir and returns raw stdout JSON.
    private func runJSON(script: String, _ extra: [String]) async throws -> Data {
        let dir = engineDir()
        let py = python()
        return try await withCheckedThrowingContinuation { cont in
            DispatchQueue.global().async {
                let proc = Process()
                proc.executableURL = URL(fileURLWithPath: py)
                proc.arguments = [script] + extra
                proc.currentDirectoryURL = URL(fileURLWithPath: dir)
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
                                "\(script) exited with status \(proc.terminationStatus)"]))
                    } else {
                        cont.resume(returning: data)
                    }
                } catch {
                    cont.resume(throwing: error)
                }
            }
        }
    }

    /// Runs `recommendation_engine.py --json` and decodes the result.
    func fetch(count: Int = 10, fast: Bool = true) async throws -> [Recommendation] {
        let cache = "\(engineDir())/cache"
        var args = ["-n", "\(count)", "--json", "--cache", cache]
        if fast { args.append("--fast") }
        let data = try await runJSON(script: "recommendation_engine.py", args)
        return try JSONDecoder().decode([Recommendation].self, from: data)
    }

    /// Runs `data_cli.py history TICKER --period P`.
    func history(_ ticker: String, period: String = "1y") async throws -> PriceHistory {
        let data = try await runJSON(script: "data_cli.py",
                                     ["history", ticker, "--period", period])
        return try JSONDecoder().decode(PriceHistory.self, from: data)
    }

    /// Runs `data_cli.py screen --fast -n N`.
    func screen(fast: Bool = true, count: Int = 40) async throws -> [ScreenRow] {
        var args = ["screen", "-n", "\(count)"]
        if fast { args.append("--fast") }
        let data = try await runJSON(script: "data_cli.py", args)
        return try JSONDecoder().decode([ScreenRow].self, from: data)
    }
}
