// ShipIconController.swift
// Bridges real signals into ShipActivity transitions and drives
// ShipIconAnimator accordingly. AppDelegate owns one of these and wires
// VoiceDuplexManager's `onShipSignal` closure to `handle(_:)` — the voice
// manager never imports this file, it only emits ShipSignal.

import AppKit

@MainActor
final class ShipIconController {
    private(set) var activity: ShipActivity = .idle

    private let animator: ShipIconAnimator
    private let client = DaemonClient()

    private var downloadPollTask: Task<Void, Never>?
    private var dispatchPollTask: Task<Void, Never>?

    private let idleAmplitude: CGFloat = 1.5
    private let idlePeriod: TimeInterval = 6.0

    init(button: NSStatusBarButton) {
        animator = ShipIconAnimator(button: button)
        playIdleBob()
    }

    // MARK: - Voice signals

    func handle(_ signal: ShipSignal) {
        switch signal {
        case .daemonRecovered:
            probeOnce()
        case .daemonWentOffline:
            setOffline()
        case .chatStarted:
            beginWorking()
        case .chatEnded(let aborted):
            endWorking(aborted: aborted)
        }
    }

    // MARK: - Idle

    /// Always-on and unbounded on purpose — a few px of vertical drift and a
    /// small opacity variation, cheap enough at 12fps that the timeout
    /// ceiling other loops need does not apply here. This is asserted from
    /// reading ShipIconAnimator's per-tick cost (one transform + opacity
    /// set, no image redraw), not measured — see the NOT CONFIRMED note in
    /// the PR body, since nothing in this worktree can run the app to
    /// profile it.
    func playIdleBob() {
        downloadPollTask?.cancel()
        downloadPollTask = nil
        dispatchPollTask?.cancel()
        dispatchPollTask = nil
        activity = .idle
        animator.startIdleLoop { [weak self] elapsed in
            guard let self else { return }
            let phase = (elapsed.truncatingRemainder(dividingBy: self.idlePeriod)) / self.idlePeriod
            let y = CGFloat(sin(phase * 2 * .pi)) * self.idleAmplitude
            let opacity = 0.92 + 0.08 * Float(cos(phase * 2 * .pi))
            self.animator.apply(translationY: y, opacity: opacity)
        }
    }

    // MARK: - Probing (one-shot)
    //
    // Fires when a local-status round trip changes reachability — see
    // VoiceDuplexManager.refreshDaemon(). The call itself is fast and
    // blocking (docs/design confirms /api/compute/local-status reads only
    // this machine), so a one-shot ping covers it; there is no "probing"
    // loop because there is nothing that takes long enough to loop over.

    private func probeOnce() {
        activity = .probing
        let duration = 0.6
        animator.playOnce(duration: duration, completion: { [weak self] in
            self?.playIdleBob()
        }) { [weak self] elapsed in
            guard let self else { return }
            let f = elapsed / duration
            let x = CGFloat(sin(f * .pi)) * 2.5
            self.animator.apply(translationX: x)
        }
    }

    // MARK: - Working (a brain call in flight)
    //
    // `/v1/chat/completions` is called non-streaming (DaemonClient.chatCompletion
    // sends `stream: false`), so there is no literal SSE stream to key off of
    // today — this fires for the whole span of `answer()`, daemon or Apple
    // brain alike, which is the closest real observable signal.

    private func beginWorking() {
        activity = .working
        animator.startLoop(onTimeout: { [weak self] in
            // Past the ceiling the call may still be in flight — a chat
            // completion can legitimately run the length of DaemonClient's
            // 120s timeout — but the animation stops moving rather than
            // spin forever. Still visibly not idle: dimmed, held still.
            self?.animator.apply(opacity: 0.6)
        }) { [weak self] elapsed in
            guard let self else { return }
            let period = 1.4
            let phase = elapsed.truncatingRemainder(dividingBy: period) / period
            self.animator.apply(opacity: Float(0.75 + 0.25 * abs(sin(phase * .pi))))
        }
    }

    private func endWorking(aborted: Bool) {
        if aborted {
            wobbleAborted()
        } else {
            playIdleBob()
        }
    }

