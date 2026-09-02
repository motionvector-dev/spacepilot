import SwiftUI
import AppKit
@preconcurrency import AVFoundation
import FoundationModels
import Speech
import Darwin

// MARK: - SpaceBar Application Entrypoint

/// The real entry point, so the bundle check runs before AppKit builds the
/// delegate — `VoiceDuplexManager` is a stored property of `AppDelegate`, and
/// its `init` reaches TCC. By the time `applicationDidFinishLaunching` runs,
/// an unbundled process is already dead.
@main
enum SpaceBarMain {
    static func main() {
        if DryRunVoice.isRequested() {
            DryRunVoice.run()
            return
        }
        if let wav = SelfTest.requestedPath() {
            LaunchGuard.enforceOrExit()
            Task { @MainActor in await SelfTest.run(wav: wav) }
            RunLoop.main.run()
            return
        }
        LaunchGuard.enforceOrExit()
        SpaceBarApp.main()
    }
}

struct SpaceBarApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) var appDelegate

    var body: some Scene {
        Settings {
            EmptyView()
        }
    }
}

// MARK: - Local machine telemetry
//
// Every field here is measured on this machine. Nothing is invented.
// The previous version mapped ProcessInfo's four thermal categories onto
// made-up temperatures ("41°C · Nominal") and fan speeds ("0 RPM · Silent").
// macOS does not expose either to an unprivileged process, so those numbers
// were decoration. A category is what we can read, so a category is what we
// show.
struct HardwareSnapshot: Sendable, Equatable {
    let residentMemoryGB: Double
    let physicalMemoryGB: Double
    let thermal: String
    let isNominal: Bool
}

enum NativeTelemetry {
    static func capture() -> HardwareSnapshot {
        var taskInfo = mach_task_basic_info()
        var count = mach_msg_type_number_t(MemoryLayout<mach_task_basic_info>.size / 4)
        let kerr = withUnsafeMutablePointer(to: &taskInfo) {
            $0.withMemoryRebound(to: integer_t.self, capacity: Int(count)) {
                task_info(mach_task_self_, task_flavor_t(MACH_TASK_BASIC_INFO), $0, &count)
            }
        }

        let residentGB = kerr == KERN_SUCCESS
            ? Double(taskInfo.resident_size) / 1_073_741_824.0
            : 0.0
        let physicalGB = Double(ProcessInfo.processInfo.physicalMemory) / 1_073_741_824.0

        let (thermal, nominal): (String, Bool) = {
            switch ProcessInfo.processInfo.thermalState {
            case .nominal:  return ("Nominal", true)
            case .fair:     return ("Fair", true)
            case .serious:  return ("Serious", false)
            case .critical: return ("Critical", false)
            @unknown default: return ("Unknown", true)
            }
        }()

        return HardwareSnapshot(
            residentMemoryGB: residentGB,
            physicalMemoryGB: physicalGB,
            thermal: thermal,
            isNominal: nominal
        )
    }
}

// MARK: - Voice
@MainActor
final class VoiceDuplexManager: NSObject, ObservableObject, SFSpeechRecognizerDelegate, AVSpeechSynthesizerDelegate {
    @Published var state: PopoverState = .idle {
        didSet {
            guard state != oldValue else { return }
            recentTransitions.append((state, Date()))
            if recentTransitions.count > 3 { recentTransitions.removeFirst(recentTransitions.count - 3) }
        }
    }
    @Published var lastHeard = ""
    @Published var lastSaid = ""
    @Published var telemetry: HardwareSnapshot = NativeTelemetry.capture()
    @Published var audioLevel: Float = 0.0

    /// What the daemon last told us, and when. Nil means we have no reading —
    /// which the popover says out loud rather than filling in with zeros.
    @Published var daemon: LocalStatus?
    @Published var daemonError: String?

    /// The most recent failure a person would need to see. Set by any path
    /// that used to fail silently — a permission request that never answers
    /// is the one this file exists to kill; see `startListening`.
    @Published var lastError: String?

    /// The last three state changes, oldest first. What "diagnostics" shows
    /// instead of a live log — enough to see a stall without a console.
    @Published var recentTransitions: [(state: PopoverState, at: Date)] = []

    private var audioEngine = AVAudioEngine()
    private var speechSynthesizer = AVSpeechSynthesizer()
    private let speechRecognizer = SFSpeechRecognizer(locale: Locale(identifier: "en-US"))
    private var recognitionRequest: SFSpeechAudioBufferRecognitionRequest?
    private var recognitionTask: SFSpeechRecognitionTask?
    private var timers: [Timer] = []

    private var debounceTask: Task<Void, Never>?
    private let afmManager = AppleFoundationModelManager()
    private let client = DaemonClient()

