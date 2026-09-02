// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "SpaceBar",
    platforms: [
        .macOS("26.0")
    ],
    products: [
        .executable(name: "SpaceBar", targets: ["SpaceBar"])
    ],
    targets: [
        .executableTarget(
            name: "SpaceBar",
            path: "Sources"
        )
    ]
)
