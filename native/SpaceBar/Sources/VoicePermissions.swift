// VoicePermissions.swift
// Every TCC call the app makes, in one place, off the main actor.
//
// The bug this file exists to kill:
//
// `VoiceDuplexManager` is `@MainActor`. Under Swift 6, a closure literal
// written inside a main-actor context and handed to an Objective-C completion
// handler is *inferred* main-actor-isolated, and the compiler emits a runtime
// executor check at its entry. `SFSpeechRecognizer.requestAuthorization` calls
// its handler on TCC's XPC reply queue, so that check fails and the process
// takes SIGTRAP before a single line of the handler runs:
//
//   dispatch_assert_queue_fail
//   swift_task_isCurrentExecutorWithFlagsImpl
//   closure #1 in VoiceDuplexManager.connect()
//   __TCCAccessRequest_block_invoke.229
//
// Ten reports on 2026-08-28 are that stack, unchanged. It is the "talk and it
// dies" crash: it fires the moment the user first presses Talk.
//
// The fix is that these wrappers are `nonisolated`, so the closures formed
// inside them inherit no isolation and no check is emitted. The result — a
// plain enum value — crosses back to the main actor by `await`, which is the
// hop the compiler was trying to force in the first place.

import AVFoundation
import Speech

/// Where authorization answers come from.
///
/// `.system` asks TCC. The stubs exist so `--dry-run-voice` can drive the
/// whole talk path on a machine with no permission granted and no microphone
/// touched — the two states that used to trap are the two it runs.
enum PermissionSource: Sendable {
    case system
    case stubbed(speech: SFSpeechRecognizerAuthorizationStatus, microphone: AVAuthorizationStatus)

    static let denied = PermissionSource.stubbed(speech: .denied, microphone: .denied)
    static let restricted = PermissionSource.stubbed(speech: .restricted, microphone: .restricted)

    var isStubbed: Bool {
        if case .stubbed = self { return true }
        return false
    }
}

enum VoicePermissions {

    // MARK: Status — read, never prompt

    /// Current speech-recognition status, or `.notDetermined` when we are not
    /// bundled. An unbundled process must not ask: TCC aborts it.
    nonisolated static func speechStatus(_ source: PermissionSource) -> SFSpeechRecognizerAuthorizationStatus {
        switch source {
        case .stubbed(let speech, _):
            return speech
        case .system:
            guard LaunchGuard.isBundled else { return .notDetermined }
            return SFSpeechRecognizer.authorizationStatus()
        }
    }

    nonisolated static func microphoneStatus(_ source: PermissionSource) -> AVAuthorizationStatus {
        switch source {
        case .stubbed(_, let microphone):
            return microphone
        case .system:
            guard LaunchGuard.isBundled else { return .notDetermined }
            return AVCaptureDevice.authorizationStatus(for: .audio)
        }
    }

    // MARK: Request — may prompt, and must not be main-actor-isolated

    /// Ask for speech recognition. `nonisolated`, so the completion handler
    /// carries no executor check and cannot trap on TCC's reply queue.
    nonisolated static func requestSpeech(_ source: PermissionSource) async -> SFSpeechRecognizerAuthorizationStatus {
        if case .stubbed(let speech, _) = source { return speech }
        guard LaunchGuard.isBundled else { return .denied }
        return await withCheckedContinuation { continuation in
            SFSpeechRecognizer.requestAuthorization { status in
                continuation.resume(returning: status)
            }
        }
    }

    /// Ask for the microphone. The async overload does the actor hop for us,
    /// and being called from a `nonisolated` context it forms no isolated
    /// closure at all.
    nonisolated static func requestMicrophone(_ source: PermissionSource) async -> Bool {
        if case .stubbed(_, let microphone) = source { return microphone == .authorized }
        guard LaunchGuard.isBundled else { return false }
        return await AVCaptureDevice.requestAccess(for: .audio)
    }
}