    /// Which brain answers `Talk`, and which daemon model if that is the
    /// one chosen. `didSet` is how a picker change or a relaunch with
    /// `--brain`/`--model` gets remembered — see `BrainSelection.persist`.
    /// Not fired by the property's own initial value, so init needs no
    /// special-casing here.
    @Published var brainSelection: BrainSelection = BrainSelection.resolve() {
        didSet { brainSelection.persist() }
    }

    /// The brain `answer()` reaches for right now. A computed property, not
    /// a stored one, so switching `brainSelection` takes effect on the next
    /// question with no extra plumbing — `afmManager` is still the one
    /// long-lived instance, so its lazy `LanguageModelSession` still only
    /// gets built once.
    private var brain: any Brain {
        switch brainSelection.kind {
        case .apple:
            return afmManager
        case .daemon:
            return DaemonBrain(client: client, requestedModel: brainSelection.daemonModel)
        }
    }

    /// What the Diagnostics picker shows for the brain in play right now.
    var brainLabel: String { brain.label }

    /// Where permission answers come from. `.system` in the app; stubbed in
    /// `--dry-run-voice`, which is how the denied and restricted paths get
    /// exercised without touching the microphone.
    let permissions: PermissionSource

    /// Whether we installed a tap, so teardown does not reach for
    /// `inputNode` on a Mac that has no input device. `AVAudioEngine.inputNode`
    /// raises an Objective-C exception in that case, which Swift cannot catch.
    private var tapIsInstalled = false

    init(permissions: PermissionSource = .system) {
        self.permissions = permissions
        super.init()
        speechSynthesizer.delegate = self
        startPolling()
    }

    private func startPolling() {
        // Local telemetry is free — it is a mach call. Poll it often.
        timers.append(Timer.scheduledTimer(withTimeInterval: 2.0, repeats: true) { [weak self] _ in
            Task { @MainActor in self?.telemetry = NativeTelemetry.capture() }
        })
        // The daemon is one loopback request against a route that reads this
        // machine and nothing else. 5s is comfortable; see DaemonClient for
        // why this is not /api/cockpit/status.
        timers.append(Timer.scheduledTimer(withTimeInterval: 5.0, repeats: true) { [weak self] _ in
            Task { @MainActor in await self?.refreshDaemon() }
        })
        Task { await refreshDaemon() }
        refreshPermission()
    }

    func refreshDaemon() async {
        do {
            let status = try await client.localStatus()
            daemon = status
            daemonError = nil
            if case .daemonOffline = state { state = .idle }
        } catch let error as DaemonError {
            daemon = nil
            daemonError = error.userFacing
            // Offline is only the headline state when nothing more urgent is
            // happening. A live conversation outranks a missing daemon.
            switch state {
            case .idle, .daemonOffline:
                state = .daemonOffline(reason: error.userFacing)
            default:
                break
            }
        } catch {
            daemon = nil
            daemonError = "Unreachable"
        }
    }

    // MARK: Permission

    /// What is missing, if anything. Checked without prompting, so the popover
    /// can show the gap before the user ever presses the talk key.
    ///
    /// This is polled and folded into `state`, never called from a view body —
    /// the authorization-status calls cross into TCC, and a SwiftUI body is
    /// evaluated far too often to be a sensible place to ask.
    func permissionGap() -> PopoverState.PermissionGap? {
        let speech = VoicePermissions.speechStatus(permissions)
        if speech == .denied || speech == .restricted { return .speechRecognition }
        let mic = VoicePermissions.microphoneStatus(permissions)
        if mic == .denied || mic == .restricted { return .microphone }
        return nil
    }

    /// Fold a permission gap into the state, if one outranks what we are doing.
    func refreshPermission() {
        if let gap = permissionGap() {
            state = .needsPermission(gap)
        } else if case .needsPermission = state {
            state = daemonError == nil ? .idle : .daemonOffline(reason: daemonError ?? "")
        }
    }

    func toggleConnection() {
        switch state {
        case .listening, .thinking:
            stopListening()
        case .needsPermission(let gap):
            // In a dry run there is no user and no System Settings to open.
            guard !permissions.isStubbed else { return }
            if let url = gap.settingsURL { NSWorkspace.shared.open(url) }
        case .daemonOffline:
            Task { await refreshDaemon() }
        case .idle, .speaking, .interrupted:
            Task { await startListening() }
        }
    }

