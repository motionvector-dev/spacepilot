// Brain.swift
// What answers a question: Apple's on-device model, a model the daemon
// serves over `/v1/chat/completions`, or an `.aimodel` this app runs itself
// through Core AI. One protocol, three implementations, so
// `VoiceDuplexManager.answer()` and `SelfTest` drive any of them without
// knowing which one they hold.

import CoreAILanguageModels
import Foundation
import FoundationModels

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
    /// No model to answer with, and nothing the app can do about it from
    /// here. `AppleBrain` throws it when Apple Intelligence is off;
    /// `CoreAIBrain` when the `.aimodel` is missing, unreadable, or the
    /// runtime refuses to load it. Both render the same way: say the
    /// sentence, stay idle.
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
    var daemonModel: String? = nil
    /// Where the exported Core AI bundle lives. `nil` means
    /// `CoreAIBrain.defaultModelURL`. Set by `--model` while `--brain coreai`
    /// is in play.
    var coreaiModelPath: String? = nil

    static let defaultsKindKey = "spacebar.brain.kind"
    static let defaultsModelKey = "spacebar.brain.daemonModel"
    static let defaultsCoreAIPathKey = "spacebar.brain.coreaiModelPath"

    /// `--model` means two different things depending on `--brain`: a daemon
    /// model id, or a path to an `.aimodel` bundle. They persist under
    /// separate keys so switching brains back and forth never clobbers the
    /// other one's setting.
    static func resolve(arguments: [String] = CommandLine.arguments,
                        defaults: UserDefaults = .standard) -> BrainSelection {
        var kind = defaults.string(forKey: defaultsKindKey).flatMap(BrainKind.init(rawValue:)) ?? .apple
        var daemonModel = defaults.string(forKey: defaultsModelKey)
        var coreaiModelPath = defaults.string(forKey: defaultsCoreAIPathKey)

        if let index = arguments.firstIndex(of: "--brain"), index + 1 < arguments.count,
           let parsed = BrainKind(rawValue: arguments[index + 1]) {
            kind = parsed
        }
        if let index = arguments.firstIndex(of: "--model"), index + 1 < arguments.count {
            let value = arguments[index + 1]
            if kind == .coreai {
                coreaiModelPath = value
            } else {
                daemonModel = value
            }
        }
        return BrainSelection(kind: kind, daemonModel: daemonModel, coreaiModelPath: coreaiModelPath)
    }

    func persist(to defaults: UserDefaults = .standard) {
        defaults.set(kind.rawValue, forKey: Self.defaultsKindKey)
        Self.store(daemonModel, forKey: Self.defaultsModelKey, in: defaults)
        Self.store(coreaiModelPath, forKey: Self.defaultsCoreAIPathKey, in: defaults)
    }

    private static func store(_ value: String?, forKey key: String, in defaults: UserDefaults) {
        if let value {
            defaults.set(value, forKey: key)
        } else {
            defaults.removeObject(forKey: key)
        }
    }
}

enum BrainKind: String, Sendable {
    case apple
    case daemon
    case coreai
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

/// Runs an exported Core AI `.aimodel` inside this process — no daemon, no
/// network, no Apple Intelligence. Same system instructions and telemetry
/// block as the other two, so all three are answering the same question;
/// only where the weights run differs.
///
/// An actor for the same reason `AppleFoundationModelManager` is one: the
/// model and its session are built once, on the first question, and a
/// `Brain` can be called from anywhere. Loading is where this brain is slow
/// (a few hundred MB off disk), so it must not happen at launch on a Mac
/// where nobody ever picks it.
actor CoreAIBrain: Brain {
    /// The bundle directory the export recipe writes — the folder holding
    /// `*.aimodel` and `tokenizer/`, not the `.aimodel` itself. Under
    /// `media-scratch/`, never inside a checkout: it is 331 MB of generated
    /// weights and one `git add -A` from being tracked.
    static var defaultModelURL: URL {
        URL(fileURLWithPath: NSHomeDirectory())
            .appending(path: "code/motionvector/media-scratch/coreai-exports/Qwen3-0.6B/qwen3_0_6b_4bit_dynamic")
    }

    nonisolated let modelURL: URL

    /// Built on first use. `nil` until then, and stays `nil` if loading
    /// threw — a second question retries rather than caching the failure,
    /// which is what makes "export the model, then ask again" work without
    /// a relaunch.
    private var session: LanguageModelSession?

    init(modelURL: URL) {
        self.modelURL = modelURL
    }

    nonisolated var label: String { "coreai · \(modelURL.lastPathComponent)" }

    func answer(userText: String, telemetry: HardwareSnapshot, daemon: LocalStatus?) async throws -> String {
        let session = try await activeSession()

        let block = SpacePilotInstructions.telemetryBlock(
            shipName: daemon?.deviceName ?? "no reading",
            thermalState: telemetry.thermal,
            backend: daemon?.backend ?? "no reading",
            headroom: daemon?.headroomLine ?? "no reading",
            loadedModels: daemon?.loadedModels ?? [],
            daemonReachable: daemon != nil
        )

        do {
            let response = try await session.respond(to: "\(block)\n\n\(userText)")
            return response.content
        } catch {
            // The session is kept — a generation failure is not a load
            // failure, and rebuilding the session would re-read the weights
            // for nothing.
            throw BrainError.modelUnavailable("the Core AI model failed to answer — \(error.localizedDescription)")
        }
    }

    private func activeSession() async throws -> LanguageModelSession {
        if let session { return session }

        // Checked before the load rather than trusting the runtime's own
        // error, because "no such file" is the failure a person actually
        // hits here (they have not run the export yet) and it deserves a
        // sentence that says what to do.
        var isDirectory: ObjCBool = false
        guard FileManager.default.fileExists(atPath: modelURL.path, isDirectory: &isDirectory) else {
            throw BrainError.unavailable(
                "No Core AI model at \(modelURL.lastPathComponent). Export one first — see SPACEBAR.md.")
        }

        let model: CoreAILanguageModel
        do {
            model = try await CoreAILanguageModel(resourcesAt: modelURL)
        } catch {
            throw BrainError.unavailable(
                "Could not load \(modelURL.lastPathComponent) — \(error.localizedDescription)")
        }

        let fresh = LanguageModelSession(model: model, instructions: SpacePilotInstructions.system)
        session = fresh
        return fresh
    }
}
