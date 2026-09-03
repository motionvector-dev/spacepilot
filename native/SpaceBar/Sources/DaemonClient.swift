// DaemonClient.swift
// The one way SpaceBar talks to SpacePilot.
//
// This replaces the websocket to ws://127.0.0.1:8090, which was opened and
// never written to or read from. There is no websocket server on 8090; the
// daemon is FastAPI over HTTP on 127.0.0.1:8088.
//
// Two things a reader should know before changing anything here:
//
//   1. The token is fetched, not read from disk. GET /api/token returns the
//      studio token to loopback callers only (spacepilot/api/routes/health.py,
//      gated by is_loopback_client). This is what web/app.js already does.
//      Reading <repo>/.studio_token would need SpaceBar to know where the
//      checkout is, and there is no reason for it to.
//
//   2. The glance endpoint is /api/compute/local-status, NOT
//      /api/cockpit/status. The latter shells out to `aws ec2
//      describe-instances` behind a 2-second cache, so a menu bar polling it
//      every 5s spawns an AWS subprocess every 5s. local-status reads this
//      machine and nothing else.

import Foundation

/// One glance at the local machine, as the daemon reports it.
/// Every field is optional because the daemon's degraded shapes drop keys
/// rather than sending zeros, and a menu bar that renders a missing number
/// as 0.0 is telling a lie.
struct LocalStatus: Decodable, Equatable {
    let status: String?
    let backend: String?
    let deviceName: String?
    let vramUsableGB: Double?
    let vramUsableKnown: Bool?
    let loadedModels: [String]?
    let isLocalCapable: Bool?

    enum CodingKeys: String, CodingKey {
        case status
        case backend
        case deviceName = "device_name"
        case vramUsableGB = "vram_usable_gb"
        case vramUsableKnown = "vram_usable_known"
        case loadedModels = "loaded_models"
        case isLocalCapable = "is_local_capable"
    }

    /// The headroom line, or nil when the daemon says it does not know.
    /// `vram_usable_known: false` means the probe could not measure it, and
    /// the honest answer is "no reading", not a plausible number.
    var headroomLine: String? {
        guard vramUsableKnown != false, let gb = vramUsableGB else { return nil }
        return String(format: "%.1f GB usable", gb)
    }
}

enum DaemonError: Error, Equatable {
    /// Nothing is listening. The daemon is not running.
    case unreachable(String)
    /// It answered, but not with what we asked for.
    case badResponse(Int)
    case decoding(String)
    /// A non-2xx from a `/v1` route, with the message the daemon gave —
    /// `{"detail": {"error": {"message": ...}}}`, the OpenAI error shape
    /// `docs/design/INFERENCE-SURFACE.md` specifies. This is the daemon's
    /// own words, not a guess at why the call failed.
    case apiError(Int, String)
    /// A call site asked for a method+path that is not in
    /// `DaemonRoute.allowed`. This should never fire — it means a future
    /// change added a `get`/`post` call without adding the route to the
    /// allowlist first. See that type's header for why the gate exists.
    case disallowed(String)

    var userFacing: String {
        switch self {
        case .unreachable:
            return "Not running on 127.0.0.1:8088"
        case .badResponse(let code):
            return "Answered \(code)"
        case .decoding:
            return "Answered with something unexpected"
        case .apiError(let status, let message):
            return "\(message) (\(status))"
        case .disallowed(let route):
            return "refused — \(route) is not on SpaceBar's allowlist"
        }
    }
}

/// The only requests SpaceBar is allowed to send to the daemon, checked
/// before every `get`/`post` builds a request.
///
/// SpaceBar's voice loop is still being trusted — a misheard word or a
/// model going sideways should never be able to reach a route that changes
/// the machine or the fleet: no download, no runtime install, no checkpoint
/// create or restore, no dock launch or terminate, no LoRA train. Voice can
/// read, and voice can ask the model to answer; nothing else. This is a
/// single list precisely so growing the surface later is a decision made
/// here, not a side effect of a new call site somewhere else. See
/// `docs/design/SPACEBAR.md`, "Brains — Read-only, for now".
struct DaemonRoute: Hashable, Sendable {
    let method: String
    let path: String