    // MARK: - Aborted (one-shot)
    //
    // The closest thing this app has to an in-band SSE error, since the
    // call is non-streaming (see "Working" above). Must read differently
    // from `.offline`: this is "asked and failed," offline is "couldn't ask
    // at all" — a decaying wobble rather than a static dim.

    private func wobbleAborted() {
        activity = .aborted
        let duration = 0.8
        animator.playOnce(duration: duration, completion: { [weak self] in
            self?.playIdleBob()
        }) { [weak self] elapsed in
            guard let self else { return }
            let decay = 1.0 - (elapsed / duration)
            let angle = sin(elapsed * 28) * 0.18 * decay
            self.animator.apply(rotationRadians: CGFloat(angle))
        }
    }

    // MARK: - Offline (static, no timer running at all)

    private func setOffline() {
        downloadPollTask?.cancel()
        downloadPollTask = nil
        dispatchPollTask?.cancel()
        dispatchPollTask = nil
        activity = .offline
        animator.stop()
        animator.apply(opacity: 0.4)
    }

    // MARK: - Downloading — plumbing is real, nothing calls it yet
    //
    // GET .../recipes/{id}/progress is polled here, but no UI in SpaceBar
    // today discovers a recipe_id to watch (there is no recipe browser in
    // the popover), so `beginWatchingDownload` is currently unreachable —
    // the same situation as the checkpoint beats below, for the same
    // reason: nothing to wire it to yet. A download started through the MCP
    // tools (spacepilot_download_model_recipe) would be invisible here even
    // if it were wired: that tool runs in a separate stdio process with no
    // shared state with the daemon on 8088 — see mcp_server.py. Only a
    // download started through the cockpit or the CLI, which both go
    // through this same daemon, could ever be observed this way.

    func beginWatchingDownload(recipeId: String) {
        downloadPollTask?.cancel()
        downloadPollTask = Task { [weak self] in
            guard let self else { return }
            while !Task.isCancelled {
                do {
                    let progress = try await self.client.downloadProgress(recipeId: recipeId)
                    if progress.status == "completed" {
                        await MainActor.run { self.stopWatchingDownload(failed: false) }
                        return
                    }
                    if progress.status == "failed" {
                        await MainActor.run { self.stopWatchingDownload(failed: true) }
                        return
                    }
                    await MainActor.run { self.applyDownloading(progress: progress.progressPercent ?? 0) }
                } catch {
                    await MainActor.run { self.stopWatchingDownload(failed: true) }
                    return
                }
                try? await Task.sleep(nanoseconds: 2_000_000_000)
            }
        }
    }

    func stopWatchingDownload(failed: Bool) {
        downloadPollTask?.cancel()
        downloadPollTask = nil
        if failed {
            wobbleAborted()
        } else {
            playIdleBob()
        }
    }

    private func applyDownloading(progress: Double) {
        let alreadyDownloading: Bool
        if case .downloading = activity { alreadyDownloading = true } else { alreadyDownloading = false }
        activity = .downloading(progress: progress)
        guard !alreadyDownloading else { return }
        animator.startLoop { [weak self] elapsed in
            guard let self else { return }
            let period = 1.0
            let phase = elapsed.truncatingRemainder(dividingBy: period) / period
            self.animator.apply(opacity: Float(0.7 + 0.3 * abs(sin(phase * .pi))))
        }
    }

    // MARK: - Remote dispatch — same gap as downloading
    //
    // GET /api/status is bounded and single-flight cached server-side
    // (gpu_lifecycle.get_cached_status, 2s TTL), so polling it is cheap. But
    // nothing in SpaceBar triggers `POST /api/gpu/launch` — nor should it,
    // that route bills real money and is deliberately never on this app's
    // allowlist (see DaemonClient.DaemonRoute and AGENTS.md's "Money and
    // hardware"). `beginWatchingRemoteDispatch` exists for a future caller
    // that learns a dispatch was launched elsewhere (cockpit, CLI) and asks
    // SpaceBar to watch for it landing — nothing calls it today.