    /// Ask, then open the graph. Both requests go through `VoicePermissions`,
    /// which is `nonisolated` on purpose — see the header of that file for the
    /// SIGTRAP this shape replaces. Denied and restricted both land in
    /// `no-mic-permission`; neither is a trap and neither is silent.
    func startListening() async {
        lastError = nil

        // TCC's own answer to `requestAuthorization` can simply never arrive —
        // confirmed on this machine: three of four real Talk presses on
        // 2026-09-02 produced no prompt and no callback at all (see
        // docs/design/SPACEBAR.md's "ad-hoc identity" note). Before this
        // guard, that hang was invisible: the button said "Talk", the state
        // never moved, and there was nothing to look at. 12s is generous for
        // a system dialog a person answers; it is not generous enough to look
        // like the app is thinking.
        guard let speech = await withTimeout(seconds: 12, { await VoicePermissions.requestSpeech(self.permissions) }) else {
            lastError = "Speech Recognition permission did not answer within 12s — TCC may have a stale grant for this build. See Diagnostics."
            state = .needsPermission(.speechRecognition)
            return
        }
        guard speech == .authorized else {
            state = .needsPermission(.speechRecognition)
            return
        }
        guard let granted = await withTimeout(seconds: 12, { await VoicePermissions.requestMicrophone(self.permissions) }) else {
            lastError = "Microphone permission did not answer within 12s — TCC may have a stale grant for this build. See Diagnostics."
            state = .needsPermission(.microphone)
            return
        }
        guard granted else {
            state = .needsPermission(.microphone)
            return
        }
        setupAudioGraph()
    }

