// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "StockAnalyzerMac",
    platforms: [.macOS(.v13)],
    targets: [
        .executableTarget(
            name: "StockAnalyzerMac",
            path: "Sources/StockAnalyzerMac"
        )
    ]
)
