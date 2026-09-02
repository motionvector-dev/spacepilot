// Snapshot.swift
// Render the real popover offscreen, in every state, in both themes.
//
//   swift run SpaceBar --snapshot /path/to/dir
//
// Why this exists: the popover lives in an NSStatusItem, and driving a menu
// bar extra from a script needs Accessibility permission that a review session
// does not have and should not need. This renders the same SwiftUI view the
// app shows, through the same tokens, with no window server interaction and no
// permission — so a design change can be seen before it is merged, by a person
// or by CI.
//
// It renders states, not behaviour. A screenshot from here proves the view
// draws correctly for a given state; it does not prove the state machine ever
// reaches that state.

import AppKit
import SwiftUI

@MainActor
enum Snapshot {

    /// The states worth looking at, and the filename each one writes.
    static let cases: [(name: String, state: PopoverState)] = [
        ("idle", .idle),
        ("listening", .listening),
        ("thinking", .thinking),
        ("speaking", .speaking),
        ("interrupted", .interrupted),
        ("offline-daemon", .daemonOffline(reason: "Not running on 127.0.0.1:8088")),
        ("no-mic-permission", .needsPermission(.microphone)),
    ]

    /// Returns the output directory if `--snapshot <dir>` was passed.
    static func requestedDirectory() -> URL? {
        let args = CommandLine.arguments
        guard let index = args.firstIndex(of: "--snapshot"), index + 1 < args.count else {
            return nil
        }
        return URL(fileURLWithPath: args[index + 1])
    }

    static func run(into directory: URL) async {
        try? FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)

        // Dark is what ships. Light is rendered too, because tokens.css
        // carries a designed light palette and a screenshot is the only way to
        // know it still holds up.
        let themes: [(String, NSAppearance?)] = [
            ("dark", NSAppearance(named: .darkAqua)),
            ("light", NSAppearance(named: .aqua)),
        ]

        var written = 0
        for (themeName, appearance) in themes {
            for entry in cases {
                let voice = VoiceDuplexManager()
                // Pull the real reading first, so a screenshot shows what this
                // machine actually reports rather than a plausible placeholder.
                // The offline case deliberately skips it.
                if case .daemonOffline = entry.state {} else {
                    await voice.refreshDaemon()
                }
                voice.state = entry.state
                populate(voice, for: entry.state)

                let view = SpaceBarPopoverView(voice: voice)
                let url = directory.appendingPathComponent("\(entry.name)-\(themeName).png")
                if render(view, appearance: appearance, to: url) {
                    written += 1
                    print("wrote \(url.lastPathComponent)")
                }
            }
        }
        print("\(written) snapshots in \(directory.path)")
    }

    /// Give each state the conversation content it would realistically carry,
    /// so a screenshot shows layout under text rather than an empty box.
    private static func populate(_ voice: VoiceDuplexManager, for state: PopoverState) {
        switch state {
        case .idle, .daemonOffline, .needsPermission:
            break
        case .listening:
            voice.lastHeard = "how much headroom have I got"
        case .thinking:
            voice.lastHeard = "how much headroom have I got"
        case .speaking, .interrupted:
            voice.lastHeard = "how much headroom have I got"
            voice.lastSaid = "Apple M1 Max · nominal · mlx · 20.5 GB usable · nothing loaded."
        }
    }

    private static func render(_ view: some View, appearance: NSAppearance?, to url: URL) -> Bool {
        let hosting = NSHostingView(rootView: view)
        hosting.appearance = appearance
        hosting.frame = NSRect(origin: .zero, size: hosting.fittingSize)
        hosting.layoutSubtreeIfNeeded()

        guard hosting.bounds.width > 0, hosting.bounds.height > 0,
              let rep = hosting.bitmapImageRepForCachingDisplay(in: hosting.bounds) else {
            return false
        }
        hosting.cacheDisplay(in: hosting.bounds, to: rep)
        guard let png = rep.representation(using: .png, properties: [:]) else { return false }
        do {
            try png.write(to: url)
            return true
        } catch {
            print("snapshot: \(url.lastPathComponent) — \(error.localizedDescription)")
            return false
        }
    }
}
