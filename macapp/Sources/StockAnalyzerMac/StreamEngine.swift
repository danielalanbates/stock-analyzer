import Foundation

/// One real-time tick from the streaming engine.
struct LiveTick: Decodable {
    let ticker: String
    let price: Double
    let change: Double
    let changePercent: Double
}

/// Drives a long-running streaming subprocess (`engine_cli stream …` or the dev
/// `stream_cli.py`) and publishes ticks as they arrive over Yahoo's WebSocket.
/// Unlike the one-shot JSON calls, this stays alive and pushes updates.
@MainActor
final class StreamEngine: ObservableObject {
    @Published private(set) var ticks: [String: LiveTick] = [:]
    @Published private(set) var streaming = false

    private var process: Process?
    private var buffer = Data()

    static let defaultEngineDir = RecommendationEngine.defaultEngineDir
    private static let pythonCandidates = RecommendationEngine.pythonCandidates

    private func bundledEngine() -> String? {
        if let env = ProcessInfo.processInfo.environment["STOCKANALYZER_CLI"] { return env }
        if let res = Bundle.main.resourceURL?.appendingPathComponent("engine/engine_cli").path,
           FileManager.default.isExecutableFile(atPath: res) { return res }
        return nil
    }

    private func python() -> String {
        if let env = ProcessInfo.processInfo.environment["STOCKANALYZER_PYTHON"] { return env }
        return Self.pythonCandidates.first { FileManager.default.isExecutableFile(atPath: $0) }
            ?? "/usr/bin/python3"
    }

    func start(symbols: [String]) {
        stop()
        let syms = symbols.map { $0.uppercased() }
        guard !syms.isEmpty else { return }

        let proc = Process()
        if let bin = bundledEngine() {
            proc.executableURL = URL(fileURLWithPath: bin)
            proc.arguments = ["stream"] + syms
        } else {
            proc.executableURL = URL(fileURLWithPath: python())
            proc.arguments = ["stream_cli.py"] + syms
            proc.currentDirectoryURL = URL(fileURLWithPath: Self.defaultEngineDir)
        }
        let out = Pipe()
        proc.standardOutput = out
        proc.standardError = Pipe()

        out.fileHandleForReading.readabilityHandler = { [weak self] handle in
            let data = handle.availableData
            guard !data.isEmpty else { return }
            Task { @MainActor in self?.ingest(data) }
        }
        do {
            try proc.run()
            process = proc
            streaming = true
        } catch {
            streaming = false
        }
    }

    func stop() {
        if let p = process, p.isRunning { p.terminate() }
        (process?.standardOutput as? Pipe)?.fileHandleForReading.readabilityHandler = nil
        process = nil
        buffer.removeAll()
        streaming = false
    }

    /// Accumulate bytes and parse complete newline-delimited JSON ticks.
    private func ingest(_ data: Data) {
        buffer.append(data)
        let newline = UInt8(ascii: "\n")
        while let idx = buffer.firstIndex(of: newline) {
            let line = buffer.subdata(in: buffer.startIndex..<idx)
            buffer.removeSubrange(buffer.startIndex...idx)
            guard !line.isEmpty,
                  let tick = try? JSONDecoder().decode(LiveTick.self, from: line)
            else { continue }
            ticks[tick.ticker] = tick
        }
    }
}