    /// Races `operation` against a timer and returns whichever finishes
    /// first. `operation` keeps running in the background if it loses — Swift
    /// cannot cancel a TCC completion handler — but the caller stops waiting
    /// on it, which is the difference between a hang and a stated failure.
    private func withTimeout<T: Sendable>(seconds: Double, _ operation: @escaping @Sendable () async -> T) async -> T? {
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

    func stopListening() {
        if audioEngine.isRunning { audioEngine.stop() }
        if tapIsInstalled {
            audioEngine.inputNode.removeTap(onBus: 0)
            tapIsInstalled = false
        }
        recognitionRequest?.endAudio()
        recognitionTask?.cancel()
        recognitionTask = nil
        recognitionRequest = nil
        speechSynthesizer.stopSpeaking(at: .immediate)
        debounceTask?.cancel()

        audioLevel = 0.0
        state = daemonError == nil ? .idle : .daemonOffline(reason: daemonError ?? "")
    }

    private func setupAudioGraph() {
        // A dry run proves the permission ladder, not the audio hardware.
        // Opening a real input device is exactly what it must not do.
        guard !permissions.isStubbed else {
            state = .listening
            return
        }

        guard let recognizer = speechRecognizer else {
            // No recogniser for this locale. Say so; do not open a microphone
            // whose audio nothing will read.
            state = .needsPermission(.speechRecognition)
            print("SpaceBar: no speech recogniser for en-US on this Mac")
            return
        }

        let inputNode = audioEngine.inputNode

        // Voice-processing IO gives us echo cancellation, which is what makes
        // barge-in work at all: without it the recogniser hears the synthesiser
        // and interrupts the reply with the reply.
        do {
            try inputNode.setVoiceProcessingEnabled(true)
        } catch {
            print("SpaceBar: echo cancellation unavailable — \(error.localizedDescription)")
        }

        let hwFormat = inputNode.inputFormat(forBus: 0)
        guard hwFormat.sampleRate > 0, hwFormat.channelCount > 0 else {
            state = .idle
            print("SpaceBar: no usable input format on bus 0")
            return
        }

        guard let targetFormat = AVAudioFormat(commonFormat: .pcmFormatInt16, sampleRate: 16000, channels: 1, interleaved: true),
              let converter = AVAudioConverter(from: hwFormat, to: targetFormat) else {
            state = .idle
            return
        }

        recognitionTask?.cancel()
        recognitionTask = nil
        let request = SFSpeechAudioBufferRecognitionRequest()
        request.shouldReportPartialResults = true
        // Local-first is a claim we can actually keep here. Without this,
        // SFSpeechRecognizer may send audio to Apple's servers, which would
        // make the Info.plist string false and the ladder in SPACEBAR.md a lie.
        if recognizer.supportsOnDeviceRecognition {
            request.requiresOnDeviceRecognition = true
        }
        recognitionRequest = request

        recognitionTask = startRecognition(on: recognizer, request: request)

        if tapIsInstalled { inputNode.removeTap(onBus: 0) }
        installTap(
            on: inputNode,
            hwFormat: hwFormat,
            targetFormat: targetFormat,
            converter: converter,
            request: request
        )
        tapIsInstalled = true

        do {
            audioEngine.prepare()
            try audioEngine.start()
            state = .listening
        } catch {
            inputNode.removeTap(onBus: 0)
            tapIsInstalled = false
            state = .idle
            print("SpaceBar: audio engine — \(error.localizedDescription)")
        }
    }

    // MARK: The two callbacks that must not be main-actor-isolated
    //
    // Both of these are called off the main thread — the recognition handler on
    // Speech's own queue, the tap on the realtime audio render thread. Written
    // inline in a `@MainActor` method, Swift 6 infers them main-actor-isolated
    // and emits an executor check that traps. Formed inside these `nonisolated`
    // methods they inherit no isolation, and each hops to the main actor
    // explicitly with a value that is already Sendable.

    private nonisolated func startRecognition(
        on recognizer: SFSpeechRecognizer,
        request: SFSpeechAudioBufferRecognitionRequest
    ) -> SFSpeechRecognitionTask {
        recognizer.recognitionTask(with: request) { [weak self] result, error in
            // `heard` is a String before the hop. The result object itself is
            // not Sendable and must not cross.
            let heard = result?.bestTranscription.formattedString
            let failure = error?.localizedDescription
            Task { @MainActor in
                guard let self else { return }
                if let heard { self.heard(heard) }
                if let failure { print("SpaceBar: recognition — \(failure)") }
            }
        }
    }

    private nonisolated func installTap(
        on inputNode: AVAudioInputNode,
        hwFormat: AVAudioFormat,
        targetFormat: AVAudioFormat,
        converter: AVAudioConverter,
        request: SFSpeechAudioBufferRecognitionRequest
    ) {
        final class StreamState: @unchecked Sendable { var hasData = true }

        inputNode.installTap(onBus: 0, bufferSize: 1024, format: hwFormat) { [weak self] buffer, _ in
            let outputCapacity = AVAudioFrameCount(Double(buffer.frameLength) * 16000.0 / hwFormat.sampleRate)
            guard outputCapacity > 0,
                  let converted = AVAudioPCMBuffer(pcmFormat: targetFormat, frameCapacity: outputCapacity) else { return }

            var convError: NSError?
            let stream = StreamState()
            converter.convert(to: converted, error: &convError) { _, outStatus in
                if stream.hasData {
                    stream.hasData = false
                    outStatus.pointee = .haveData
                    return buffer
                }
                outStatus.pointee = .noDataNow
                return nil
            }
            if convError == nil { request.append(converted) }

            if let channelData = buffer.floatChannelData?[0] {
                let n = min(Int(buffer.frameLength), 256)
                guard n > 0 else { return }
                var sum: Float = 0
                for i in 0..<n { sum += abs(channelData[i]) }
                let level = min(1.0, (sum / Float(n)) * 5.0)
                Task { @MainActor in self?.audioLevel = level }
            }
        }
    }

    /// One transcription update, on the main actor.
    private func heard(_ text: String) {
        lastHeard = text
        guard !text.isEmpty else { return }

        // Barge-in: the user talking wins, immediately.
        if case .speaking = state {
            speechSynthesizer.stopSpeaking(at: .immediate)
            state = .interrupted
        }

        debounceTask?.cancel()
        debounceTask = Task { [weak self] in
            try? await Task.sleep(nanoseconds: 1_200_000_000)
            guard !Task.isCancelled, let self else { return }
            await self.answer(text)
        }
    }

    private func answer(_ text: String) async {
        state = .thinking
        let snap = NativeTelemetry.capture()
        telemetry = snap

        do {
            let response = try await brain.answer(userText: text, telemetry: snap, daemon: daemon)
            lastSaid = response
            speak(response)
        } catch let error as BrainError {
            handleBrainError(error)
        } catch {
            state = .idle
            lastSaid = "Could not answer: \(error.localizedDescription)"
        }
    }

    /// One line per failure a person would actually want to hear — never a
    /// fabricated reply. `.daemonOffline` reuses the same state
    /// `refreshDaemon()` already renders for a dead heartbeat; this is the
    /// same sentence, just reached from `Talk` instead of the poller.
    private func handleBrainError(_ error: BrainError) {
        switch error {
        case .unavailable(let message):
            state = .idle
            lastSaid = message
            speak(lastSaid)
        case .daemonOffline(let reason):
            state = .daemonOffline(reason: reason)
            lastSaid = "SpacePilot's daemon isn't running, so I can't answer with the daemon brain."
            speak(lastSaid)
        case .modelNotListed:
            state = .idle
            lastSaid = error.userFacing
            speak(lastSaid)
        case .modelUnavailable(let message):
            state = .idle
            lastSaid = "Could not answer: \(message)"
        }
    }

    private func speak(_ text: String) {
        // A dry run must not make the Mac talk out loud.
        guard !permissions.isStubbed else {
            state = .speaking
            return
        }
        let utterance = AVSpeechUtterance(string: text)
        utterance.voice = AVSpeechSynthesisVoice(language: "en-US")
        utterance.rate = 0.52
        state = .speaking
        speechSynthesizer.speak(utterance)
    }

    nonisolated func speechSynthesizer(_ synthesizer: AVSpeechSynthesizer, didFinish utterance: AVSpeechUtterance) {
        Task { @MainActor in
            if case .speaking = self.state { self.state = .listening }
        }
    }

    // MARK: - Diagnostics
    //
    // Every field here is read from the real API at the moment the popover
    // asks, never cached and never guessed. "no reading" is a value, not an
    // absence — see the honesty rule in docs/design/SPACEBAR.md.

    func diagnosticsSnapshot() -> DiagnosticsSnapshot {
        let recognizer = speechRecognizer
        let inputDeviceName = AVCaptureDevice.default(for: .audio)?.localizedName
        // `inputFormat(forBus:)` is safe to read without a tap installed —
        // `setupAudioGraph` already does this unguarded. A sample rate of 0
        // is what "no input device" looks like from here.
        let format = audioEngine.inputNode.inputFormat(forBus: 0)

        return DiagnosticsSnapshot(
            speechPermission: String(describing: VoicePermissions.speechStatus(permissions)),
            microphonePermission: String(describing: VoicePermissions.microphoneStatus(permissions)),
            recognizerAvailable: recognizer?.isAvailable,
            recognizerOnDevice: recognizer?.supportsOnDeviceRecognition,
            inputDeviceName: inputDeviceName,
            inputSampleRate: format.sampleRate > 0 ? format.sampleRate : nil,
            audioEngineRunning: audioEngine.isRunning,
            inputLevel: audioLevel,
            modelAvailability: String(describing: SystemLanguageModel.default.availability),
            lastError: lastError,
            recentTransitions: recentTransitions
        )
    }
}

/// One read of everything the popover's Diagnostics disclosure shows. `nil`
/// means the value could not be read, not that it is zero or off.
struct DiagnosticsSnapshot {
    let speechPermission: String
    let microphonePermission: String
    let recognizerAvailable: Bool?
    let recognizerOnDevice: Bool?
    let inputDeviceName: String?
    let inputSampleRate: Double?
    let audioEngineRunning: Bool
    let inputLevel: Float
    let modelAvailability: String
    let lastError: String?
    let recentTransitions: [(state: PopoverState, at: Date)]
}

// MARK: - Appearance
//
// DESIGN.md's first principle is Obsidian Dark Precision, so the app forces
// dark rather than following the system. Tokens.swift still carries the
// designed light values, so unforcing this later needs no new colour work —
// it is one line here, not a repaint.
enum Appearance {
    /// A function, not a stored constant: NSAppearance is not Sendable, so a
    /// static let would be a shared-mutable-state error under Swift 6.
    static func product() -> NSAppearance? { NSAppearance(named: .darkAqua) }
}

// MARK: - Status bar
@MainActor
final class AppDelegate: NSObject, NSApplicationDelegate {
    var statusItem: NSStatusItem?
    var popover: NSPopover?
    let voiceManager = VoiceDuplexManager()

