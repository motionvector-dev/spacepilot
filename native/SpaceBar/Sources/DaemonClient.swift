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

    var userFacing: String {
        switch self {
        case .unreachable:
            return "Not running on 127.0.0.1:8088"
        case .badResponse(let code):
            return "Answered \(code)"
        case .decoding:
            return "Answered with something unexpected"
        }
    }
}

/// Talks to the SpacePilot daemon over loopback HTTP.
///
/// An actor because the token is cached state and the polling timer and the
/// popover both reach for it.
actor DaemonClient {
    static let base = URL(string: "http://127.0.0.1:8088")!

    private let session: URLSession
    private var cachedToken: String?

    init() {
        let config = URLSessionConfiguration.ephemeral
        // Short. A menu bar that hangs for 60s waiting on a dead port is worse
        // than one that says "not running" in two.
        config.timeoutIntervalForRequest = 2.0
        config.waitsForConnectivity = false
        self.session = URLSession(configuration: config)
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

    private func get(_ path: String) async throws -> Data {
        var request = URLRequest(url: Self.base.appendingPathComponent(path))
        request.httpMethod = "GET"
        // The daemon rejects a non-loopback Host header with 421. URLSession
        // sets it correctly from the URL, so this is only here to say that the
        // guard exists and that rewriting the base URL to a LAN address will
        // fail on purpose.
        request.setValue("application/json", forHTTPHeaderField: "Accept")

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
}