    func beginWatchingRemoteDispatch() {
        dispatchPollTask?.cancel()
        dispatchPollTask = Task { [weak self] in
            guard let self else { return }
            while !Task.isCancelled {
                do {
                    let status = try await self.client.computeStatus()
                    if status.gpuOnline {
                        await MainActor.run { self.stopWatchingDispatch(confirmed: true) }
                        return
                    }
                    await MainActor.run { self.applyRemoteDispatch() }
                } catch {
                    await MainActor.run { self.stopWatchingDispatch(confirmed: false) }
                    return
                }
                try? await Task.sleep(nanoseconds: 3_000_000_000)
            }
        }
    }

    func stopWatchingDispatch(confirmed: Bool) {
        dispatchPollTask?.cancel()
        dispatchPollTask = nil
        if confirmed {
            probeOnce()
        } else {
            playIdleBob()
        }
    }

    private func applyRemoteDispatch() {
        let already: Bool
        if case .remoteDispatch = activity { already = true } else { already = false }
        activity = .remoteDispatch(confirmed: false)
        guard !already else { return }
        animator.startLoop { [weak self] elapsed in
            guard let self else { return }
            let period = 2.0
            let phase = elapsed.truncatingRemainder(dividingBy: period) / period
            let y = CGFloat(sin(phase * 2 * .pi))
            self.animator.apply(translationY: y, opacity: Float(0.8 + 0.2 * sin(phase * 2 * .pi)))
        }
    }

    // MARK: - Checkpoints (dead code — no UI trigger exists yet)
    //
    // Confirmed by inspection: no "checkpoint" string appears anywhere in
    // SpaceBarApp.swift's view code, so there is no control in the popover
    // to call these from — SpaceBar is read-only and cannot create or
    // restore a checkpoint itself. The MCP tools that do
    // (spacepilot_create_checkpoint / _restore_checkpoint in mcp_server.py)
    // run in a separate stdio process with no shared state with the daemon
    // on 8088, so even a checkpoint made that way would be invisible here.
    // TODO: wire these to a real control once SpaceBar gains one.

    func checkpointSaveBeat() {
        activity = .checkpointSave
        ejectOrDock(outward: true)
    }

    func checkpointRestoreBeat() {
        activity = .checkpointRestore
        ejectOrDock(outward: false)
    }

    /// The backend has no real progress signal for a save or restore today
    /// — spacepilot/services/checkpoint_sync.py's upload and download paths
    /// are both `TODO(real-sync)` in-memory mocks that block then return,
    /// no job id, no progress. So this is intentionally a single instant
    /// before/after beat — something ejects, something docks — never a
    /// fill or a duration implying progress that does not exist.
    private func ejectOrDock(outward: Bool) {
        let duration = 0.5
        animator.playOnce(duration: duration, completion: { [weak self] in
            self?.playIdleBob()
        }) { [weak self] elapsed in
            guard let self else { return }
            let f = elapsed / duration
            let x: CGFloat = outward ? CGFloat(f) * 4.0 : CGFloat(1 - f) * 4.0
            let opacity: Float = outward ? Float(1 - f * 0.5) : Float(0.5 + f * 0.5)
            self.animator.apply(translationX: x, opacity: opacity)
        }
    }

    // MARK: - Deferred: needs a product decision, not implemented

    /// TODO(product decision needed): a "first flight" liftoff hero beat —
    /// bigger and longer than any beat above, playing once the first time
    /// SpaceBar reaches some milestone. Blocked on: what exactly counts as
    /// "first flight" (first launch ever? first successful daemon
    /// connection? first spoken answer?) and whether it must persist across
    /// relaunches (a UserDefaults flag) or reset per-session. Stub only —
    /// never called.
    func firstFlightBeat() {
        // Intentionally empty until the trigger condition is decided.
    }

    /// TODO(product decision needed): a meter-fill overlay inside the hull
    /// for `.downloading(progress:)`. Blocked on: what should visually fill
    /// (bytes vs percent vs a coarser bucket) and whether a fill inside an
    /// 18x14pt template glyph is legible at menu-bar scale at all. Stub
    /// only — never called; `applyDownloading` above ignores `progress` and
    /// plays a plain bounded pulse instead.
    func meterFillOverlay(progress: Double) {
        // Intentionally empty until the visual is decided.
    }
}
