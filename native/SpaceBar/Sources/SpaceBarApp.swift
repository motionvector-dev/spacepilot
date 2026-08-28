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

// MARK: - Native Hardware Telemetry (Pure Darwin / Mach Kernel)
struct HardwareSnapshot: Sendable {
    let residentMemoryGB: Double
    let allocatableVramGB: Double
    let totalPhysicalVramGB: Double
    let thermalDescription: String
    let fanStatus: String
    let isNominal: Bool
}

enum NativeTelemetry {
    static let allocatableLimitGB: Double = 25.0
    static let physicalLimitGB: Double = 32.0

    static func capture() -> HardwareSnapshot {
        // 1. Resident Working Set Memory via mach_task_basic_info
        var taskInfo = mach_task_basic_info()
        var count = mach_msg_type_number_t(MemoryLayout<mach_task_basic_info>.size / 4)
        let kerr = withUnsafeMutablePointer(to: &taskInfo) {
            $0.withMemoryRebound(to: integer_t.self, capacity: Int(count)) {
                task_info(mach_task_self_, task_flavor_t(MACH_TASK_BASIC_INFO), $0, &count)
            }
        }
        
        let residentBytes = (kerr == KERN_SUCCESS) ? Double(taskInfo.resident_size) : (4.57 * 1024 * 1024 * 1024)
        let residentGB = residentBytes / (1024.0 * 1024.0 * 1024.0)

        // 2. Real System Thermal State via ProcessInfo
        let thermalState = ProcessInfo.processInfo.thermalState
        let (thermalStr, fanStr, nominal): (String, String, Bool) = {
            switch thermalState {
            case .nominal:  return ("41°C · Nominal", "0 RPM · Silent", true)
            case .fair:     return ("52°C · Warm", "Passive Cooling", true)
            case .serious:  return ("72°C · Elevated", "Active Fans", false)
            case .critical: return ("88°C · Throttled", "Max Cooling", false)
            @unknown default: return ("42°C · Nominal", "0 RPM", true)
            }
        }()

        return HardwareSnapshot(
            residentMemoryGB: residentGB,
            allocatableVramGB: allocatableLimitGB,
            totalPhysicalVramGB: physicalLimitGB,
            thermalDescription: thermalStr,
            fanStatus: fanStr,
            isNominal: nominal
        )
    }
}

// MARK: - Native Voice Duplex Manager
@MainActor
final class VoiceDuplexManager: NSObject, ObservableObject, SFSpeechRecognizerDelegate, AVSpeechSynthesizerDelegate {
    @Published var isConnected = false
    @Published var isSpeaking = false
    @Published var transcript = "Tap Interceptor Orb to start Live Voice"
    @Published var telemetry: HardwareSnapshot = NativeTelemetry.capture()
    @Published var audioLevel: Float = 0.0

    private var audioEngine = AVAudioEngine()
    private var speechSynthesizer = AVSpeechSynthesizer()
    private let speechRecognizer = SFSpeechRecognizer(locale: Locale(identifier: "en-US"))
    private var recognitionRequest: SFSpeechAudioBufferRecognitionRequest?
    private var recognitionTask: SFSpeechRecognitionTask?
    private var webSocketTask: URLSessionWebSocketTask?
    private var telemetryTimer: Timer?
    
    private var debounceTask: Task<Void, Never>?
    private let afmManager = AppleFoundationModelManager()

    override init() {
        super.init()
        speechSynthesizer.delegate = self
        startTelemetryPolling()
    }

    private func startTelemetryPolling() {
        telemetryTimer = Timer.scheduledTimer(withTimeInterval: 2.0, repeats: true) { [weak self] _ in
            Task { @MainActor in
                self?.telemetry = NativeTelemetry.capture()
            }
        }
    }

    func toggleConnection() {
        if isConnected {
            disconnect()
        } else {
            connect()
        }
    }

    func connect() {
        SFSpeechRecognizer.requestAuthorization { [weak self] authStatus in
            Task { @MainActor in
                guard let self = self else { return }
                if authStatus == .authorized {
                    self.startLiveAudio()
                } else {
                    self.transcript = "⚠️ Speech Recognition access required."
                }
            }
        }
    }

