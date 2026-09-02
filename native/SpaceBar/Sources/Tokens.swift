// Tokens.swift — GENERATED. Do not edit.
//
// Source:    web/spacebar/tokens.css
// Generator: native/SpaceBar/tools/gen_tokens.py
//
// Every colour in SpaceBar is written down once, in the CSS file, so the
// Swift popover and the web mockups cannot drift apart. To change a colour,
// edit the CSS and rerun the generator.
//
// Each token is an NSColor with a dynamic provider, so it resolves against
// the effective appearance at draw time. Dark is the product (DESIGN.md,
// "Obsidian Dark Precision") and the app forces it; the light values are the
// designed opt-in, kept so unforcing it later needs no new colour work.

import AppKit
import SwiftUI

enum Tokens {

    /// A colour that resolves itself against whatever appearance is drawing.
    static func dynamic(light: NSColor, dark: NSColor) -> NSColor {
        NSColor(name: nil) { appearance in
            let match = appearance.bestMatch(from: [.aqua, .darkAqua])
            return match == .darkAqua ? dark : light
        }
    }

    static func rgba(_ r: Double, _ g: Double, _ b: Double, _ a: Double) -> NSColor {
        NSColor(srgbRed: r, green: g, blue: b, alpha: a)
    }


    // MARK: - Palette

    /// True black. The deepest step, behind everything.
    static let root = dynamic(light: rgba(0.99216, 0.99216, 0.98824, 1.0),
                              dark: rgba(0.00000, 0.00000, 0.00000, 1.0))

    /// The app's ground.
    static let ground = dynamic(light: rgba(0.96863, 0.96863, 0.96078, 1.0),
                                dark: rgba(0.03529, 0.03529, 0.04314, 1.0))

    /// The popover's own surface.
    static let panel = dynamic(light: rgba(0.94902, 0.94902, 0.93725, 1.0),
                               dark: rgba(0.06667, 0.06667, 0.07843, 1.0))

    /// A card inside the popover.
    static let card = dynamic(light: rgba(1.00000, 1.00000, 1.00000, 1.0),
                              dark: rgba(0.09412, 0.09412, 0.10588, 1.0))

    /// The raised step: a pressed control, a filled track.
    static let raised = dynamic(light: rgba(0.90196, 0.90196, 0.88235, 1.0),
                                dark: rgba(0.13333, 0.13333, 0.14902, 1.0))

    /// A divider that should barely register.
    static let line = dynamic(light: rgba(0.00000, 0.00000, 0.00000, 0.08),
                              dark: rgba(1.00000, 1.00000, 1.00000, 0.08))

    /// The default hairline.
    static let line2 = dynamic(light: rgba(0.00000, 0.00000, 0.00000, 0.14),
                               dark: rgba(1.00000, 1.00000, 1.00000, 0.14))

    /// The one hairline that has to be seen.
    static let line3 = dynamic(light: rgba(0.00000, 0.00000, 0.00000, 0.22),
                               dark: rgba(1.00000, 1.00000, 1.00000, 0.22))

    /// Headline and primary text.
    static let ink = dynamic(light: rgba(0.03529, 0.03529, 0.04314, 1.0),
                             dark: rgba(0.98039, 0.98039, 0.98039, 1.0))

    /// Body text.
    static let ink2 = dynamic(light: rgba(0.32157, 0.32157, 0.35686, 1.0),
                              dark: rgba(0.63137, 0.63137, 0.66667, 1.0))

    /// Secondary text and labels.
    static let ink3 = dynamic(light: rgba(0.44314, 0.44314, 0.47843, 1.0),
                              dark: rgba(0.44314, 0.44314, 0.47843, 1.0))

    /// Quiet states: offline, asleep, stale, nothing to report.
    static let ink4 = dynamic(light: rgba(0.63137, 0.63137, 0.66667, 1.0),
                              dark: rgba(0.32157, 0.32157, 0.35686, 1.0))

