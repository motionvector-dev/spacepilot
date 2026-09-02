// Brain.swift
// What answers a question: Apple's on-device model, or a model the daemon
// serves over `/v1/chat/completions`. One protocol, two implementations,
// so `VoiceDuplexManager.answer()` and `SelfTest` drive either without
// knowing which one they hold.

import Foundation

/// A thing that can answer a spoken question, given this machine's telemetry
/// and (if reachable) the daemon's own reading of it.
///
/// Errors are `BrainError`, never a fabricated string — a brain that cannot
/// answer throws and says why, and the caller decides what to say out loud.
protocol Brain: Sendable {
    /// What the Diagnostics picker shows for this brain right now.
    var label: String { get }

    func answer(userText: String, telemetry: HardwareSnapshot, daemon: LocalStatus?) async throws -> String
}

/// The ways a brain can fail to answer. Distinct from a network error: these
/// are what the popover says out loud, so each one carries a sentence a
/// person would actually want to hear.
enum BrainError: Error, Sendable {
    /// Apple Intelligence is off. Only `AppleBrain` throws this.
    case unavailable(String)
    /// The daemon is not answering on 127.0.0.1:8088. Only `DaemonBrain`
    /// throws this — the same reason `VoiceDuplexManager.refreshDaemon()`
    /// already renders as `.daemonOffline`.
    case daemonOffline(String)
    /// The requested model is not in `GET /v1/models`. Carries what is, so
    /// the reply can say it instead of guessing.
    case modelNotListed(requested: String, available: [String])
    /// The daemon answered, but not with a completion — a 409 for weights
    /// that are not cached, a 502 from the driver, anything else the model
    /// path can fail with. Never fabricated; this is the daemon's own words.
    case modelUnavailable(String)

    var userFacing: String {
        switch self {
        case .unavailable(let message):
            return message
        case .daemonOffline(let reason):
            return "daemon offline — \(reason)"
        case .modelNotListed(let requested, let available):
            return available.isEmpty
                ? "\(requested) isn't available, and the daemon has no models listed."
                : "\(requested) isn't available. The daemon has: \(available.joined(separator: ", "))."
        case .modelUnavailable(let message):
            return message
        }
    }
}

/// Which brain answers, and which daemon model if that is the one chosen.
///
/// Resolution order: a launch argument wins over whatever was persisted last
/// session; with neither, Apple is the default — unchanged behaviour for
/// anyone who never touches `--brain`.
struct BrainSelection: Sendable, Equatable {
    var kind: BrainKind
    /// `nil` means "pick the first `runs_well`, served text model at answer
    /// time" — see `DaemonBrain.resolveModel`. Set explicitly by `--model`
    /// or by the Diagnostics picker.
    var daemonModel: String?

    static let defaultsKindKey = "spacebar.brain.kind"
    static let defaultsModelKey = "spacebar.brain.daemonModel"

    static func resolve(arguments: [String] = CommandLine.arguments,
                        defaults: UserDefaults = .standard) -> BrainSelection {
        var kind = defaults.string(forKey: defaultsKindKey).flatMap(BrainKind.init(rawValue:)) ?? .apple
        var daemonModel = defaults.string(forKey: defaultsModelKey)

        if let index = arguments.firstIndex(of: "--brain"), index + 1 < arguments.count,
           let parsed = BrainKind(rawValue: arguments[index + 1]) {
            kind = parsed
        }
        if let index = arguments.firstIndex(of: "--model"), index + 1 < arguments.count {
            daemonModel = arguments[index + 1]
        }
        return BrainSelection(kind: kind, daemonModel: daemonModel)
    }

    func persist(to defaults: UserDefaults = .standard) {
        defaults.set(kind.rawValue, forKey: Self.defaultsKindKey)
        if let daemonModel {
            defaults.set(daemonModel, forKey: Self.defaultsModelKey)
        } else {
            defaults.removeObject(forKey: Self.defaultsModelKey)
        }
    }
}

enum BrainKind: String, Sendable {
    case apple
    case daemon
}

/// Talks to the daemon's `/v1/chat/completions` instead of the on-device
/// model. Same system instructions and telemetry block as `AppleBrain`
/// (`SpacePilotInstructions`), so the two are answering the same question —
/// only where the weights run differs.
struct DaemonBrain: Brain {
    let client: DaemonClient
    /// `nil` means auto-pick. See `resolveModel`.
    let requestedModel: String?

    var label: String { "daemon · \(requestedModel ?? "auto")" }

    func answer(userText: String, telemetry: HardwareSnapshot, daemon: LocalStatus?) async throws -> String {
        let models: [DaemonModelInfo]
        do {
            models = try await client.models()
        } catch let error as DaemonError {
            throw Self.brainError(from: error)
        }

        let textModels = models.filter { $0.kind == "text" }
        let modelId = try resolveModel(from: textModels)

        let block = SpacePilotInstructions.telemetryBlock(
            shipName: daemon?.deviceName ?? "no reading",
            thermalState: telemetry.thermal,
            backend: daemon?.backend ?? "no reading",
            headroom: daemon?.headroomLine ?? "no reading",
            loadedModels: daemon?.loadedModels ?? [],
            daemonReachable: daemon != nil
        )
        let messages = [
            DaemonChatMessage(role: "system", content: SpacePilotInstructions.system),
            DaemonChatMessage(role: "user", content: "\(block)\n\n\(userText)"),
        ]

        do {
            // ~400 tokens is enough for a spoken reply and leaves headroom
            // under the 40-word instruction in SpacePilotInstructions.system.
            return try await client.chatCompletion(model: modelId, messages: messages, maxTokens: 400)
        } catch let error as DaemonError {
            throw Self.brainError(from: error)
        }
    }

    /// An explicit `--model` (or picker choice) must be in the listing or we
    /// refuse rather than send a request the daemon will 404. With none
    /// given, the first `runs_well` **and served** text model — `runs_well`
    /// alone still includes variants with no wired route (`served: false`),
    /// which would 409 on every request; picking one of those as the silent
    /// default would trade one failure for a more confusing one.
    private func resolveModel(from textModels: [DaemonModelInfo]) throws -> String {
        if let requestedModel {
            guard textModels.contains(where: { $0.id == requestedModel }) else {
                throw BrainError.modelNotListed(requested: requestedModel, available: textModels.map(\.id))
            }
            return requestedModel
        }
        if let auto = textModels.first(where: { $0.verdictLevel == "runs_well" && $0.served }) {
            return auto.id
        }
        throw BrainError.modelNotListed(requested: "a runs_well local model", available: textModels.map(\.id))
    }

    private static func brainError(from error: DaemonError) -> BrainError {
        switch error {
        case .unreachable:
            return .daemonOffline("Not running on 127.0.0.1:8088")
        case .apiError(_, let message):
            return .modelUnavailable(message)
        case .badResponse(let code):
            return .modelUnavailable("daemon answered \(code)")
        case .decoding(let detail):
            return .modelUnavailable("daemon answered with something unexpected — \(detail)")
        case .disallowed(let route):
            // Should be unreachable — `DaemonBrain` only ever calls
            // `client.models()` and `client.chatCompletion()`, both on
            // `DaemonRoute.allowed`. Surfaced honestly rather than force-
            // unwrapped, in case that ever stops being true.
            return .modelUnavailable("refused — \(route) is not on SpaceBar's allowlist")
        }
    }
}
