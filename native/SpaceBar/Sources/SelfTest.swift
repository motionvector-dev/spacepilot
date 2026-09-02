// SelfTest.swift
// Prove the recogniser, the model, and the synthesiser work — with no
// microphone and no AVCaptureDevice permission in the path at all.
//
//   .build/SpaceBar.app/Contents/MacOS/SpaceBar --self-test <wav>
//
// Why this exists: 2026-09-02, Talk did nothing visible and nothing audible.
// The mic is one gate among four (Speech Recognition permission, the
// recogniser itself, the on-device model, the synthesiser) and TCC's own
// dialog is the least reliable of the four on this machine — see
// VoiceDuplexManager.startListening. This exercises the other three without
// going anywhere near AVAudioEngine or AVCaptureDevice, so a failure here can
// never be a microphone problem.
//
// It still asks for Speech Recognition, which is a real TCC-guarded call —
// the same one Talk makes. If that hangs, this hangs too, on purpose: an app
// that answers "the model works" while permission is stuck would be lying.

import AVFoundation
import Foundation
import FoundationModels
import Speech

@MainActor
enum SelfTest {

    static func requestedPath() -> URL? {
        let args = CommandLine.arguments
        guard let index = args.firstIndex(of: "--self-test"), index + 1 < args.count else {
            return nil
        }
        return URL(fileURLWithPath: args[index + 1])
    }

    static func run(wav: URL) async {
        print("self-test: \(wav.path)")
        guard FileManager.default.fileExists(atPath: wav.path) else {
            print("[wav] FAIL — no file at \(wav.path)")
            exit(1)
        }

        // Stage 1 — the one TCC-guarded call, and the one this whole file
        // exists to time. Racing it against a timer is what turns "hung
        // forever" into a reported failure; see VoiceDuplexManager.withTimeout.
        let permStart = Date()
        guard let status = await withTimeout(seconds: 12, { await VoicePermissions.requestSpeech(.system) }) else {
            report("speech-permission", start: permStart, failure: "timed out after 12s — TCC never answered")
            exit(1)
        }
        guard status == .authorized else {
            report("speech-permission", start: permStart, failure: "status=\(status.rawValue) — not authorized")
            exit(1)
        }
        report("speech-permission", start: permStart, ok: "authorized")

        guard let recognizer = SFSpeechRecognizer(locale: Locale(identifier: "en-US")) else {
            print("[recognizer] FAIL — no en-US recogniser on this Mac")
            exit(1)
        }
        guard recognizer.isAvailable else {
            print("[recognizer] FAIL — isAvailable=false")
            exit(1)
        }
        print("[recognizer] ok — available=true onDevice=\(recognizer.supportsOnDeviceRecognition)")

        // Stage 2 — transcribe the wav through the same recogniser Talk uses,
        // via a file request instead of a live buffer tap.
        let transcribeStart = Date()
        let transcript: String
        do {
            transcript = try await transcribe(wav: wav, recognizer: recognizer)
        } catch {
            report("transcribe", start: transcribeStart, failure: error.localizedDescription)
            exit(1)
        }
        guard !transcript.isEmpty else {
            report("transcribe", start: transcribeStart, failure: "empty transcript")
            exit(1)
        }
        report("transcribe", start: transcribeStart, ok: "\"\(transcript)\"")

        // Stage 3 — the same brain call `answer()` makes, minus the debounce.
        // `--brain apple|daemon|coreai` (default apple) and `--model
        // <id-or-path>` select it the same way `BrainSelection.resolve()`
        // does for the app — this is what proves the daemon and Core AI
        // chains end to end with no microphone in the path.
        let selection = BrainSelection.resolve()
        let brain: any Brain
        switch selection.kind {
        case .apple:
            brain = AppleFoundationModelManager()
        case .daemon:
            brain = DaemonBrain(client: DaemonClient(), requestedModel: selection.daemonModel)
        case .coreai:
            let url = selection.coreaiModelPath
                .map { URL(fileURLWithPath: ($0 as NSString).expandingTildeInPath) }
                ?? CoreAIBrain.defaultModelURL
            brain = CoreAIBrain(modelURL: url)
        }
        print("[brain] \(brain.label)")

        let modelStart = Date()
        let answer: String
        do {
            answer = try await brain.answer(
                userText: transcript,
                telemetry: NativeTelemetry.capture(),
                daemon: nil
            )
        } catch let error as BrainError {
            report("model", start: modelStart, failure: error.userFacing)
            exit(1)
        } catch {
            report("model", start: modelStart, failure: error.localizedDescription)
            exit(1)
        }
        report("model", start: modelStart, ok: "\"\(answer)\"")

        // Stage 4 — the same synthesiser call `speak()` makes.
        let synthStart = Date()
        do {
            try await synthesize(text: answer)
        } catch {
            report("synth", start: synthStart, failure: error.localizedDescription)
            exit(1)
        }
        report("synth", start: synthStart, ok: "spoke \(answer.count) chars")

        print("self-test: ok — heard \"\(transcript)\" — said \"\(answer)\"")
        exit(0)
    }

