#!/usr/bin/env python3
"""Generate Sources/Tokens.swift from web/spacebar/tokens.css.

One source of colour. The CSS file is authored; the Swift file is not.
Run after editing tokens.css:

    python3 native/SpaceBar/tools/gen_tokens.py

--check exits 1 if the committed Swift file is stale, so CI or a hook can
notice drift instead of a reviewer noticing it.

The parser is deliberately small: it reads the two palette blocks it needs
by their exact selector, so a token that exists in only one of them is a
hard error rather than a silently half-themed colour.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
CSS = REPO / "web" / "spacebar" / "tokens.css"
SWIFT = REPO / "native" / "SpaceBar" / "Sources" / "Tokens.swift"

LIGHT_SELECTOR = ":root"
DARK_SELECTOR = ':root[data-theme="dark"]'

# Only these reach Swift. The aliases and the gold alternate stay in CSS:
# the app names colours by role, and an alias would give one colour two names.
EXPORT = [
    ("mv-ground", "ground", "The popover's own background."),
    ("mv-surface", "surface", "A panel sitting on the ground."),
    ("mv-surface-2", "surface2", "A card inside a panel."),
    ("mv-surface-3", "surface3", "The raised step: a pressed control, a filled track."),
    ("mv-border", "border", "The default hairline."),
    ("mv-border-soft", "borderSoft", "A divider that should barely register."),
    ("mv-border-strong", "borderStrong", "The one hairline that has to be seen."),
    ("mv-ink", "ink", "Headline and primary text."),
    ("mv-text", "text", "Body text."),
    ("mv-muted", "muted", "Secondary text and labels."),
    ("mv-faint", "faint", "Quiet states: offline, asleep, stale, unread."),
    ("mv-accent", "accent", "The one accent. Violet. Use it where it is earned."),
    ("mv-accent-soft", "accentSoft", "An accent wash behind content."),
    ("mv-accent-border", "accentBorder", "An accent hairline."),
    ("mv-accent-contrast", "accentContrast", "Text sitting on a solid accent fill."),
    ("mv-true", "true_", "Measured and healthy. Never a guess wearing green."),
    ("mv-wrong", "wrong", "A real failure."),
]

HEADER = """// Tokens.swift — GENERATED. Do not edit.
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
"""


def strip_comments(text: str) -> str:
    return re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)


def block_bodies(css: str, selector: str) -> list[str]:
    """Every top-level block whose selector list is exactly `selector`."""
    bodies = []
    for match in re.finditer(r"([^{}]*)\{([^{}]*)\}", css):
        head = " ".join(match.group(1).split())
        if head == selector:
            bodies.append(match.group(2))
    return bodies


def declarations(css: str, selector: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for body in block_bodies(css, selector):
        for decl in body.split(";"):
            if ":" not in decl:
                continue
            name, _, value = decl.partition(":")
            name = name.strip()
            if name.startswith("--"):
                out[name[2:]] = value.strip()
    return out


def to_swift_color(value: str, token: str) -> str:
    value = value.strip()
    hexmatch = re.fullmatch(r"#([0-9a-fA-F]{6})", value)
    if hexmatch:
        h = hexmatch.group(1)
        r, g, b = (int(h[i : i + 2], 16) / 255.0 for i in (0, 2, 4))
        return f"rgba({r:.5f}, {g:.5f}, {b:.5f}, 1.0)"
    rgbamatch = re.fullmatch(
        r"rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*(?:,\s*([\d.]+)\s*)?\)", value
    )
    if rgbamatch:
        r, g, b = (int(rgbamatch.group(i)) / 255.0 for i in (1, 2, 3))
        a = float(rgbamatch.group(4) or 1.0)
        return f"rgba({r:.5f}, {g:.5f}, {b:.5f}, {a})"
    raise SystemExit(f"gen_tokens: --{token} is {value!r}; expected #rrggbb or rgba().")


def render() -> str:
    css = strip_comments(CSS.read_text())
    light = declarations(css, LIGHT_SELECTOR)
    dark = declarations(css, DARK_SELECTOR)

    missing = [t for t, _, _ in EXPORT if t not in light or t not in dark]
    if missing:
        raise SystemExit(
            "gen_tokens: these tokens are not defined in both "
            f"`{LIGHT_SELECTOR}` and `{DARK_SELECTOR}`: {', '.join(missing)}"
        )

    lines = [HEADER, "", "    // MARK: - Palette", ""]
    for token, swift, doc in EXPORT:
        opening = f"    static let {swift} = dynamic("
        lines.append(f"    /// {doc}")
        lines.append(f"{opening}light: {to_swift_color(light[token], token)},")
        lines.append(f"{' ' * len(opening)}dark: {to_swift_color(dark[token], token)})")
        lines.append("")

    lines.append("    // MARK: - SwiftUI")
    lines.append("")
    lines.append("    enum UI {")
    for _, swift, _ in EXPORT:
        lines.append(f"        static let {swift} = Color(nsColor: Tokens.{swift})")
    lines.append("    }")
    lines.append("}")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check", action="store_true", help="exit 1 if Tokens.swift is stale"
    )
    args = parser.parse_args()

    generated = render()
    if args.check:
        current = SWIFT.read_text() if SWIFT.exists() else ""
        if current != generated:
            print(
                f"Tokens.swift is stale. Run: python3 {Path(__file__).relative_to(REPO)}",
                file=sys.stderr,
            )
            return 1
        print("Tokens.swift matches tokens.css.")
        return 0

    SWIFT.parent.mkdir(parents=True, exist_ok=True)
    SWIFT.write_text(generated)
    print(f"Wrote {SWIFT.relative_to(REPO)} — {len(EXPORT)} tokens, light and dark.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
