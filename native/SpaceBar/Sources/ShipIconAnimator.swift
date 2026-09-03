// ShipIconAnimator.swift
// Drives the menu bar button's own CALayer transform and opacity to animate
// the ship glyph — independent of whatever NSImage is loaded into the
// button, which stays the static template image from ShipGlyph.
//
// The one hard constraint (CodexBar's own documented lesson, repeated here
// because it is easy to forget under the next feature deadline): a status
// item redraw is expensive, so every looping animation ticks at a bounded
// rate — 12fps, as a plain Timer setting the transform directly each tick,
// never a CABasicAnimation left to interpolate on its own schedule. And
// anything that could in principle run indefinitely (a hung stream, a
// stalled download) gets a hard ceiling: past it, the loop stops moving and
// falls back to a static "still going" look rather than spinning forever.
//
// The idle bob is the one exception on purpose — see ShipIconController.

import AppKit
import QuartzCore

@MainActor
final class ShipIconAnimator {
    private static let frameInterval: TimeInterval = 1.0 / 12.0
    /// Ceiling for one bounded loop burst. Not a ceiling on the underlying
    /// operation — a chat call can legitimately run the length of
    /// DaemonClient's 120s timeout — only on how long the animation itself
    /// keeps moving before it settles into a static "still going" state.
    static let defaultMaxLoopDuration: TimeInterval = 45.0

    private weak var button: NSStatusBarButton?
    private var timer: Timer?
    private var startTime: CFTimeInterval = 0

    init(button: NSStatusBarButton) {
        self.button = button
        button.wantsLayer = true
    }

    /// Runs `tick` at the bounded rate until `stop()`, or until
    /// `maxDuration` elapses, at which point `onTimeout` fires once and the
    /// loop stops itself (the layer is left wherever `onTimeout` puts it,
    /// not reset to identity — that is `onTimeout`'s job if it wants that).
    func startLoop(
        maxDuration: TimeInterval = ShipIconAnimator.defaultMaxLoopDuration,
        onTimeout: (@MainActor () -> Void)? = nil,
        tick: @escaping @MainActor (CFTimeInterval) -> Void
    ) {
        stopTimer()
        startTime = CACurrentMediaTime()
        timer = Timer.scheduledTimer(withTimeInterval: Self.frameInterval, repeats: true) { [weak self] _ in
            guard let self else { return }
            // `Timer` scheduled on `RunLoop.main` already fires on the main
            // thread — the `Task { @MainActor in ... }` hop this used to
            // wrap the body in was redundant, and worse: it let a tick that
            // was already in flight when a state-changing call (e.g.
            // `setOffline()`) ran synchronously on the main thread execute
            // *after* it, silently overwriting the layer that call had just
            // set. `assumeIsolated` asserts the actor context this closure
            // is already running in without another suspension point, so
            // ticks and state changes stay ordered the way they were
            // scheduled. See finding #5.
            MainActor.assumeIsolated {
                let elapsed = CACurrentMediaTime() - self.startTime
                if elapsed > maxDuration {
                    self.stopTimer()
                    onTimeout?()
                    return
                }
                tick(elapsed)
            }
        }
        if let timer { RunLoop.main.add(timer, forMode: .common) }
    }

    /// Runs `tick` at the bounded rate for exactly `duration`, then calls
    /// `completion` once and resets the layer to identity. One-shot beats
    /// (probe ping, checkpoint eject/dock, abort wobble) are inherently
    /// time-limited by definition, so they need no separate ceiling — keep
    /// `duration` under ~2s by convention.
    func playOnce(
        duration: TimeInterval,
        completion: (@MainActor () -> Void)? = nil,
        tick: @escaping @MainActor (CFTimeInterval) -> Void
    ) {
        stopTimer()
        startTime = CACurrentMediaTime()
        timer = Timer.scheduledTimer(withTimeInterval: Self.frameInterval, repeats: true) { [weak self] _ in
            guard let self else { return }
            // See the matching comment in `startLoop` — same redundant hop,
            // same fix.
            MainActor.assumeIsolated {
                let elapsed = CACurrentMediaTime() - self.startTime
                if elapsed >= duration {
                    self.stop()
                    completion?()
                    return
                }
                tick(elapsed)
            }
        }
        if let timer { RunLoop.main.add(timer, forMode: .common) }
    }