    static let allowed: Set<DaemonRoute> = [
        DaemonRoute(method: "GET", path: "/healthz"),
        DaemonRoute(method: "GET", path: "/api/compute/local-status"),
        DaemonRoute(method: "GET", path: "/api/token"),
        DaemonRoute(method: "GET", path: "/v1/models"),
        DaemonRoute(method: "POST", path: "/v1/chat/completions"),
        // Bounded, single-flight cached server-side (gpu_lifecycle.get_cached_status,
        // 2s TTL — health.py's /api/status has no require_token gate). Read-only-safe:
        // it only ever reports GPU-box/worker state. The routes that actually start or
        // stop billing (POST /api/gpu/launch, /api/gpu/terminate — gpu.py) are not on
        // this allowlist and must never be added here; see AGENTS.md "Money and hardware".
        DaemonRoute(method: "GET", path: "/api/status"),
    ]

    /// A route with exactly one dynamic path segment — `{recipe_id}` in the
    /// real FastAPI route (recipes.py). Matched by prefix+suffix rather than
    /// falling open to every `/api/compute/recipes/*` path, so the allowlist
    /// still names the one shape it permits instead of a whole namespace.
    static let allowedPatterns: [DaemonRoutePattern] = [
        // GET .../recipes/{id}/progress: read-only-safe because it only
        // observes a download job that POST .../recipes/{id}/download
        // (never allowlisted — SpaceBar must never start a download itself)
        // started elsewhere, e.g. the cockpit or the CLI. Requires a token
        // server-side (recipes.py's require_token) even though it is a GET.
        DaemonRoutePattern(method: "GET", prefix: "/api/compute/recipes/", suffix: "/progress"),
    ]

    var isAllowed: Bool {
        if Self.allowed.contains(self) { return true }
        return Self.allowedPatterns.contains { $0.matches(method: method, path: path) }
    }
}

/// One allowlist entry with a single dynamic segment in the middle. Kept
/// separate from the exact-match `DaemonRoute` set on purpose: growing this
/// list is meant to stay rare and deliberate, same as the set above.
struct DaemonRoutePattern: Sendable {
    let method: String
    let prefix: String
    let suffix: String

    func matches(method: String, path: String) -> Bool {
        guard method == self.method, path.hasPrefix(prefix), path.hasSuffix(suffix) else { return false }
        let middle = path.dropFirst(prefix.count).dropLast(suffix.count)
        return !middle.isEmpty && !middle.contains("/")
    }
}

/// One text or embedding variant from `GET /v1/models`, decoded down to
/// what `DaemonBrain` needs to pick a default and validate an explicit
/// choice. See `spacepilot/api/routes/inference.py::list_models`.
struct DaemonModelInfo: Decodable, Sendable {
    let id: String
    let kind: String
    let verdictLevel: String
    let served: Bool

    private enum RootKeys: String, CodingKey { case id, x_spacepilot }
    private enum ExtKeys: String, CodingKey { case kind, verdict, served }
    private enum VerdictKeys: String, CodingKey { case level }

    init(from decoder: Decoder) throws {
        let root = try decoder.container(keyedBy: RootKeys.self)
        id = try root.decode(String.self, forKey: .id)
        let ext = try root.nestedContainer(keyedBy: ExtKeys.self, forKey: .x_spacepilot)
        kind = try ext.decode(String.self, forKey: .kind)
        served = try ext.decode(Bool.self, forKey: .served)
        let verdict = try ext.nestedContainer(keyedBy: VerdictKeys.self, forKey: .verdict)
        verdictLevel = try verdict.decode(String.self, forKey: .level)
    }
}

/// One turn in a `/v1/chat/completions` request — the OpenAI shape
/// `spacepilot/api/routes/inference.py::Message` decodes.
struct DaemonChatMessage: Encodable, Sendable {
    let role: String
    let content: String
}

/// One recipe's download job, from `GET .../recipes/{id}/progress` —
/// `spacepilot/services/model_catalog.py::DownloadJob`. Only the fields
/// ShipIconController needs to animate and to know when to stop polling;
/// the route itself returns the whole job (bytes, local_path, error too).
struct DownloadProgress: Decodable, Sendable {
    let status: String
    let progressPercent: Double?
    let error: String?