    // MARK: - Reporting

    private static func report(_ name: String, start: Date, ok result: String) {
        print("[\(name)] ok (\(elapsedMs(start))ms) — \(result)")
    }

    private static func report(_ name: String, start: Date, failure: String) {
        print("[\(name)] FAIL (\(elapsedMs(start))ms) — \(failure)")
    }

    private static func elapsedMs(_ start: Date) -> Int {
        Int(Date().timeIntervalSince(start) * 1000)
    }

    /// Races `operation` against a timer. Duplicated from
    /// `VoiceDuplexManager.withTimeout` rather than shared — same shape, two
    /// call sites, not worth a third file to unify.
    private static func withTimeout<T: Sendable>(seconds: Double, _ operation: @escaping @Sendable () async -> T) async -> T? {
        await withTaskGroup(of: T?.self) { group in
            group.addTask { Optional(await operation()) }
            group.addTask {
                try? await Task.sleep(nanoseconds: UInt64(seconds * 1_000_000_000))
                return nil
            }
            let first = await group.next() ?? nil
            group.cancelAll()
            return first
        }
    }

    // MARK: - The three legs, with no microphone anywhere in them

    // `nonisolated`, not a bare `private static` — `recognizer.recognitionTask`
    // calls its handler off the main thread. Written inline inside a
    // `@MainActor` method (SelfTest is `@MainActor`), that closure would be
    // *inferred* main-actor-isolated and SIGTRAP the moment Speech's queue
    // invokes it — the same trap VoicePermissions.swift's header documents
    // for `requestAuthorization`. `nonisolated` here is what stops it.
    private static nonisolated func transcribe(wav: URL, recognizer: SFSpeechRecognizer) async throws -> String {
        try await withCheckedThrowingContinuation { continuation in
            let request = SFSpeechURLRecognitionRequest(url: wav)
            if recognizer.supportsOnDeviceRecognition {
                request.requiresOnDeviceRecognition = true
            }
            let resumed = ResumeGuard()
            recognizer.recognitionTask(with: request) { result, error in
                if let error {
                    resumed.resumeOnce(continuation, .failure(error))
                    return
                }
                if let result, result.isFinal {
                    resumed.resumeOnce(continuation, .success(result.bestTranscription.formattedString))
                }
            }
        }
    }

    private static func synthesize(text: String) async throws {
        let synthesizer = AVSpeechSynthesizer()
        let utterance = AVSpeechUtterance(string: text)
        utterance.voice = AVSpeechSynthesisVoice(language: "en-US")
        utterance.rate = 0.52
        try await withCheckedThrowingContinuation { (continuation: CheckedContinuation<Void, Error>) in
            let delegate = SynthDoneDelegate { continuation.resume() }
            synthDelegateKeepAlive = delegate
            synthesizer.delegate = delegate
            synthesizer.speak(utterance)
        }
        synthDelegateKeepAlive = nil
    }

    /// `AVSpeechSynthesizer.delegate` is unretained; nothing else in this
    /// process holds `delegate` between `speak()` and its completion
    /// callback, so it needs a keep-alive slot rather than trusting ARC to
    /// find a retaining reference that does not exist.
    private static var synthDelegateKeepAlive: SynthDoneDelegate?
}

/// `SFSpeechRecognitionTask`'s callback can fire more than once (partial
/// results, then final, then sometimes an error after final). This resumes
/// the continuation exactly once and drops the rest.
private final class ResumeGuard: @unchecked Sendable {
    private let lock = NSLock()
    private var done = false

    func resumeOnce(_ continuation: CheckedContinuation<String, Error>, _ result: Result<String, Error>) {
        lock.lock()
        defer { lock.unlock() }
        guard !done else { return }
        done = true
        switch result {
        case .success(let value): continuation.resume(returning: value)
        case .failure(let error): continuation.resume(throwing: error)
        }
    }
}

private final class SynthDoneDelegate: NSObject, AVSpeechSynthesizerDelegate {
    private let onDone: @Sendable () -> Void
    init(onDone: @escaping @Sendable () -> Void) { self.onDone = onDone }
    nonisolated func speechSynthesizer(_ synthesizer: AVSpeechSynthesizer, didFinish utterance: AVSpeechUtterance) {
        onDone()
    }
}
