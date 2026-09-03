// ShipActivity.swift
// The menu bar icon's own state machine — distinct from PopoverState, which
// tracks the voice conversation. This tracks what the *icon* should be
// doing, and every case here is driven by something SpaceBar can actually
// observe over DaemonClient's allowlist (see that file's header for what it
// deliberately excludes: no download, launch, or checkpoint trigger, ever).

import Foundation

enum ShipActivity: Equatable {
    /// Parked. The default, and where every other case returns to.
    case idle
    /// A local-status round trip just completed and changed something —
    /// a one-shot ping, not a loop, because the call itself is fast and
    /// blocking. See ShipIconController.handle(_:.daemonRecovered).
    case probing
    /// A chat call to the daemon (or a local Apple Intelligence answer) is
    /// in flight — true for as long as `PopoverState.thinking` is true.
    case working
    /// Polling GET .../recipes/{id}/progress found an active download.
    /// `progress` is carried for a future meter — see the TODO stub below,
    /// nothing renders it today.
    case downloading(progress: Double)
    /// Polling GET /api/status found a GPU dispatch that has not yet
    /// reached "running". `confirmed` flips true for the one-shot beat that
    /// plays the moment it does.
    case remoteDispatch(confirmed: Bool)
    /// A checkpoint save just happened. Dead code today — see
    /// ShipIconController's "Checkpoints" section for why.
    case checkpointSave
    /// A checkpoint restore just happened. Same caveat as above.
    case checkpointRestore
    /// A chat call ended in failure rather than a spoken reply — the
    /// closest thing this app has to an in-band SSE error, since
    /// `/v1/chat/completions` is called non-streaming today (see
    /// DaemonClient.chatCompletion). Must look distinct from `.offline`:
    /// this is "asked and failed," not "couldn't ask at all."
    case aborted
    /// The daemon is not answering on 127.0.0.1:8088. Static, not animated —
    /// there is nothing in flight to show motion for.
    case offline
}

/// Raw events `VoiceDuplexManager` can actually observe, translated into
/// `ShipActivity` transitions by `ShipIconController`. Kept separate from
/// `ShipActivity` so the voice manager never needs to know the icon's state
/// machine or its animation — only the plain fact that just happened.
enum ShipSignal {
    /// A `localStatus()` call succeeded after the daemon was previously
    /// unreachable (or reachability was still unknown, e.g. at launch).
    case daemonRecovered
    /// A `localStatus()` call failed after the daemon was previously
    /// reachable (or reachability was still unknown, e.g. at launch).
    case daemonWentOffline
    /// `answer()` started a brain call — the closest observable proxy for
    /// "a stream is open" now that `/v1/chat/completions` is non-streaming.
    case chatStarted
    /// `answer()` finished. `aborted` is true for any path that did not end
    /// in a spoken reply — a `BrainError` or a thrown error.
    case chatEnded(aborted: Bool)
}