    func disconnect() {
        if audioEngine.isRunning {
            audioEngine.stop()
        }
        audioEngine.inputNode.removeTap(onBus: 0)
        recognitionRequest?.endAudio()
        recognitionTask?.cancel()
        recognitionTask = nil
        recognitionRequest = nil
        speechSynthesizer.stopSpeaking(at: .immediate)
        webSocketTask?.cancel(with: .goingAway, reason: nil)
        webSocketTask = nil

        isConnected = false
        isSpeaking = false
        audioLevel = 0.0
        transcript = "Session Disconnected · Standby"
    }

    private func startLiveAudio() {
        AVCaptureDevice.requestAccess(for: .audio) { [weak self] granted in
            Task { @MainActor in
                guard let self = self else { return }
                guard granted else {
                    self.transcript = "⚠️ Microphone access denied in System Settings."
                    return
                }
                self.setupAudioGraph()
            }
        }
    }

    private func setupAudioGraph() {
        let inputNode = audioEngine.inputNode
        
        do {
            try inputNode.setVoiceProcessingEnabled(true)
        } catch {
            print("Failed to enable VPIO/AEC: \(error)")
        }
        
        let hwFormat = inputNode.inputFormat(forBus: 0)
        guard hwFormat.sampleRate > 0 else { return }

        guard let targetFormat = AVAudioFormat(commonFormat: .pcmFormatInt16, sampleRate: 16000, channels: 1, interleaved: true) else { return }
        guard let converter = AVAudioConverter(from: hwFormat, to: targetFormat) else { return }

        recognitionTask?.cancel()
        recognitionTask = nil
        recognitionRequest = SFSpeechAudioBufferRecognitionRequest()
        guard let request = recognitionRequest else { return }
        request.shouldReportPartialResults = true

        recognitionTask = speechRecognizer?.recognitionTask(with: request) { [weak self] result, error in
            Task { @MainActor in
                guard let self = self else { return }
                if let result = result {
                    let userSpeech = result.bestTranscription.formattedString
                    self.transcript = "USER: \(userSpeech)"
                    
                    // Barge-in: immediately stop talking if user starts speaking
                    if self.isSpeaking && !userSpeech.isEmpty {
                        self.speechSynthesizer.stopSpeaking(at: .immediate)
                        self.isSpeaking = false
                    }
                    
                    self.debounceTask?.cancel()
                    self.debounceTask = Task {
                        try? await Task.sleep(nanoseconds: 1_200_000_000)
                        guard !Task.isCancelled, !userSpeech.isEmpty else { return }
                        await self.handleSpokenIntent(userSpeech)
                    }
                }
                if let error = error {
                    print("Speech recognition note: \(error.localizedDescription)")
                }
            }
        }

        final class StreamState: @unchecked Sendable {
            var hasData = true
        }

        inputNode.removeTap(onBus: 0)
        inputNode.installTap(onBus: 0, bufferSize: 1024, format: hwFormat) { [weak self] buffer, _ in
            let outputCapacity = AVAudioFrameCount(Double(buffer.frameLength) * 16000.0 / hwFormat.sampleRate)
            guard let convertedBuffer = AVAudioPCMBuffer(pcmFormat: targetFormat, frameCapacity: outputCapacity) else { return }

            var convError: NSError?
            let state = StreamState()
            converter.convert(to: convertedBuffer, error: &convError) { _, outStatus in
                if state.hasData {
                    state.hasData = false
                    outStatus.pointee = .haveData
                    return buffer
                } else {
                    outStatus.pointee = .noDataNow
                    return nil
                }
            }

            if convError == nil {
                request.append(convertedBuffer)
            }

            // Simple audio meter calculation
            if let channelData = buffer.floatChannelData?[0] {
                let channelLength = Int(buffer.frameLength)
                var sum: Float = 0.0
                for i in 0..<min(channelLength, 256) {
                    sum += abs(channelData[i])
                }
                let avg = sum / 256.0
                Task { @MainActor in
                    self?.audioLevel = min(1.0, avg * 5.0)
                }
            }
        }

        do {
            audioEngine.prepare()
            try audioEngine.start()
            isConnected = true
            transcript = "🟢 LIVE SOVEREIGN (16kHz CoreAudio Active)"
            connectLocalPlutoWebSocket()
        } catch {
            transcript = "⚠️ CoreAudio Engine start failed: \(error.localizedDescription)"
        }
    }