    /// The attention colour. Where the eye is meant to go.
    static let gold = dynamic(light: rgba(0.54118, 0.41569, 0.13333, 1.0),
                              dark: rgba(0.78824, 0.63529, 0.15294, 1.0))

    /// A gold hairline.
    static let goldLine = dynamic(light: rgba(0.54118, 0.41569, 0.13333, 0.34),
                                  dark: rgba(0.78824, 0.63529, 0.15294, 0.4))

    /// The machine's own colour: hardware readouts.
    static let silver = dynamic(light: rgba(0.36078, 0.40000, 0.44706, 1.0),
                                dark: rgba(0.81176, 0.83137, 0.86275, 1.0))

    /// A silver hairline.
    static let silverLine = dynamic(light: rgba(0.36078, 0.40000, 0.44706, 0.32),
                                    dark: rgba(0.81176, 0.83137, 0.86275, 0.3))

    /// Anything an agent or a remote model said or did.
    static let agent = dynamic(light: rgba(0.35686, 0.32157, 0.56078, 1.0),
                               dark: rgba(0.64314, 0.60784, 0.81569, 1.0))

    /// Measured and healthy. Never a guess wearing green.
    static let true_ = dynamic(light: rgba(0.01961, 0.58824, 0.41176, 1.0),
                               dark: rgba(0.06275, 0.72549, 0.50588, 1.0))

    /// Known, but stale or asleep.
    static let amber = dynamic(light: rgba(0.70588, 0.32549, 0.03529, 1.0),
                               dark: rgba(0.96078, 0.61961, 0.04314, 1.0))

    /// A real failure.
    static let wrong = dynamic(light: rgba(0.88235, 0.11373, 0.28235, 1.0),
                               dark: rgba(0.95686, 0.24706, 0.36863, 1.0))

    /// Machine fill, darkest stop.
    static let chrome1 = dynamic(light: rgba(0.12941, 0.15294, 0.18431, 1.0),
                                 dark: rgba(0.32941, 0.36078, 0.40392, 1.0))

    /// Machine fill, middle stop.
    static let chrome2 = dynamic(light: rgba(0.26275, 0.29804, 0.34510, 1.0),
                                 dark: rgba(0.65490, 0.69020, 0.73725, 1.0))

    /// Machine fill, lightest stop.
    static let chrome3 = dynamic(light: rgba(0.44314, 0.49020, 0.54902, 1.0),
                                 dark: rgba(0.90980, 0.92941, 0.95686, 1.0))

    // MARK: - SwiftUI

    enum UI {
        static let root = Color(nsColor: Tokens.root)
        static let ground = Color(nsColor: Tokens.ground)
        static let panel = Color(nsColor: Tokens.panel)
        static let card = Color(nsColor: Tokens.card)
        static let raised = Color(nsColor: Tokens.raised)
        static let line = Color(nsColor: Tokens.line)
        static let line2 = Color(nsColor: Tokens.line2)
        static let line3 = Color(nsColor: Tokens.line3)
        static let ink = Color(nsColor: Tokens.ink)
        static let ink2 = Color(nsColor: Tokens.ink2)
        static let ink3 = Color(nsColor: Tokens.ink3)
        static let ink4 = Color(nsColor: Tokens.ink4)
        static let gold = Color(nsColor: Tokens.gold)
        static let goldLine = Color(nsColor: Tokens.goldLine)
        static let silver = Color(nsColor: Tokens.silver)
        static let silverLine = Color(nsColor: Tokens.silverLine)
        static let agent = Color(nsColor: Tokens.agent)
        static let true_ = Color(nsColor: Tokens.true_)
        static let amber = Color(nsColor: Tokens.amber)
        static let wrong = Color(nsColor: Tokens.wrong)
        static let chrome1 = Color(nsColor: Tokens.chrome1)
        static let chrome2 = Color(nsColor: Tokens.chrome2)
        static let chrome3 = Color(nsColor: Tokens.chrome3)
    }
}
