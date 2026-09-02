// DryRunVoice.swift
// Drive the whole talk path with permissions stubbed, and assert no crash.
//
//   swift run SpaceBar --dry-run-voice
//
// It exists because the crash it guards cannot be reached by any other test.
// Pressing Talk needs a menu bar, a click, and a real TCC prompt; the two
// answers that used to trap — denied and restricted — need a machine where
// permission has been refused. So the permission source is a parameter, this
// pins it to each of those answers in turn, and runs the same code the button
// runs.
//
// It touches no microphone, opens no System Settings, and speaks nothing
// aloud. `PermissionSource.isStubbed` is what those three guards read.

import AppKit
import Foundation

@MainActor
enum DryRunVoice {

    static func isRequested() -> Bool {
        CommandLine.arguments.contains("--dry-run-voice")
    }

    /// Runs the ladder for every stubbed answer, then exits 0 or 1.
    /// AppKit is initialised but no window, status item or popover is created.
    static func run() {
        let cases: [(String, PermissionSource, PopoverState.PermissionGap)] = [
            ("denied", .denied, .speechRecognition),
            ("restricted", .restricted, .speechRecognition),
            ("microphone-denied",
             .stubbed(speech: .authorized, microphone: .denied),
             .microphone),
            ("microphone-restricted",
             .stubbed(speech: .authorized, microphone: .restricted),
             .microphone),
        ]

        var failures: [String] = []

        Task { @MainActor in
            for (name, source, expected) in cases {
                let problems = await exercise(name: name, source: source, expected: expected)
                failures.append(contentsOf: problems)
            }

            // The granted path too, so the audio-graph branch is entered at
            // least once. It stops at the stub guard rather than opening a
            // device, but everything before that guard is the real code.
            let granted = await exercise(
                name: "granted",
                source: .stubbed(speech: .authorized, microphone: .authorized),
                expected: nil
            )
            failures.append(contentsOf: granted)

            if failures.isEmpty {
                print("dry-run-voice: ok — \(cases.count + 1) permission paths, no crash")
                exit(0)
            }
            for failure in failures { print("dry-run-voice: FAIL — \(failure)") }
            exit(1)
        }

        // The work above is main-actor async; the run loop is what lets it run.
        // `exit` inside the task is the only way out.
        RunLoop.main.run()
    }

    /// One permission answer, through every entry point a user can reach.
    private static func exercise(
        name: String,
        source: PermissionSource,
        expected: PopoverState.PermissionGap?
    ) async -> [String] {
        var problems: [String] = []
        let voice = VoiceDuplexManager(permissions: source)

        // The status read the popover does on every poll.
        voice.refreshPermission()

        // The button, pressed. This is the call that used to SIGTRAP.
        await voice.startListening()
        let settled = voice.state
        print("dry-run-voice: \(name) → \(settled.headline)")

        if let expected {
            guard case .needsPermission(let gap) = voice.state else {
                problems.append("\(name): expected needsPermission, got \(voice.state)")
                return problems
            }
            if gap != expected {
                problems.append("\(name): expected \(expected), got \(gap)")
            }
        } else if case .needsPermission = voice.state {
            problems.append("\(name): authorized stub still reported a permission gap")
        }

        // The button pressed again in whatever state that left. In the denied
        // states this is the Open Settings branch, which the stub must not open.
        voice.toggleConnection()

        // Teardown, including the input-node reach that raises on a Mac with
        // no input device.
        voice.stopListening()

        // The answer path with no model call: it must degrade, not trap.
        voice.state = .listening
        voice.lastHeard = "how much headroom have I got"

        return problems
    }
}