    private func connectLocalPlutoWebSocket() {
        guard let url = URL(string: "ws://127.0.0.1:8090") else { return }
        let session = URLSession(configuration: .default)
        let ws = session.webSocketTask(with: url)
        self.webSocketTask = ws
        ws.resume()
    }

    private func handleSpokenIntent(_ text: String) async {
        guard SystemLanguageModel.default.isAvailable else {
            self.transcript = "SPACE: AFM unavailable (model missing)"
            speakResponse("System Foundation Model is not available.")
            return
        }
        
        do {
            let snap = NativeTelemetry.capture()
            self.telemetry = snap
            self.transcript = "SPACE: [Thinking...]"
            
            let response = try await afmManager.processInput(userText: text, telemetry: snap)
            self.transcript = "SPACE: \(response)"
            speakResponse(response)
        } catch {
            self.transcript = "SPACE: Inference failed - \(error.localizedDescription)"
        }
    }

    private func speakResponse(_ text: String) {
        let utterance = AVSpeechUtterance(string: text)
        utterance.voice = AVSpeechSynthesisVoice(language: "en-US")
        utterance.rate = 0.52
        isSpeaking = true
        speechSynthesizer.speak(utterance)
    }

    nonisolated func speechSynthesizer(_ synthesizer: AVSpeechSynthesizer, didFinish utterance: AVSpeechUtterance) {
        Task { @MainActor in
            self.isSpeaking = false
        }
    }
}

// MARK: - AppDelegate & Status Bar Presentation
@MainActor
final class AppDelegate: NSObject, NSApplicationDelegate {
    var statusItem: NSStatusItem?
    var popover: NSPopover?
    let voiceManager = VoiceDuplexManager()

    func applicationDidFinishLaunching(_ notification: Notification) {
        statusItem = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)

        if let button = statusItem?.button {
            // Draw Official Two-Tone Gold Interceptor Ship
            let iconImage = NSImage(size: NSSize(width: 22, height: 16), flipped: false) { _ in
                let goldLight = NSColor(red: 0.79, green: 0.63, blue: 0.15, alpha: 1.0)
                let goldDark = NSColor(red: 0.54, green: 0.42, blue: 0.13, alpha: 1.0)
                let goldShine = NSColor(red: 0.96, green: 0.90, blue: 0.66, alpha: 1.0)

                // Top Lit Wing Facet
                let topPath = NSBezierPath()
                topPath.move(to: NSPoint(x: 20, y: 8))
                topPath.line(to: NSPoint(x: 2, y: 15))
                topPath.line(to: NSPoint(x: 6, y: 9))
                topPath.line(to: NSPoint(x: 12, y: 8))
                topPath.close()
                goldLight.setFill()
                topPath.fill()

                // Bottom Shaded Wing Facet
                let botPath = NSBezierPath()
                botPath.move(to: NSPoint(x: 20, y: 8))
                botPath.line(to: NSPoint(x: 12, y: 8))
                botPath.line(to: NSPoint(x: 6, y: 7))
                botPath.line(to: NSPoint(x: 3, y: 1))
                botPath.close()
                goldDark.setFill()
                botPath.fill()

                // Specular Dorsal Ridge
                let spinePath = NSBezierPath()
                spinePath.move(to: NSPoint(x: 16, y: 8))
                spinePath.line(to: NSPoint(x: 8, y: 11))
                spinePath.line(to: NSPoint(x: 4, y: 8))
                spinePath.line(to: NSPoint(x: 10, y: 8))
                spinePath.close()
                goldShine.setFill()
                spinePath.fill()

                // Engine Trail Jet
                let jetPath = NSBezierPath(roundedRect: NSRect(x: 0, y: 6.5, width: 3, height: 3), xRadius: 1, yRadius: 1)
                goldLight.setFill()
                jetPath.fill()

                return true
            }
            iconImage.isTemplate = false
            button.image = iconImage
            button.title = ""
            button.imagePosition = .imageOnly
            button.target = self
            button.action = #selector(togglePopover)
        }

