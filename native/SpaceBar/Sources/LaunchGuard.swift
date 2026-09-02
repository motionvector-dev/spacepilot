// LaunchGuard.swift
// Why `swift run SpaceBar` must refuse to start.
//
// A SwiftPM executable is a bare Mach-O with no bundle, so `Bundle.main` has
// no Info.plist and no usage strings. The first TCC-guarded call — and
// `SFSpeechRecognizer.authorizationStatus()` at launch is one — does not
// return an error and does not prompt. TCC SIGABRTs the process:
//
//   namespace TCC, "This app has crashed because it attempted to access
//   privacy-sensitive data without a usage description."
//
// That is report 3D581B3D-C049-45D8-8256-CFA58B21660D. Nothing in Swift can
// catch it. The only fix is to be a real bundle, so this checks for one and
// says which script builds it rather than letting macOS kill us.

import Foundation

enum LaunchGuard {
    /// The keys macOS demands before it will even show a prompt.
    static let requiredUsageKeys = [
        "NSSpeechRecognitionUsageDescription",
        "NSMicrophoneUsageDescription",
    ]

    /// True only when this process is a real bundle carrying both usage
    /// strings. Every TCC-guarded call in the app is gated on this, so an
    /// unbundled build degrades to the no-mic-permission state instead of
    /// aborting.
    static let isBundled: Bool = {
        guard let info = Bundle.main.infoDictionary else { return false }
        return requiredUsageKeys.allSatisfy { key in
            (info[key] as? String)?.isEmpty == false
        }
    }()

    static let message = """
        SpaceBar cannot run as a bare executable.

        macOS kills any process that touches the microphone or speech
        recognition without an Info.plist carrying:

          NSSpeechRecognitionUsageDescription
          NSMicrophoneUsageDescription

        Build and open the real app instead:

          native/SpaceBar/tools/make_app.sh

        To exercise the voice pipeline headlessly, with permissions stubbed
        and no microphone touched:

          swift run SpaceBar --dry-run-voice

        """

    /// Refuse to start, loudly, with the fix. EX_USAGE, because the build
    /// is fine and the way it was launched is not.
    static func enforceOrExit() {
        if isBundled { return }
        FileHandle.standardError.write(Data(message.utf8))
        exit(64)
    }
}
