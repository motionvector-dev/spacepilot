// ShipGlyph.swift
// The menu bar icon's artwork, isolated from its animation and its state
// machine (ShipIconAnimator, ShipActivity). Swapping the silhouette for a
// real design pass later means replacing this one function — nothing else
// in the app needs to change.

import AppKit

enum ShipGlyph {
    static let size = NSSize(width: 18, height: 14)

    /// A simple side-profile ship silhouette: nose, hull, a swallowtail
    /// stern, and one small ventral fin. Placeholder art — the exact shape
    /// doesn't matter yet, only that it reads as a ship rather than the
    /// generic chevron it replaces.
    static func path() -> NSBezierPath {
        let path = NSBezierPath()

        // Hull: nose at the right, swept back to a swallowtail stern at the
        // left, exactly like a paper-airplane dart in profile.
        path.move(to: NSPoint(x: 17, y: 7))
        path.line(to: NSPoint(x: 1, y: 13))
        path.line(to: NSPoint(x: 7, y: 7))
        path.line(to: NSPoint(x: 1, y: 1))
        path.close()

        // A small ventral fin, roughly amidships.
        path.move(to: NSPoint(x: 10, y: 7))
        path.line(to: NSPoint(x: 7, y: 2))
        path.line(to: NSPoint(x: 11, y: 5))
        path.close()

        return path
    }

    /// A template image, so the menu bar tints it for us and it reads
    /// correctly on a light bar, a dark bar, and behind a wallpaper. A
    /// hardcoded fill color could do none of those — see the same note on
    /// the chevron this replaces.
    static func templateImage() -> NSImage {
        let image = NSImage(size: size, flipped: false) { _ in
            NSColor.black.setFill()
            path().fill()
            return true
        }
        image.isTemplate = true
        return image
    }
}