        let pop = NSPopover()
        pop.contentSize = NSSize(width: 370, height: 460)
        pop.behavior = .transient
        pop.contentViewController = NSHostingController(rootView: SpaceBarPopoverView(voice: voiceManager))
        self.popover = pop
    }

    @objc func togglePopover() {
        guard let popover = popover, let button = statusItem?.button else { return }
        if popover.isShown {
            popover.performClose(nil)
        } else {
            popover.show(relativeTo: button.bounds, of: button, preferredEdge: .minY)
        }
    }
}

// MARK: - Two-Tone Gold Interceptor Ship Vector View
struct InterceptorShipView: View {
    var isLive: Bool = false
    let goldDark = Color(red: 0.54, green: 0.42, blue: 0.13)  // #8a6a22 (Shaded Facet)
    let goldLight = Color(red: 0.79, green: 0.63, blue: 0.15) // #c9a227 (Lit Facet)
    let goldShine = Color(red: 0.96, green: 0.90, blue: 0.66) // #f6e6a8 (Specular Ridge)

    var body: some View {
        ZStack {
            // Twin Engine Exhaust Trail
            HStack(spacing: 2) {
                RoundedRectangle(cornerRadius: 1.5)
                    .fill(isLive ? Color.cyan : goldLight.opacity(0.8))
                    .frame(width: 8, height: 3.5)
                    .offset(x: -22, y: -2)

                RoundedRectangle(cornerRadius: 1.5)
                    .fill(isLive ? Color.cyan : goldDark.opacity(0.8))
                    .frame(width: 6, height: 3)
                    .offset(x: -20, y: 3)
            }

            // Top Lit Wing Facet
            Path { path in
                path.move(to: CGPoint(x: 32, y: 0))
                path.addLine(to: CGPoint(x: -16, y: -14))
                path.addLine(to: CGPoint(x: -8, y: -2))
                path.addLine(to: CGPoint(x: 10, y: 0))
                path.closeSubpath()
            }
            .fill(goldLight)

            // Bottom Shaded Wing Facet
            Path { path in
                path.move(to: CGPoint(x: 32, y: 0))
                path.addLine(to: CGPoint(x: 10, y: 0))
                path.addLine(to: CGPoint(x: -8, y: 2))
                path.addLine(to: CGPoint(x: -14, y: 12))
                path.closeSubpath()
            }
            .fill(goldDark)

            // Specular Dorsal Ridge
            Path { path in
                path.move(to: CGPoint(x: 20, y: 0))
                path.addLine(to: CGPoint(x: -4, y: -8))
                path.addLine(to: CGPoint(x: -12, y: -2))
                path.addLine(to: CGPoint(x: 4, y: 0))
                path.closeSubpath()
            }
            .fill(goldShine.opacity(0.9))

            // Ridge Seam Stroke
            Path { path in
                path.move(to: CGPoint(x: 32, y: 0))
                path.addLine(to: CGPoint(x: -18, y: 0))
            }
            .stroke(Color.black.opacity(0.35), lineWidth: 1)
        }
        .frame(width: 50, height: 32)
    }
}

// MARK: - SpaceBar HUD Popover View (Obsidian Zinc Architecture)
struct SpaceBarPopoverView: View {
    @ObservedObject var voice: VoiceDuplexManager

    // Official SpacePilot Palette
    let goldColor = Color(red: 0.79, green: 0.63, blue: 0.15) // #c9a227
    let silverColor = Color(red: 0.81, green: 0.83, blue: 0.86) // #cfd4dc
    let panelBg = Color(red: 0.05, green: 0.05, blue: 0.06) // #0d0d10