    func applicationDidFinishLaunching(_ notification: Notification) {
        if let directory = Snapshot.requestedDirectory() {
            Task {
                await Snapshot.run(into: directory)
                NSApplication.shared.terminate(nil)
            }
            return
        }

        NSApp.appearance = Appearance.product()

        statusItem = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
        if let button = statusItem?.button {
            button.image = Self.menuBarGlyph()
            button.imagePosition = .imageOnly
            button.target = self
            button.action = #selector(togglePopover)
            button.setAccessibilityLabel("SpacePilot")
        }

        let pop = NSPopover()
        pop.contentSize = NSSize(width: 360, height: 420)
        pop.behavior = .transient
        pop.contentViewController = NSHostingController(
            rootView: SpaceBarPopoverView(voice: voiceManager)
        )
        popover = pop
    }

    /// A template image, so the menu bar tints it for us and it reads correctly
    /// on a light bar, a dark bar, and behind a wallpaper. A hardcoded gold
    /// ship could do none of those.
    private static func menuBarGlyph() -> NSImage {
        let image = NSImage(size: NSSize(width: 18, height: 14), flipped: false) { _ in
            let path = NSBezierPath()
            path.move(to: NSPoint(x: 17, y: 7))
            path.line(to: NSPoint(x: 1, y: 13))
            path.line(to: NSPoint(x: 5, y: 7))
            path.line(to: NSPoint(x: 1, y: 1))
            path.close()
            NSColor.black.setFill()
            path.fill()
            return true
        }
        image.isTemplate = true
        return image
    }