    /// An always-on, unbounded loop — used only for the idle bob, which is
    /// cheap enough (a few px of translation, a small opacity variation)
    /// that the timeout ceiling above does not apply to it. See
    /// `ShipIconController.playIdleBob` for the amplitude and period that
    /// keep this trivial, and the NOT CONFIRMED note in the PR body: nothing
    /// in this worktree can run the app to measure the actual CPU cost.
    func startIdleLoop(tick: @escaping @MainActor (CFTimeInterval) -> Void) {
        stopTimer()
        startTime = CACurrentMediaTime()
        timer = Timer.scheduledTimer(withTimeInterval: Self.frameInterval, repeats: true) { [weak self] _ in
            guard let self else { return }
            // See the matching comment in `startLoop` — same redundant hop,
            // same fix.
            MainActor.assumeIsolated {
                tick(CACurrentMediaTime() - self.startTime)
            }
        }
        if let timer { RunLoop.main.add(timer, forMode: .common) }
    }

    /// Stops any running loop and resets the layer to identity — the button
    /// image itself is untouched.
    func stop() {
        stopTimer()
        button?.layer?.transform = CATransform3DIdentity
        button?.layer?.opacity = 1.0
    }

    private func stopTimer() {
        timer?.invalidate()
        timer = nil
    }

    /// Sets the button layer's transform and opacity directly — no implicit
    /// animation, so the cost of one call is exactly one composited frame,
    /// which is what keeps the bounded-rate ticks above cheap.
    ///
    /// Recenters `anchorPoint` first on every call — see `recenterAnchorIfNeeded`
    /// for why this has to happen here rather than once in `init`.
    func apply(translationX: CGFloat = 0, translationY: CGFloat = 0, rotationRadians: CGFloat = 0, opacity: Float = 1.0) {
        guard let layer = button?.layer else { return }
        CATransaction.begin()
        CATransaction.setDisableActions(true)
        recenterAnchorIfNeeded(layer)
        var transform = CATransform3DIdentity
        transform = CATransform3DTranslate(transform, translationX, translationY, 0)
        transform = CATransform3DRotate(transform, rotationRadians, 0, 0, 1)
        layer.transform = transform
        layer.opacity = opacity
        CATransaction.commit()
    }

    /// Finding #6, empirically confirmed this session (not reasoned from
    /// docs) with a standalone `NSStatusItem` probe outside this app: a
    /// fresh `NSStatusBarButton`'s backing layer has `anchorPoint = (0, 0)`,
    /// not the `(0.5, 0.5)` a plain `CALayer` defaults to — so
    /// `CATransform3DRotate` (the abort wobble) pivots around the glyph's
    /// bottom-left corner, producing a sideways swing rather than a rock in
    /// place, exactly as flagged. The same probe also confirmed AppKit
    /// resets `anchorPoint`, `position`, *and* `transform` back to their
    /// view-derived defaults on its own layout passes (observed by forcing
    /// one via `NSStatusItem.length` changes) — so a one-time fix in `init`
    /// would not survive the app's lifetime. `opacity` was not reset by the
    /// same probe, which is why `.offline`'s static dim doesn't need this
    /// treatment.
    ///
    /// A dedicated sublayer (per the review's suggestion) would sidestep
    /// AppKit's syncing entirely, but would also mean duplicating the
    /// template-image glyph outside the button's own cell rendering, which
    /// currently gets light/dark menu-bar tinting for free — a real
    /// re-architecture, not a bug fix. Recentering here instead piggybacks
    /// on the pattern this file already uses for `transform` itself: redo it
    /// on every tick so an occasional AppKit reset self-heals within one
    /// frame (~83ms at 12fps) instead of needing to survive indefinitely.
    private func recenterAnchorIfNeeded(_ layer: CALayer) {
        let centered = CGPoint(x: 0.5, y: 0.5)
        guard layer.anchorPoint != centered else { return }
        let size = layer.bounds.size
        let old = layer.anchorPoint
        layer.position = CGPoint(
            x: layer.position.x + (centered.x - old.x) * size.width,
            y: layer.position.y + (centered.y - old.y) * size.height
        )
        layer.anchorPoint = centered
    }
}