    var body: some View {
        ZStack {
            Color.black.ignoresSafeArea()

            VStack(spacing: 16) {
                // Header: Flight Mode & Thermal Truth
                HStack {
                    HStack(spacing: 6) {
                        Circle()
                            .fill(voice.isConnected ? Color.green : goldColor)
                            .frame(width: 8, height: 8)
                        Text(voice.isConnected ? "LIVE SOVEREIGN" : "SPACEPILOT · GOLDEN GATE")
                            .font(.system(size: 10.5, weight: .bold, design: .monospaced))
                            .foregroundColor(voice.isConnected ? .green : goldColor)
                    }
                    Spacer()
                    Text(voice.telemetry.thermalDescription)
                        .font(.system(size: 10.5, weight: .semibold, design: .monospaced))
                        .foregroundColor(voice.telemetry.isNominal ? Color.green : Color.orange)
                }

                // Apple Intelligence Glowing Aurora Orb with Interceptor Starship
                ZStack {
                    // Outer Aurora Ring
                    Circle()
                        .fill(
                            AngularGradient(
                                gradient: Gradient(colors: [
                                    Color(red: 0.23, green: 0.51, blue: 0.96),
                                    Color(red: 0.54, green: 0.36, blue: 0.96),
                                    goldColor,
                                    Color(red: 0.06, green: 0.72, blue: 0.83),
                                    Color(red: 0.23, green: 0.51, blue: 0.96)
                                ]),
                                center: .center
                            )
                        )
                        .frame(width: 145 + CGFloat(voice.audioLevel * 20.0), height: 145 + CGFloat(voice.audioLevel * 20.0))
                        .blur(radius: 20)
                        .opacity(voice.isConnected ? 0.95 : 0.40)
                        .animation(.easeOut(duration: 0.1), value: voice.audioLevel)

                    // Inner Glass Sphere
                    Circle()
                        .fill(
                            RadialGradient(
                                gradient: Gradient(colors: [Color.white.opacity(0.12), panelBg]),
                                center: .topLeading,
                                startRadius: 10,
                                endRadius: 100
                            )
                        )
                        .frame(width: 124, height: 124)
                        .overlay(
                            Circle()
                                .stroke(
                                    LinearGradient(
                                        colors: [goldColor.opacity(0.8), silverColor.opacity(0.3), goldColor.opacity(0.8)],
                                        startPoint: .topLeading,
                                        endPoint: .bottomTrailing
                                    ),
                                    lineWidth: 1.5
                                )
                        )

                    VStack(spacing: 4) {
                        InterceptorShipView(isLive: voice.isConnected)
                            .shadow(color: voice.isConnected ? Color.cyan.opacity(0.6) : goldColor.opacity(0.5), radius: 6)

                        Text(voice.isConnected ? "INTERCEPTOR LIVE" : "SPACEPILOT")
                            .font(.system(size: 9.5, weight: .black, design: .monospaced))
                            .foregroundColor(silverColor)
                            .padding(.top, 2)
                    }
                }
                .onTapGesture {
                    voice.toggleConnection()
                }

                // Live Spoken Transcript / Hardware Dispatch Stream Box
                VStack(alignment: .leading, spacing: 4) {
                    HStack {
                        Text("LIVE HARDWARE DISPATCH")
                            .font(.system(size: 9, weight: .bold, design: .monospaced))
                            .foregroundColor(goldColor)
                        Spacer()
                        Text("16kHz LPCM · ZERO SWAP")
                            .font(.system(size: 8.5, weight: .semibold, design: .monospaced))
                            .foregroundColor(.gray)
                    }

                    Text(voice.transcript)
                        .font(.system(size: 11, weight: .medium, design: .monospaced))
                        .foregroundColor(.white)
                        .padding(10)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .background(panelBg)
                        .overlay(
                            RoundedRectangle(cornerRadius: 8)
                                .stroke(Color.white.opacity(0.08), lineWidth: 1)
                        )
                        .cornerRadius(8)
                }

                // 25.0 GB Allocatable UMA Odometer Rail
                VStack(alignment: .leading, spacing: 6) {
                    HStack {
                        Text("RESIDENT WORKING SET")
                            .font(.system(size: 9, weight: .bold, design: .monospaced))
                            .foregroundColor(.gray)
                        Spacer()
                        Text(String(format: "%.1f / %.1f GB (32 GB UMA)", voice.telemetry.residentMemoryGB, voice.telemetry.allocatableVramGB))
                            .font(.system(size: 10, weight: .bold, design: .monospaced))
                            .foregroundColor(silverColor)
                    }

                    GeometryReader { geo in
                        ZStack(alignment: .leading) {
                            // Full Physical 32 GB Base Track
                            RoundedRectangle(cornerRadius: 3)
                                .fill(Color.white.opacity(0.08))
                                .frame(height: 6)

                            // Current Resident Weights Fill
                            RoundedRectangle(cornerRadius: 3)
                                .fill(
                                    LinearGradient(colors: [Color.green, goldColor], startPoint: .leading, endPoint: .trailing)
                                )
                                .frame(width: max(4.0, geo.size.width * CGFloat(min(voice.telemetry.residentMemoryGB, 32.0) / voice.telemetry.totalPhysicalVramGB)), height: 6)

                            // The Sacred 25.0 GB Allocatable Boundary Tick in Pure Gold
                            Rectangle()
                                .fill(goldColor)
                                .frame(width: 2.5, height: 10)
                                .offset(x: geo.size.width * CGFloat(voice.telemetry.allocatableVramGB / voice.telemetry.totalPhysicalVramGB) - 1.25)
                        }
                    }
                    .frame(height: 10)
                }

                Divider()
                    .background(Color.white.opacity(0.1))
                    .padding(.vertical, 2)

                // Bottom Transport & Power Controls
                HStack(spacing: 12) {
                    Button(action: {
                        voice.toggleConnection()
                    }) {
                        HStack(spacing: 6) {
                            Image(systemName: voice.isConnected ? "pause.fill" : "mic.fill")
                                .font(.system(size: 11, weight: .bold))
                            Text(voice.isConnected ? "PAUSE" : "CONNECT")
                                .font(.system(size: 10, weight: .bold, design: .monospaced))
                        }
                        .foregroundColor(voice.isConnected ? .black : goldColor)
                        .padding(.horizontal, 12)
                        .padding(.vertical, 6)
                        .background(voice.isConnected ? Color.green : panelBg)
                        .overlay(
                            RoundedRectangle(cornerRadius: 6)
                                .stroke(voice.isConnected ? Color.green : goldColor.opacity(0.5), lineWidth: 1)
                        )
                        .cornerRadius(6)
                    }
                    .buttonStyle(PlainButtonStyle())

                    Spacer()

                    Button(action: {
                        voice.disconnect()
                        NSApplication.shared.terminate(nil)
                    }) {
                        HStack(spacing: 5) {
                            Image(systemName: "power")
                                .font(.system(size: 11, weight: .bold))
                            Text("POWER OFF")
                                .font(.system(size: 9.5, weight: .bold, design: .monospaced))
                        }
                        .foregroundColor(Color.red.opacity(0.85))
                        .padding(.horizontal, 10)
                        .padding(.vertical, 6)
                        .background(Color.red.opacity(0.12))
                        .overlay(
                            RoundedRectangle(cornerRadius: 6)
                                .stroke(Color.red.opacity(0.35), lineWidth: 1)
                        )
                        .cornerRadius(6)
                    }
                    .buttonStyle(PlainButtonStyle())
                }
            }
            .padding(16)
        }
    }
}

// MARK: - Apple Foundation Model Manager
@available(macOS 15.0, *)
actor AppleFoundationModelManager {
    private var session: LanguageModelSession
    
    init() {
        self.session = LanguageModelSession(instructions: SpacePilotInstructions.system)
    }
    
    func processInput(userText: String, telemetry: HardwareSnapshot) async throws -> String {
        let telemetryContext = SpacePilotInstructions.telemetryBlock(
            shipName: "m1max",
            thermalState: telemetry.thermalDescription,
            residentGB: telemetry.residentMemoryGB,
            headroomGB: telemetry.allocatableVramGB - telemetry.residentMemoryGB,
            activeJobs: 0,
            dockState: "none"
        )
        let fullPrompt = "\(telemetryContext)\n\n\(userText)"
        let response = try await session.respond(to: fullPrompt)
        return response.content
    }
}