    enum CodingKeys: String, CodingKey {
        case status
        case progressPercent = "progress_percent"
        case error
    }
}

/// GPU box status, from `GET /api/status` —
/// `spacepilot/services/gpu_lifecycle.py::get_cached_status`. Only
/// `gpu_online` is needed to detect a pending dispatch reaching "running".
struct ComputeStatus: Decodable, Sendable {
    let gpuOnline: Bool

    enum CodingKeys: String, CodingKey {
        case gpuOnline = "gpu_online"
    }
}

/// Talks to the SpacePilot daemon over loopback HTTP.
///
/// An actor because the token is cached state and the polling timer and the
/// popover both reach for it.
actor DaemonClient {
    static let base = URL(string: "http://127.0.0.1:8088")!

    private let session: URLSession
    private let chatSession: URLSession
    private var cachedToken: String?

    init() {
        let config = URLSessionConfiguration.ephemeral
        // Short. A menu bar that hangs for 60s waiting on a dead port is worse
        // than one that says "not running" in two.
        config.timeoutIntervalForRequest = 2.0
        config.waitsForConnectivity = false
        self.session = URLSession(configuration: config)

        let chatConfig = URLSessionConfiguration.ephemeral
        // A chat completion can mean loading weights and decoding ~400
        // tokens — the 2s health-check budget would abort a real answer
        // before it ever printed a token.
        chatConfig.timeoutIntervalForRequest = 120.0
        chatConfig.waitsForConnectivity = false
        self.chatSession = URLSession(configuration: chatConfig)
    }

    // MARK: - Read-only

    /// Is the daemon up? Cheapest possible question — no AWS, no probe.
    func isAlive() async -> Bool {
        do {
            _ = try await get("/healthz")
            return true
        } catch {
            return false
        }
    }

    /// One glance at this machine. Read-only, open route, no token needed.
    func localStatus() async throws -> LocalStatus {
        let data = try await get("/api/compute/local-status")
        do {
            return try JSONDecoder().decode(LocalStatus.self, from: data)
        } catch {
            throw DaemonError.decoding(String(describing: error))
        }
    }

    /// Every local text and embedding variant, with its fit verdict. Open
    /// route, no token — same tier as `localStatus()`.
    func models() async throws -> [DaemonModelInfo] {
        let data = try await get("/v1/models")
        struct Response: Decodable { let data: [DaemonModelInfo] }
        do {
            return try JSONDecoder().decode(Response.self, from: data).data
        } catch {
            throw DaemonError.decoding(String(describing: error))
        }
    }

    /// One non-streaming call to `/v1/chat/completions`. Returns just the
    /// reply text — `DaemonBrain` is the only caller, and it only ever
    /// needs the one string to speak.
    func chatCompletion(
        model: String,
        messages: [DaemonChatMessage],
        maxTokens: Int,
        temperature: Double = 0.0
    ) async throws -> String {
        let authToken = try await token()
        struct Body: Encodable {
            let model: String
            let messages: [DaemonChatMessage]
            let max_tokens: Int
            let temperature: Double
            let stream: Bool
        }
        let body = Body(model: model, messages: messages, max_tokens: maxTokens,
                        temperature: temperature, stream: false)
        let data = try await post("/v1/chat/completions", body: body, token: authToken)

        struct Choice: Decodable {
            struct Msg: Decodable { let content: String }
            let message: Msg
        }
        struct Response: Decodable { let choices: [Choice] }
        do {
            let decoded = try JSONDecoder().decode(Response.self, from: data)
            guard let content = decoded.choices.first?.message.content else {
                throw DaemonError.decoding("/v1/chat/completions: no choices")
            }
            return content
        } catch let error as DaemonError {
            throw error
        } catch {
            throw DaemonError.decoding(String(describing: error))
        }
    }

    /// One recipe's download progress. Polled only while ShipIconController
    /// believes a download is active — never on a fixed timer regardless of
    /// state, see that type's "Downloading" section. This is the one GET
    /// call that needs a token: `recipes.py`'s route is behind
    /// `require_token` even though it is read-only.
    func downloadProgress(recipeId: String) async throws -> DownloadProgress {
        let authToken = try await token()
        let data = try await get("/api/compute/recipes/\(recipeId)/progress", token: authToken)
        do {
            return try JSONDecoder().decode(DownloadProgress.self, from: data)
        } catch {
            throw DaemonError.decoding(String(describing: error))
        }
    }

    /// GPU box + worker status. Cheap to poll — bounded and single-flight
    /// cached server-side, 2s TTL. Read-only-safe: it only ever reports
    /// state; the routes that start or stop billing are not on this
    /// allowlist and never will be.
    func computeStatus() async throws -> ComputeStatus {
        let data = try await get("/api/status")
        do {
            return try JSONDecoder().decode(ComputeStatus.self, from: data)
        } catch {
            throw DaemonError.decoding(String(describing: error))
        }
    }

    // MARK: - The token

    /// The studio token, fetched once and kept in memory.
    ///
    /// Nothing in the read-only path needs this. It exists so the compute
    /// path — which is behind a spoken confirmation, see docs/design/SPACEBAR.md
    /// — has a token to send when that lands. Fetching it costs one loopback
    /// request and never touches the filesystem.
    func token() async throws -> String {
        if let cachedToken { return cachedToken }
        let data = try await get("/api/token")
        struct Payload: Decodable { let token: String }
        guard let payload = try? JSONDecoder().decode(Payload.self, from: data) else {
            throw DaemonError.decoding("/api/token")
        }
        cachedToken = payload.token
        return payload.token
    }

    // MARK: - Transport

    private func get(_ path: String, token: String? = nil) async throws -> Data {
        let route = DaemonRoute(method: "GET", path: path)
        guard route.isAllowed else { throw DaemonError.disallowed("GET \(path)") }

        var request = URLRequest(url: Self.base.appendingPathComponent(path))
        request.httpMethod = "GET"
        // The daemon rejects a non-loopback Host header with 421. URLSession
        // sets it correctly from the URL, so this is only here to say that the
        // guard exists and that rewriting the base URL to a LAN address will
        // fail on purpose.
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        // Most GET routes here are open (no require_token gate). The recipe
        // progress route is the one exception — see downloadProgress().
        if let token { request.setValue(token, forHTTPHeaderField: "X-SpacePilot-Token") }

        let data: Data
        let response: URLResponse
        do {
            (data, response) = try await session.data(for: request)
        } catch {
            throw DaemonError.unreachable(error.localizedDescription)
        }
        guard let http = response as? HTTPURLResponse else {
            throw DaemonError.badResponse(0)
        }
        guard (200..<300).contains(http.statusCode) else {
            throw DaemonError.badResponse(http.statusCode)
        }
        return data
    }

    private func post<Body: Encodable>(_ path: String, body: Body, token: String) async throws -> Data {
        let route = DaemonRoute(method: "POST", path: path)
        guard route.isAllowed else { throw DaemonError.disallowed("POST \(path)") }

        var request = URLRequest(url: Self.base.appendingPathComponent(path))
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue(token, forHTTPHeaderField: "X-SpacePilot-Token")
        request.httpBody = try JSONEncoder().encode(body)

        let data: Data
        let response: URLResponse
        do {
            (data, response) = try await chatSession.data(for: request)
        } catch {
            throw DaemonError.unreachable(error.localizedDescription)
        }
        guard let http = response as? HTTPURLResponse else {
            throw DaemonError.badResponse(0)
        }
        guard (200..<300).contains(http.statusCode) else {
            throw DaemonError.apiError(http.statusCode, Self.errorMessage(from: data) ?? "answered \(http.statusCode)")
        }
        return data
    }

    /// Pulls the human-readable message out of the OpenAI error shape every
    /// `/v1` refusal uses: `{"detail": {"error": {"message": ...}}}`. `nil`
    /// when the body does not parse, so the caller falls back to the status
    /// code rather than a guess.
    private static func errorMessage(from data: Data) -> String? {
        struct Body: Decodable {
            struct Detail: Decodable {
                struct Err: Decodable { let message: String }
                let error: Err
            }
            let detail: Detail
        }
        return try? JSONDecoder().decode(Body.self, from: data).detail.error.message
    }
}
