// ShipIconController.swift
// Bridges real signals into ShipActivity transitions and drives
// ShipIconAnimator accordingly. AppDelegate owns one of these and wires
// VoiceDuplexManager's `onShipSignal` closure to `handle(_:)` — the voice
// manager never imports this file, it only emits ShipSignal.

import AppKit
import QuartzCore

@MainActor
final class ShipIconController {
    private(set) var activity: ShipActivity = .idle

    /// Reachability as SpaceBar currently believes it, kept independently of
    /// `activity` — `activity` describes what the icon is *animating right
    /// now* (which can legitimately be `.probing` or `.aborted` for a beat
    /// while still offline underneath), `isReachable` is what it should
    /// settle back to once that beat ends. This is the one source of truth
    /// `settleToCurrentState()` reads; no completion handler hardcodes a
    /// destination state directly. See finding #1.
    private var isReachable = true
    /// True for the span of a chat call (`chatStarted` … `chatEnded`),
    /// independent of `activity` for the same reason as `isReachable` — a
    /// one-shot beat (the recovery probe) can play *during* a working call
    /// without that meaning the call is no longer in flight. See finding #4.
    private var isWorking = false

    private let animator: ShipIconAnimator
    private let client = DaemonClient()

    private var downloadPollTask: Task<Void, Never>?
    private var dispatchPollTask: Task<Void, Never>?

    private let idleAmplitude: CGFloat = 1.5
    private let idlePeriod: TimeInterval = 6.0

    /// Wall-clock ceilings on the progress/status poll loops below — separate
    /// from `ShipIconAnimator.defaultMaxLoopDuration` (45s), which only
    /// bounds one *animation* burst, not the underlying operation. A model
    /// recipe download is realistically minutes, not seconds, so a 45s poll
    /// ceiling would abandon (and mis-report as failed) any real download
    /// almost immediately. These numbers are a judgment call, not a measured
    /// fact — documented here so the next person can revise them instead of
    /// archaeologizing the diff: 30 minutes for a download is generous for
    /// even a large model recipe on a slow link; 10 minutes for a remote
    /// dispatch reaching "running" is generous for a g6e.2xlarge spot launch.
    /// Past the ceiling we stop polling (and stop firing outbound requests)
    /// rather than loop on a job stuck in a non-terminal state forever.
    private static let maxDownloadPollDuration: TimeInterval = 30 * 60
    private static let maxDispatchPollDuration: TimeInterval = 10 * 60

    /// True while the machine is fully asleep or the display is off. The
    /// idle bob is the one always-on loop in this file (see its doc comment)
    /// so it is the one thing worth pausing outright rather than just
    /// dimming — there is nothing to show motion for while nobody can see
    /// it. Chosen over stopping/restarting the animator's `Timer` because
    /// `RunLoop` timers already stop firing during full sleep on their own;
    /// what this actually buys is skipping ticks during *display* sleep,
    /// where the CPU (and this timer) keeps running but the screen doesn't.
    /// See finding #7.
    private var isSuspended = false

    init(button: NSStatusBarButton) {
        animator = ShipIconAnimator(button: button)
        observeSleepAndWake()
        playIdleBob()
    }

    // No deinit / observer teardown: `ShipIconController` lives exactly as
    // long as `AppDelegate` does (one instance, created in
    // `applicationDidFinishLaunching`, never torn down before process exit).
    // Swift 6 makes `deinit` unconditionally nonisolated, so removing a
    // @MainActor-isolated observer list there would need extra ceremony
    // (Sendable tokens, a nonisolated(unsafe) box) to protect a cleanup path
    // that, for an app-lifetime singleton, never actually runs.
    private func observeSleepAndWake() {
        // `queue: .main` guarantees these blocks run on the main thread, but
        // `NotificationCenter`'s closure parameter is typed `@Sendable` with
        // no way to declare that guarantee to the compiler — `assumeIsolated`
        // asserts it explicitly instead of adding a real `Task` hop for what
        // is, at each of these four call sites, a single non-reentrant flag
        // write.
        let center = NSWorkspace.shared.notificationCenter
        center.addObserver(forName: NSWorkspace.willSleepNotification, object: nil, queue: .main) { [weak self] _ in
            MainActor.assumeIsolated { self?.isSuspended = true }
        }
        center.addObserver(forName: NSWorkspace.screensDidSleepNotification, object: nil, queue: .main) { [weak self] _ in
            MainActor.assumeIsolated { self?.isSuspended = true }
        }
        center.addObserver(forName: NSWorkspace.didWakeNotification, object: nil, queue: .main) { [weak self] _ in
            MainActor.assumeIsolated { self?.isSuspended = false }
        }
        center.addObserver(forName: NSWorkspace.screensDidWakeNotification, object: nil, queue: .main) { [weak self] _ in
            MainActor.assumeIsolated { self?.isSuspended = false }
        }
    }

