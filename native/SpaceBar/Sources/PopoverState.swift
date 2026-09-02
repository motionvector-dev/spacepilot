// PopoverState.swift
// The seven states the popover can be in, and the one rule for reading them.
// Written down in docs/design/SPACEBAR.md; this enum is that table in code.

import Foundation

/// What the popover is doing right now. Exactly one of these is true.
///
/// The ordering matters when two could apply at once: a missing microphone
/// permission outranks a missing daemon, because the user can fix the first
/// one and the second one does not stop them talking.
enum PopoverState: Equatable {
    /// No microphone or speech permission. Nothing works until this is fixed.
    case needsPermission(PermissionGap)
    /// The daemon is not answering on 127.0.0.1:8088. Voice still works;
    /// fleet data does not, and the popover says so rather than showing zeros.
    case daemonOffline(reason: String)
    /// Ready. Not listening, not speaking.
    case idle
    /// The microphone is open and the user is talking.
    case listening
    /// The user stopped; the model is composing a reply.
    case thinking
    /// SpaceBar is speaking the reply aloud.
    case speaking
    /// The user talked over the reply, so it was cut off mid-sentence.
    case interrupted

    enum PermissionGap: Equatable {
        case microphone
        case speechRecognition

        var label: String {
            switch self {
            case .microphone: return "Microphone access is off"
            case .speechRecognition: return "Speech recognition is off"
            }
        }

        /// The System Settings pane that fixes it.
        var settingsURL: URL? {
            switch self {
            case .microphone:
                return URL(string: "x-apple.systempreferences:com.apple.preference.security?Privacy_Microphone")
            case .speechRecognition:
                return URL(string: "x-apple.systempreferences:com.apple.preference.security?Privacy_SpeechRecognition")
            }
        }
    }

    /// The short line in the popover header. Never a number, never a promise.
    var headline: String {
        switch self {
        case .needsPermission(let gap): return gap.label
        case .daemonOffline: return "SpacePilot is not running"
        case .idle: return "Ready"
        case .listening: return "Listening"
        case .thinking: return "Thinking"
        case .speaking: return "Speaking"
        case .interrupted: return "Stopped"
        }
    }

    /// True while the accent ring is drawn. Only inference earns it.
    var isWorking: Bool {
        if case .thinking = self { return true }
        return false
    }

    /// True while the microphone is actually open, so the popover can show a
    /// mic-open indicator that is driven by the audio graph and not by hope.
    var isMicrophoneOpen: Bool {
        switch self {
        case .listening, .speaking, .thinking, .interrupted: return true
        case .idle, .daemonOffline, .needsPermission: return false
        }
    }

    /// What the primary button says. One button, one verb.
    var primaryAction: String? {
        switch self {
        case .needsPermission: return "Open Settings"
        case .daemonOffline: return "Retry"
        case .idle: return "Talk"
        case .listening, .thinking: return "Stop"
        case .speaking, .interrupted: return "Talk"
        }
    }
}
