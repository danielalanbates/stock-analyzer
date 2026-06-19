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

    /// Runs `recommendation_engine.py --fast --json` and decodes the result.
    func fetch(count: Int = 10, fast: Bool = true) async throws -> [Recommendation] {
        let dir = engineDir()
        let cache = "\(dir)/cache"
        var args = ["recommendation_engine.py", "-n", "\(count)", "--json", "--cache", cache]
        if fast { args.append("--fast") }

        let proc = Process()
        proc.executableURL = URL(fileURLWithPath: python())
        proc.arguments = args
        proc.currentDirectoryURL = URL(fileURLWithPath: dir)
        let out = Pipe()
        proc.standardOutput = out
        proc.standardError = Pipe()  // discard progress noise

        try proc.run()
        let data = out.fileHandleForReading.readDataToEndOfFile()
        proc.waitUntilExit()

        guard proc.terminationStatus == 0 else {
            throw NSError(domain: "StockAnalyzer", code: Int(proc.terminationStatus),
                          userInfo: [NSLocalizedDescriptionKey:
                            "Engine exited with status \(proc.terminationStatus)"])
        }
        return try JSONDecoder().decode([Recommendation].self, from: data)
    }
}