    // MARK: - Voice signals

    func handle(_ signal: ShipSignal) {
        switch signal {
        case .daemonRecovered:
            isReachable = true
            probeOnce()
        case .daemonWentOffline:
            isReachable = false
            setOffline()
        case .chatStarted:
            isWorking = true
            beginWorking()
        case .chatEnded(let aborted):
            isWorking = false
            endWorking(aborted: aborted)
        }
    }

    /// The one place that decides what the icon should be doing right now,
    /// from the actual state flags rather than from whichever one-shot beat
    /// happens to be finishing. Every one-shot completion (probe, abort
    /// wobble, checkpoint eject/dock) calls this instead of hardcoding a
    /// destination — see finding #1.
    private func settleToCurrentState() {
        if !isReachable {
            setOffline()
        } else if isWorking {
            beginWorking()
        } else {
            playIdleBob()
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
            // Skip the tick's layer write entirely while asleep or in Low
            // Power Mode — cheaper than the alternative of tearing down and
            // re-arming the timer on every notification, and self-correcting
            // the moment either condition clears (no separate "resume"
            // wiring needed for low power, since this re-checks every tick).
            // Low Power Mode's availability on macOS was not independently
            // confirmed this session beyond the documented `ProcessInfo`
            // property itself — see the NOT CONFIRMED list.
            guard !self.isSuspended, !ProcessInfo.processInfo.isLowPowerModeEnabled else { return }
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
        // A recovery probe is a one-shot beat riding on top of whatever is
        // actually happening — if a chat call is genuinely still in flight
        // (a network blip during the 5s reachability poll, call still
        // running), playing the ping here would tear down and then re-drive
        // the working-pulse timer's animation state for no reason. Simplest
        // correct behavior: record the reachability change (already done by
        // the caller) and leave the working animation alone; there is
        // nothing useful to show mid-call anyway. See finding #4.
        guard !isWorking else { return }
        activity = .probing
        let duration = 0.6
        animator.playOnce(duration: duration, completion: { [weak self] in
            self?.settleToCurrentState()
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
            self?.settleToCurrentState()
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
        let deadline = CACurrentMediaTime() + Self.maxDownloadPollDuration
        downloadPollTask = Task { [weak self] in
            guard let self else { return }
            while !Task.isCancelled {
                if CACurrentMediaTime() > deadline {
                    // Gave up: the job never reached a terminal status inside
                    // the ceiling above. Treat it like a failure rather than
                    // polling (and firing outbound HTTP) forever — see
                    // finding #3.
                    await MainActor.run { self.stopWatchingDownload(failed: true) }
                    return
                }
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
            settleToCurrentState()
        }
    }

    /// Restarts the pulse loop on every fresh progress tick (polled every 2s
    /// — see `beginWatchingDownload`), rather than only on first entry into
    /// `.downloading`. The animator's own 45s-per-burst ceiling
    /// (`ShipIconAnimator.defaultMaxLoopDuration`) is far shorter than any
    /// real download, so leaving the original "only start the loop once"
    /// guard in place meant the loop timed out and froze at whatever opacity
    /// it stopped on, then never restarted because `activity` never left
    /// `.downloading` — see finding #2. Restarting here means the animation
    /// only actually reaches that ceiling if progress polling itself stalls
    /// for a full 45s, in which case the timeout below dims to the same
    /// "still going" look `beginWorking` uses, and the next progress tick (if
    /// one arrives) restarts it again.
    private func applyDownloading(progress: Double) {
        activity = .downloading(progress: progress)
        animator.startLoop(onTimeout: { [weak self] in
            self?.animator.apply(opacity: 0.6)
        }) { [weak self] elapsed in
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
        let deadline = CACurrentMediaTime() + Self.maxDispatchPollDuration
        dispatchPollTask = Task { [weak self] in
            guard let self else { return }
            while !Task.isCancelled {
                if CACurrentMediaTime() > deadline {
                    // Never reached "running" inside the ceiling — stop
                    // polling instead of hammering /api/status forever. See
                    // finding #3.
                    await MainActor.run { self.stopWatchingDispatch(confirmed: false) }
                    return
                }
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
            settleToCurrentState()
        }
    }

    /// Same fix as `applyDownloading` above and for the same reason: restart
    /// the loop on every fresh status tick (polled every 3s) instead of only
    /// on first entry into `.remoteDispatch`, so a dispatch that outlives one
    /// 45s animation burst keeps moving instead of freezing. See finding #2.
    private func applyRemoteDispatch() {
        activity = .remoteDispatch(confirmed: false)
        animator.startLoop(onTimeout: { [weak self] in
            self?.animator.apply(opacity: 0.6)
        }) { [weak self] elapsed in
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
            self?.settleToCurrentState()
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
