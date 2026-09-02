import SwiftUI
import AppKit
@preconcurrency import AVFoundation
import FoundationModels
import Speech
import Darwin

// MARK: - SpaceBar Application Entrypoint
@main
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
    @Published var state: PopoverState = .idle
    @Published var lastHeard = ""
    @Published var lastSaid = ""
    @Published var telemetry: HardwareSnapshot = NativeTelemetry.capture()
    @Published var audioLevel: Float = 0.0

    /// What the daemon last told us, and when. Nil means we have no reading —
    /// which the popover says out loud rather than filling in with zeros.
    @Published var daemon: LocalStatus?
    @Published var daemonError: String?

    private var audioEngine = AVAudioEngine()
    private var speechSynthesizer = AVSpeechSynthesizer()
    private let speechRecognizer = SFSpeechRecognizer(locale: Locale(identifier: "en-US"))
    private var recognitionRequest: SFSpeechAudioBufferRecognitionRequest?
    private var recognitionTask: SFSpeechRecognitionTask?
    private var timers: [Timer] = []

    private var debounceTask: Task<Void, Never>?
    private let afmManager = AppleFoundationModelManager()
    private let client = DaemonClient()

    override init() {
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
    func permissionGap() -> PopoverState.PermissionGap? {
        if SFSpeechRecognizer.authorizationStatus() == .denied
            || SFSpeechRecognizer.authorizationStatus() == .restricted {
            return .speechRecognition
        }
        if AVCaptureDevice.authorizationStatus(for: .audio) == .denied
            || AVCaptureDevice.authorizationStatus(for: .audio) == .restricted {
            return .microphone
        }
        return nil
    }

    func toggleConnection() {
        switch state {
        case .listening, .thinking:
            stopListening()
        case .needsPermission(let gap):
            if let url = gap.settingsURL { NSWorkspace.shared.open(url) }
        case .daemonOffline:
            Task { await refreshDaemon() }
        case .idle, .speaking, .interrupted:
            startListening()
        }
    }

    func startListening() {
        SFSpeechRecognizer.requestAuthorization { [weak self] authStatus in
            Task { @MainActor in
                guard let self else { return }
                guard authStatus == .authorized else {
                    self.state = .needsPermission(.speechRecognition)
                    return
                }
                AVCaptureDevice.requestAccess(for: .audio) { granted in
                    Task { @MainActor in
                        guard granted else {
                            self.state = .needsPermission(.microphone)
                            return
                        }
                        self.setupAudioGraph()
                    }
                }
            }
        }
    }

    func stopListening() {
        if audioEngine.isRunning { audioEngine.stop() }
        audioEngine.inputNode.removeTap(onBus: 0)
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
        guard hwFormat.sampleRate > 0 else { return }

        guard let targetFormat = AVAudioFormat(commonFormat: .pcmFormatInt16, sampleRate: 16000, channels: 1, interleaved: true),
              let converter = AVAudioConverter(from: hwFormat, to: targetFormat) else { return }

        recognitionTask?.cancel()
        recognitionTask = nil
        let request = SFSpeechAudioBufferRecognitionRequest()
        request.shouldReportPartialResults = true
        // Local-first is a claim we can actually keep here. Without this,
        // SFSpeechRecognizer may send audio to Apple's servers, which would
        // make the Info.plist string false and the ladder in SPACEBAR.md a lie.
        if speechRecognizer?.supportsOnDeviceRecognition == true {
            request.requiresOnDeviceRecognition = true
        }
        recognitionRequest = request

        recognitionTask = speechRecognizer?.recognitionTask(with: request) { [weak self] result, error in
            Task { @MainActor in
                guard let self else { return }
                if let result {
                    let heard = result.bestTranscription.formattedString
                    self.lastHeard = heard

                    // Barge-in: the user talking wins, immediately.
                    if case .speaking = self.state, !heard.isEmpty {
                        self.speechSynthesizer.stopSpeaking(at: .immediate)
                        self.state = .interrupted
                    } else if !heard.isEmpty, case .listening = self.state {
                        // stay listening
                    }

                    self.debounceTask?.cancel()
                    self.debounceTask = Task {
                        try? await Task.sleep(nanoseconds: 1_200_000_000)
                        guard !Task.isCancelled, !heard.isEmpty else { return }
                        await self.answer(heard)
                    }
                }
                if let error {
                    print("SpaceBar: recognition — \(error.localizedDescription)")
                }
            }
        }

        final class StreamState: @unchecked Sendable { var hasData = true }

        inputNode.removeTap(onBus: 0)
        inputNode.installTap(onBus: 0, bufferSize: 1024, format: hwFormat) { [weak self] buffer, _ in
            let outputCapacity = AVAudioFrameCount(Double(buffer.frameLength) * 16000.0 / hwFormat.sampleRate)
            guard let converted = AVAudioPCMBuffer(pcmFormat: targetFormat, frameCapacity: outputCapacity) else { return }

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
                let avg = sum / Float(n)
                Task { @MainActor in self?.audioLevel = min(1.0, avg * 5.0) }
            }
        }

        do {
            audioEngine.prepare()
            try audioEngine.start()
            state = .listening
        } catch {
            state = .idle
            print("SpaceBar: audio engine — \(error.localizedDescription)")
        }
    }

    private func answer(_ text: String) async {
        guard SystemLanguageModel.default.isAvailable else {
            lastSaid = "The on-device model is not available on this Mac."
            speak(lastSaid)
            return
        }

        state = .thinking
        let snap = NativeTelemetry.capture()
        telemetry = snap

        do {
            let response = try await afmManager.processInput(
                userText: text,
                telemetry: snap,
                daemon: daemon
            )
            lastSaid = response
            speak(response)
        } catch {
            state = .idle
            lastSaid = "Could not answer: \(error.localizedDescription)"
        }
    }

    private func speak(_ text: String) {
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
}