    @objc func togglePopover() {
        guard let popover, let button = statusItem?.button else { return }
        if popover.isShown {
            popover.performClose(nil)
        } else {
            popover.show(relativeTo: button.bounds, of: button, preferredEdge: .minY)
        }
    }
}

// MARK: - Popover
struct SpaceBarPopoverView: View {
    @ObservedObject var voice: VoiceDuplexManager
    @State private var showDiagnostics = false

    private var state: PopoverState { voice.state }

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            header
            machine
            transcript
            Spacer(minLength: 0)
            controls
            diagnosticsDisclosure
        }
        .padding(16)
        .frame(width: 360)
        .background(Tokens.UI.panel)
    }

    // MARK: Header — what the app is doing, and nothing else

    private var header: some View {
        HStack(spacing: 8) {
            Circle()
                .fill(statusColor)
                .frame(width: 6, height: 6)
            Text(state.headline)
                .font(.system(size: 12, weight: .semibold))
                .foregroundStyle(Tokens.UI.ink)
            Spacer()
        }
    }

    private var statusColor: Color {
        switch state {
        case .listening, .speaking: return Tokens.UI.true_
        case .thinking: return Tokens.UI.gold
        case .needsPermission: return Tokens.UI.wrong
        case .daemonOffline, .idle, .interrupted: return Tokens.UI.ink4
        }
    }

    // MARK: The machine

    private var machine: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Text(voice.daemon?.deviceName ?? "This Mac")
                    .font(.system(size: 13, weight: .semibold))
                    .foregroundStyle(Tokens.UI.ink)
                Spacer()
                Text(voice.telemetry.thermal)
                    .font(.system(size: 10, design: .monospaced))
                    .foregroundStyle(voice.telemetry.isNominal ? Tokens.UI.ink3 : Tokens.UI.wrong)
            }

            if case .daemonOffline(let reason) = state {
                offlineNote(reason)
            } else if let daemon = voice.daemon {
                daemonRows(daemon)
            } else {
                Text("No reading yet")
                    .font(.system(size: 11, design: .monospaced))
                    .foregroundStyle(Tokens.UI.ink4)
            }

            memoryRail
        }
        .padding(12)
        .background(RoundedRectangle(cornerRadius: 10).fill(Tokens.UI.card))
        .overlay(RoundedRectangle(cornerRadius: 10).stroke(Tokens.UI.line2, lineWidth: 0.5))
    }

    /// The offline state says what is missing and how to fix it. It does not
    /// show stale numbers, and it does not show zeros.
    private func offlineNote(_ reason: String) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(reason)
                .font(.system(size: 11, design: .monospaced))
                .foregroundStyle(Tokens.UI.ink3)
            Text("Voice still works. Fleet data does not.")
                .font(.system(size: 11))
                .foregroundStyle(Tokens.UI.ink4)
            Text("spacepilot serve")
                .font(.system(size: 11, design: .monospaced))
                .foregroundStyle(Tokens.UI.ink2)
                .padding(.horizontal, 6)
                .padding(.vertical, 3)
                .background(RoundedRectangle(cornerRadius: 4).fill(Tokens.UI.card))
        }
    }

    private func daemonRows(_ daemon: LocalStatus) -> some View {
        VStack(alignment: .leading, spacing: 3) {
            row("backend", daemon.backend ?? "no reading")
            row("headroom", daemon.headroomLine ?? "no reading")
            row("loaded", (daemon.loadedModels?.isEmpty ?? true)
                ? "nothing"
                : (daemon.loadedModels ?? []).joined(separator: ", "))
        }
    }

    private func row(_ key: String, _ value: String) -> some View {
        HStack(alignment: .top, spacing: 8) {
            Text(key.uppercased())
                .font(.system(size: 9, weight: .medium, design: .monospaced))
                .kerning(0.5)
                .foregroundStyle(Tokens.UI.ink4)
                .frame(width: 66, alignment: .leading)
            Text(value)
                .font(.system(size: 11, design: .monospaced))
                .foregroundStyle(Tokens.UI.ink2)
            Spacer(minLength: 0)
        }
    }

    /// SpaceBar's own resident memory against this machine's real physical
    /// memory. Both numbers are measured — the previous version compared a real
    /// figure against two hardcoded constants (25.0 and 32.0 GB).
    private var memoryRail: some View {
        VStack(alignment: .leading, spacing: 5) {
            HStack {
                Text("SPACEBAR MEMORY")
                    .font(.system(size: 9, weight: .medium, design: .monospaced))
                    .kerning(0.5)
                    .foregroundStyle(Tokens.UI.ink4)
                Spacer()
                Text(String(format: "%.2f of %.0f GB",
                            voice.telemetry.residentMemoryGB,
                            voice.telemetry.physicalMemoryGB))
                    .font(.system(size: 10, design: .monospaced))
                    .foregroundStyle(Tokens.UI.ink3)
            }
            GeometryReader { geo in
                ZStack(alignment: .leading) {
                    RoundedRectangle(cornerRadius: 2)
                        .fill(Tokens.UI.raised)
                        .frame(height: 4)
                    RoundedRectangle(cornerRadius: 2)
                        .fill(Tokens.UI.gold)
                        .frame(
                            width: max(2, geo.size.width * fraction),
                            height: 4
                        )
                }
            }
            .frame(height: 4)
        }
    }

    private var fraction: CGFloat {
        guard voice.telemetry.physicalMemoryGB > 0 else { return 0 }
        return CGFloat(min(1.0, voice.telemetry.residentMemoryGB / voice.telemetry.physicalMemoryGB))
    }

    // MARK: Conversation

    private var transcript: some View {
        VStack(alignment: .leading, spacing: 6) {
            if !voice.lastHeard.isEmpty {
                line("You", voice.lastHeard, Tokens.UI.ink2)
            }
            if !voice.lastSaid.isEmpty {
                line("SpacePilot", voice.lastSaid, Tokens.UI.ink)
            }
            if voice.lastHeard.isEmpty && voice.lastSaid.isEmpty {
                Text("Press Talk and ask about this machine.")
                    .font(.system(size: 11))
                    .foregroundStyle(Tokens.UI.ink4)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(12)
        .background(RoundedRectangle(cornerRadius: 10).fill(Tokens.UI.card))
        .overlay(
            RoundedRectangle(cornerRadius: 10)
                .stroke(state.isWorking ? Tokens.UI.goldLine : Tokens.UI.line2,
                        lineWidth: state.isWorking ? 1 : 0.5)
        )
    }

    private func line(_ who: String, _ what: String, _ color: Color) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(who.uppercased())
                .font(.system(size: 9, weight: .medium, design: .monospaced))
                .kerning(0.5)
                .foregroundStyle(Tokens.UI.ink4)
            Text(what)
                .font(.system(size: 12))
                .foregroundStyle(color)
                .fixedSize(horizontal: false, vertical: true)
        }
    }

    // MARK: Controls

    private var controls: some View {
        HStack(spacing: 10) {
            Button(action: { voice.toggleConnection() }) {
                Text(state.primaryAction ?? "Talk")
                    .font(.system(size: 11, weight: .semibold))
                    .foregroundStyle(Tokens.UI.gold)
                    .padding(.horizontal, 14)
                    .padding(.vertical, 6)
                    .background(RoundedRectangle(cornerRadius: 6).fill(Tokens.UI.raised))
                    .overlay(RoundedRectangle(cornerRadius: 6).stroke(Tokens.UI.goldLine, lineWidth: 1))
            }
            .buttonStyle(.plain)

            if state.isMicrophoneOpen {
                HStack(spacing: 5) {
                    Circle().fill(Tokens.UI.true_).frame(width: 5, height: 5)
                    Text("mic open")
                        .font(.system(size: 10, design: .monospaced))
                        .foregroundStyle(Tokens.UI.ink3)
                }
            }

            Spacer()

            Button("Quit") {
                voice.stopListening()
                NSApplication.shared.terminate(nil)
            }
            .buttonStyle(.plain)
            .font(.system(size: 11))
            .foregroundStyle(Tokens.UI.ink3)
        }
    }

    // MARK: Diagnostics — off by default, everything real when open
    //
    // Every row is read from the live API each time this redraws. "no
    // reading" is what a value the API would not answer looks like — never a
    // zero, never a guess. This exists because Talk failing used to look
    // exactly like Talk succeeding: nothing moved, nothing was said, and
    // there was nowhere to look. See VoiceDuplexManager.startListening.

    private var diagnosticsDisclosure: some View {
        DisclosureGroup(isExpanded: $showDiagnostics) {
            diagnosticsBody
        } label: {
            Text("Diagnostics")
                .font(.system(size: 10, weight: .medium, design: .monospaced))
                .foregroundStyle(Tokens.UI.ink4)
        }
        .tint(Tokens.UI.ink4)
    }

    private var diagnosticsBody: some View {
        let d = voice.diagnosticsSnapshot()
        return VStack(alignment: .leading, spacing: 3) {
            brainRow
            diagRow("speech perm", d.speechPermission)
            diagRow("mic perm", d.microphonePermission)
            diagRow("recognizer", d.recognizerAvailable.map { $0 ? "available" : "unavailable" } ?? "no reading")
            diagRow("on-device", d.recognizerOnDevice.map { $0 ? "yes" : "no" } ?? "no reading")
            diagRow("input device", d.inputDeviceName ?? "no reading")
            diagRow("sample rate", d.inputSampleRate.map { String(format: "%.0f Hz", $0) } ?? "no reading")
            diagRow("audio engine", d.audioEngineRunning ? "running" : "stopped")
            diagRow("input level", String(format: "%.2f", d.inputLevel))
            diagRow("model", d.modelAvailability)
            diagRow("last error", d.lastError ?? "none")
            if d.recentTransitions.isEmpty {
                diagRow("history", "no reading")
            } else {
                ForEach(Array(d.recentTransitions.enumerated()), id: \.offset) { _, entry in
                    diagRow("→ \(entry.at.formatted(date: .omitted, time: .standard))", entry.state.headline)
                }
            }
        }
        .padding(.top, 6)
    }

    /// The brain picker. Three fixed choices plus whatever is active right
    /// now, so `--model` and a prior picker choice always show correctly
    /// even when they are not one of the three. Switching takes effect on
    /// the next question — `answer()` reads `voice.brainSelection` fresh
    /// every time.
    private var brainRow: some View {
        HStack(alignment: .center, spacing: 8) {
            Text("BRAIN")
                .font(.system(size: 8, weight: .medium, design: .monospaced))
                .kerning(0.4)
                .foregroundStyle(Tokens.UI.ink4)
                .frame(width: 78, alignment: .leading)
            Menu {
                Button("Apple Intelligence") {
                    voice.brainSelection = BrainSelection(kind: .apple, daemonModel: voice.brainSelection.daemonModel)
                }
                Button("Daemon · auto") {
                    voice.brainSelection = BrainSelection(kind: .daemon, daemonModel: nil)
                }
                Button("Daemon · claude-sonnet-5") {
                    voice.brainSelection = BrainSelection(kind: .daemon, daemonModel: "claude-sonnet-5")
                }
            } label: {
                Text(voice.brainLabel)
                    .font(.system(size: 9, design: .monospaced))
                    .foregroundStyle(Tokens.UI.ink2)
            }
            .menuStyle(.borderlessButton)
            .fixedSize()
            Spacer(minLength: 0)
        }
    }

    private func diagRow(_ key: String, _ value: String) -> some View {
        HStack(alignment: .top, spacing: 8) {
            Text(key.uppercased())
                .font(.system(size: 8, weight: .medium, design: .monospaced))
                .kerning(0.4)
                .foregroundStyle(Tokens.UI.ink4)
                .frame(width: 78, alignment: .leading)
            Text(value)
                .font(.system(size: 9, design: .monospaced))
                .foregroundStyle(Tokens.UI.ink3)
                .fixedSize(horizontal: false, vertical: true)
            Spacer(minLength: 0)
        }
    }
}

