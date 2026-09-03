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
            Task { @MainActor in
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
            Task { @MainActor in
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
            Task { @MainActor in
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
    func apply(translationX: CGFloat = 0, translationY: CGFloat = 0, rotationRadians: CGFloat = 0, opacity: Float = 1.0) {
        guard let layer = button?.layer else { return }
        var transform = CATransform3DIdentity
        transform = CATransform3DTranslate(transform, translationX, translationY, 0)
        transform = CATransform3DRotate(transform, rotationRadians, 0, 0, 1)
        CATransaction.begin()
        CATransaction.setDisableActions(true)
        layer.transform = transform
        layer.opacity = opacity
        CATransaction.commit()
    }
}
