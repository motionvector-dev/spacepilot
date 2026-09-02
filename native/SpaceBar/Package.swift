// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "SpaceBar",
    // 27.0, not 26.0, because Apple's coreai-models package declares
    // `.macOS("27.0")` and SwiftPM refuses a dependent with a lower floor.
    // The CoreAI brain is the whole reason that dependency is here, so there
    // is no build that keeps both it and macOS 26.
    platforms: [
        .macOS("27.0")
    ],
    products: [
        .executable(name: "SpaceBar", targets: ["SpaceBar"])
    ],
    dependencies: [
        // Pinned to a revision, not a version range: Apple ships this repo
        // without semver discipline and the .aimodel bundle format moves with
        // it. Bump deliberately, alongside a re-export of the model.
        .package(
            url: "https://github.com/apple/coreai-models",
            revision: "cefd53d70a453518861d1958cdbb4dddab8ece34"
        )
    ],
    targets: [
        .executableTarget(
            name: "SpaceBar",
            dependencies: [
                .product(name: "CoreAILM", package: "coreai-models")
            ],
            path: "Sources"
        )
    ]
)
