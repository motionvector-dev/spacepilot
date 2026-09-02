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
// the effective appearance at draw time. Light is the default; dark is the
// override. Setting NSApp.appearance re-resolves every one of them.

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

    /// The popover's own background.
    static let ground = dynamic(light: rgba(1.00000, 1.00000, 1.00000, 1.0),
                                dark: rgba(0.00000, 0.00000, 0.00000, 1.0))

    /// A panel sitting on the ground.
    static let surface = dynamic(light: rgba(0.95686, 0.95686, 0.96078, 1.0),
                                 dark: rgba(0.09412, 0.09412, 0.10588, 1.0))

    /// A card inside a panel.
    static let surface2 = dynamic(light: rgba(0.93725, 0.93725, 0.94510, 1.0),
                                  dark: rgba(0.11373, 0.11373, 0.12549, 1.0))

    /// The raised step: a pressed control, a filled track.
    static let surface3 = dynamic(light: rgba(0.89412, 0.89412, 0.90588, 1.0),
                                  dark: rgba(0.15294, 0.15294, 0.16471, 1.0))

    /// The default hairline.
    static let border = dynamic(light: rgba(0.89412, 0.89412, 0.90588, 1.0),
                                dark: rgba(0.16471, 0.16471, 0.17647, 1.0))

    /// A divider that should barely register.
    static let borderSoft = dynamic(light: rgba(0.92549, 0.92549, 0.93333, 1.0),
                                    dark: rgba(0.10980, 0.10980, 0.12157, 1.0))

    /// The one hairline that has to be seen.
    static let borderStrong = dynamic(light: rgba(0.83137, 0.83137, 0.84706, 1.0),
                                      dark: rgba(0.24706, 0.24706, 0.27451, 1.0))

    /// Headline and primary text.
    static let ink = dynamic(light: rgba(0.06667, 0.06667, 0.07451, 1.0),
                             dark: rgba(1.00000, 1.00000, 1.00000, 1.0))

    /// Body text.
    static let text = dynamic(light: rgba(0.24706, 0.24706, 0.27451, 1.0),
                              dark: rgba(0.83137, 0.83137, 0.84706, 1.0))

    /// Secondary text and labels.
    static let muted = dynamic(light: rgba(0.32157, 0.32157, 0.35686, 1.0),
                               dark: rgba(0.63137, 0.63137, 0.66667, 1.0))

    /// Quiet states: offline, asleep, stale, unread.
    static let faint = dynamic(light: rgba(0.63137, 0.63137, 0.66667, 1.0),
                               dark: rgba(0.32157, 0.32157, 0.35686, 1.0))

    /// The one accent. Violet. Use it where it is earned.
    static let accent = dynamic(light: rgba(0.48627, 0.41961, 0.70196, 1.0),
                                dark: rgba(0.63922, 0.58824, 0.83922, 1.0))

    /// An accent wash behind content.
    static let accentSoft = dynamic(light: rgba(0.48627, 0.41961, 0.70196, 0.08),
                                    dark: rgba(0.63922, 0.58824, 0.83922, 0.1))

    /// An accent hairline.
    static let accentBorder = dynamic(light: rgba(0.48627, 0.41961, 0.70196, 0.28),
                                      dark: rgba(0.63922, 0.58824, 0.83922, 0.3))

    /// Text sitting on a solid accent fill.
    static let accentContrast = dynamic(light: rgba(1.00000, 1.00000, 1.00000, 1.0),
                                        dark: rgba(0.05098, 0.05098, 0.05882, 1.0))

    /// Measured and healthy. Never a guess wearing green.
    static let true_ = dynamic(light: rgba(0.01961, 0.58824, 0.41176, 1.0),
                               dark: rgba(0.06275, 0.72549, 0.50588, 1.0))

    /// A real failure.
    static let wrong = dynamic(light: rgba(0.88235, 0.11373, 0.28235, 1.0),
                               dark: rgba(0.95686, 0.20784, 0.20784, 1.0))

    // MARK: - SwiftUI

    enum UI {
        static let ground = Color(nsColor: Tokens.ground)
        static let surface = Color(nsColor: Tokens.surface)
        static let surface2 = Color(nsColor: Tokens.surface2)
        static let surface3 = Color(nsColor: Tokens.surface3)
        static let border = Color(nsColor: Tokens.border)
        static let borderSoft = Color(nsColor: Tokens.borderSoft)
        static let borderStrong = Color(nsColor: Tokens.borderStrong)
        static let ink = Color(nsColor: Tokens.ink)
        static let text = Color(nsColor: Tokens.text)
        static let muted = Color(nsColor: Tokens.muted)
        static let faint = Color(nsColor: Tokens.faint)
        static let accent = Color(nsColor: Tokens.accent)
        static let accentSoft = Color(nsColor: Tokens.accentSoft)
        static let accentBorder = Color(nsColor: Tokens.accentBorder)
        static let accentContrast = Color(nsColor: Tokens.accentContrast)
        static let true_ = Color(nsColor: Tokens.true_)
        static let wrong = Color(nsColor: Tokens.wrong)
    }
}