// MARK: - Theme
//
// design.md requires three states and a visible control. In an AppKit app the
// three states are: follow the system (nil appearance), force light, force dark.
// Tokens.swift resolves against whatever is effective, so setting this one
// property re-themes every colour in the popover.
enum ThemeChoice: String, CaseIterable {
    case system, light, dark

    var label: String {
        switch self {
        case .system: return "System"
        case .light: return "Light"
        case .dark: return "Dark"
        }
    }

    var appearance: NSAppearance? {
        switch self {
        case .system: return nil
        case .light: return NSAppearance(named: .aqua)
        case .dark: return NSAppearance(named: .darkAqua)
        }
    }
}

@MainActor
final class ThemeController: ObservableObject {
    private static let key = "spacebar.theme"

    @Published var choice: ThemeChoice {
        didSet {
            UserDefaults.standard.set(choice.rawValue, forKey: Self.key)
            NSApp.appearance = choice.appearance
        }
    }

    init() {
        let stored = UserDefaults.standard.string(forKey: Self.key) ?? ThemeChoice.system.rawValue
        choice = ThemeChoice(rawValue: stored) ?? .system
    }

    func apply() { NSApp.appearance = choice.appearance }
}

// MARK: - Status bar
@MainActor
final class AppDelegate: NSObject, NSApplicationDelegate {
    var statusItem: NSStatusItem?
    var popover: NSPopover?
    let voiceManager = VoiceDuplexManager()
    let theme = ThemeController()