// MARK: - Apple Foundation Model
@available(macOS 15.0, *)
actor AppleFoundationModelManager {
    /// Built on first use, not at launch.
    ///
    /// The old code created a `LanguageModelSession` in `init`, which ran when
    /// `AppDelegate` allocated its `VoiceDuplexManager` — so every launch paid
    /// for a session, including on a Mac where Apple Intelligence is switched
    /// off and there is no model behind it. Nothing needs one until the first
    /// question, and `answer()` has already checked availability by then.
    private var session: LanguageModelSession?

    private func activeSession() -> LanguageModelSession {
        if let session { return session }
        let fresh = LanguageModelSession(instructions: SpacePilotInstructions.system)
        session = fresh
        return fresh
    }

    /// Telemetry is injected into the prompt, not the instructions, so the
    /// model treats it as ground truth for this one request. Anything we do
    /// not actually know is sent as "no reading" — the instructions tell the
    /// model to repeat that rather than invent a number, which is the whole
    /// reason this app can quote figures at all.
    func processInput(
        userText: String,
        telemetry: HardwareSnapshot,
        daemon: LocalStatus?
    ) async throws -> String {
        let block = SpacePilotInstructions.telemetryBlock(
            shipName: daemon?.deviceName ?? "no reading",
            thermalState: telemetry.thermal,
            backend: daemon?.backend ?? "no reading",
            headroom: daemon?.headroomLine ?? "no reading",
            loadedModels: daemon?.loadedModels ?? [],
            daemonReachable: daemon != nil
        )
        let response = try await activeSession().respond(to: "\(block)\n\n\(userText)")
        return response.content
    }
}

@available(macOS 15.0, *)
extension AppleFoundationModelManager: Brain {
    nonisolated var label: String { "Apple Intelligence" }

    func answer(userText: String, telemetry: HardwareSnapshot, daemon: LocalStatus?) async throws -> String {
        guard case .available = SystemLanguageModel.default.availability else {
            throw BrainError.unavailable("Apple Intelligence is off, so there is no on-device model to answer with.")
        }
        return try await processInput(userText: userText, telemetry: telemetry, daemon: daemon)
    }
}