    func applicationDidFinishLaunching(_ notification: Notification) {
        theme.apply()

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
            rootView: SpaceBarPopoverView(voice: voiceManager, theme: theme)
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
    @ObservedObject var theme: ThemeController

    private var state: PopoverState {
        if let gap = voice.permissionGap() { return .needsPermission(gap) }
        return voice.state
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            header
            machine
            transcript
            Spacer(minLength: 0)
            controls
        }
        .padding(16)
        .frame(width: 360)
        .background(Tokens.UI.ground)
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
            themeToggle
        }
    }

    private var statusColor: Color {
        switch state {
        case .listening, .speaking: return Tokens.UI.true_
        case .thinking: return Tokens.UI.accent
        case .needsPermission: return Tokens.UI.wrong
        case .daemonOffline, .idle, .interrupted: return Tokens.UI.faint
        }
    }

    private var themeToggle: some View {
        HStack(spacing: 2) {
            ForEach(ThemeChoice.allCases, id: \.self) { choice in
                Button(choice.label) { theme.choice = choice }
                    .buttonStyle(.plain)
                    .font(.system(size: 10, design: .monospaced))
                    .foregroundStyle(theme.choice == choice ? Tokens.UI.ink : Tokens.UI.muted)
                    .padding(.horizontal, 7)
                    .padding(.vertical, 3)
                    .background(
                        RoundedRectangle(cornerRadius: 5)
                            .fill(theme.choice == choice ? Tokens.UI.surface3 : Color.clear)
                    )
                    .accessibilityAddTraits(theme.choice == choice ? [.isSelected] : [])
            }
        }
        .padding(2)
        .background(
            RoundedRectangle(cornerRadius: 7).fill(Tokens.UI.surface)
        )
        .overlay(
            RoundedRectangle(cornerRadius: 7).stroke(Tokens.UI.border, lineWidth: 0.5)
        )
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
                    .foregroundStyle(voice.telemetry.isNominal ? Tokens.UI.muted : Tokens.UI.wrong)
            }

            if case .daemonOffline(let reason) = state {
                offlineNote(reason)
            } else if let daemon = voice.daemon {
                daemonRows(daemon)
            } else {
                Text("No reading yet")
                    .font(.system(size: 11, design: .monospaced))
                    .foregroundStyle(Tokens.UI.faint)
            }

            memoryRail
        }
        .padding(12)
        .background(RoundedRectangle(cornerRadius: 10).fill(Tokens.UI.surface))
        .overlay(RoundedRectangle(cornerRadius: 10).stroke(Tokens.UI.border, lineWidth: 0.5))
    }

    /// The offline state says what is missing and how to fix it. It does not
    /// show stale numbers, and it does not show zeros.
    private func offlineNote(_ reason: String) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(reason)
                .font(.system(size: 11, design: .monospaced))
                .foregroundStyle(Tokens.UI.muted)
            Text("Voice still works. Fleet data does not.")
                .font(.system(size: 11))
                .foregroundStyle(Tokens.UI.faint)
            Text("spacepilot serve")
                .font(.system(size: 11, design: .monospaced))
                .foregroundStyle(Tokens.UI.text)
                .padding(.horizontal, 6)
                .padding(.vertical, 3)
                .background(RoundedRectangle(cornerRadius: 4).fill(Tokens.UI.surface2))
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
                .foregroundStyle(Tokens.UI.faint)
                .frame(width: 66, alignment: .leading)
            Text(value)
                .font(.system(size: 11, design: .monospaced))
                .foregroundStyle(Tokens.UI.text)
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
                    .foregroundStyle(Tokens.UI.faint)
                Spacer()
                Text(String(format: "%.2f of %.0f GB",
                            voice.telemetry.residentMemoryGB,
                            voice.telemetry.physicalMemoryGB))
                    .font(.system(size: 10, design: .monospaced))
                    .foregroundStyle(Tokens.UI.muted)
            }
            GeometryReader { geo in
                ZStack(alignment: .leading) {
                    RoundedRectangle(cornerRadius: 2)
                        .fill(Tokens.UI.surface3)
                        .frame(height: 4)
                    RoundedRectangle(cornerRadius: 2)
                        .fill(Tokens.UI.accent)
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
                line("You", voice.lastHeard, Tokens.UI.text)
            }
            if !voice.lastSaid.isEmpty {
                line("SpacePilot", voice.lastSaid, Tokens.UI.ink)
            }
            if voice.lastHeard.isEmpty && voice.lastSaid.isEmpty {
                Text("Press Talk and ask about this machine.")
                    .font(.system(size: 11))
                    .foregroundStyle(Tokens.UI.faint)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(12)
        .background(RoundedRectangle(cornerRadius: 10).fill(Tokens.UI.surface2))
        .overlay(
            RoundedRectangle(cornerRadius: 10)
                .stroke(state.isWorking ? Tokens.UI.accentBorder : Tokens.UI.border,
                        lineWidth: state.isWorking ? 1 : 0.5)
        )
    }

    private func line(_ who: String, _ what: String, _ color: Color) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(who.uppercased())
                .font(.system(size: 9, weight: .medium, design: .monospaced))
                .kerning(0.5)
                .foregroundStyle(Tokens.UI.faint)
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
                    .foregroundStyle(Tokens.UI.accentContrast)
                    .padding(.horizontal, 14)
                    .padding(.vertical, 6)
                    .background(RoundedRectangle(cornerRadius: 6).fill(Tokens.UI.accent))
            }
            .buttonStyle(.plain)

            if state.isMicrophoneOpen {
                HStack(spacing: 5) {
                    Circle().fill(Tokens.UI.true_).frame(width: 5, height: 5)
                    Text("mic open")
                        .font(.system(size: 10, design: .monospaced))
                        .foregroundStyle(Tokens.UI.muted)
                }
            }

            Spacer()

            Button("Quit") {
                voice.stopListening()
                NSApplication.shared.terminate(nil)
            }
            .buttonStyle(.plain)
            .font(.system(size: 11))
            .foregroundStyle(Tokens.UI.muted)
        }
    }
}

// MARK: - Apple Foundation Model
@available(macOS 15.0, *)
actor AppleFoundationModelManager {
    private var session: LanguageModelSession

    init() {
        self.session = LanguageModelSession(instructions: SpacePilotInstructions.system)
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
        let response = try await session.respond(to: "\(block)\n\n\(userText)")
        return response.content
    }
}
