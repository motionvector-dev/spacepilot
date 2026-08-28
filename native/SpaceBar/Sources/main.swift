import SwiftUI
import AppKit
import AVFoundation
import Speech

// MARK: - SpaceBar App Entrypoint
@main
struct SpaceBarApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) var appDelegate

    var body: some Scene {
        Settings {
            EmptyView()
        }
    }
}

// MARK: - Native Duplex Voice Manager
class VoiceDuplexManager: NSObject, ObservableObject, SFSpeechRecognizerDelegate, AVSpeechSynthesizerDelegate {
    @Published var isConnected = false
    @Published var isSpeaking = false
    @Published var transcript = "Tap Orb to Start Live Duplex Voice"
    
    private var audioEngine = AVAudioEngine()
    private var speechSynthesizer = AVSpeechSynthesizer()
    private let audioQueue = DispatchQueue(label: "dev.spacepilot.audioQueue", qos: .userInteractive)
    private var isAudioSetup = false
    
    // Speech Recognition
    private let speechRecognizer = SFSpeechRecognizer(locale: Locale(identifier: "en-US"))
    private var recognitionRequest: SFSpeechAudioBufferRecognitionRequest?
    private var recognitionTask: SFSpeechRecognitionTask?
    
    // Debouncer for Intent Parsing
    private var recognitionTimer: Timer?
    private var lastTranscript: String = ""
    
    override init() {
        super.init()
        speechSynthesizer.delegate = self
        // Observe AirPods / Bluetooth dynamic hardware sample rate switches
        NotificationCenter.default.addObserver(
            self,
            selector: #selector(handleAudioConfigurationChange),
            name: .AVAudioEngineConfigurationChange,
            object: audioEngine
        )
    }
    
    @objc private func handleAudioConfigurationChange() {
        audioQueue.async { [weak self] in
            guard let self = self, self.isConnected else { return }
            self.setupAudioEngine()
        }
    }
    
    func connect() {
        SFSpeechRecognizer.requestAuthorization { authStatus in
            DispatchQueue.main.async {
                if authStatus == .authorized {
                    self.startAudioCapture()
                } else {
                    self.transcript = "⚠️ Speech Recognition Access Denied"
                }
            }
        }
    }
    
    func disconnect() {
        audioQueue.async { [weak self] in
            guard let self = self else { return }
            if self.audioEngine.isRunning {
                self.audioEngine.stop()
            }
            self.audioEngine.inputNode.removeTap(onBus: 0)
            self.recognitionRequest?.endAudio()
            self.recognitionTask?.cancel()
            self.speechSynthesizer.stopSpeaking(at: .immediate)
            
            DispatchQueue.main.async {
                self.isConnected = false
                self.transcript = "Session Disconnected"
            }
        }
    }
    
    private func startAudioCapture() {
        AVCaptureDevice.requestAccess(for: .audio) { [weak self] granted in
            guard let self = self else { return }
            if !granted {
                DispatchQueue.main.async {
                    self.transcript = "⚠️ Microphone access denied in System Settings."
                }
                return
            }
            
            self.audioQueue.async {
                self.setupAudioEngine()
            }
        }
    }

    private func setupAudioEngine() {
        let inputNode = audioEngine.inputNode
        let hwFormat = inputNode.inputFormat(forBus: 0)
        guard hwFormat.sampleRate > 0 else { return }
        
        guard let targetFormat = AVAudioFormat(commonFormat: .pcmFormatInt16, sampleRate: 16000, channels: 1, interleaved: true) else { return }
        guard let converter = AVAudioConverter(from: hwFormat, to: targetFormat) else { return }
        
        // Setup Speech Recognition Request
        recognitionTask?.cancel()
        recognitionTask = nil
        recognitionRequest = SFSpeechAudioBufferRecognitionRequest()
        guard let recognitionRequest = recognitionRequest else { return }
        recognitionRequest.shouldReportPartialResults = true
        if speechRecognizer?.supportsOnDeviceRecognition == true {
            recognitionRequest.requiresOnDeviceRecognition = false // Allow automatic high-accuracy fallback
        }
        
        recognitionTask = speechRecognizer?.recognitionTask(with: recognitionRequest) { [weak self] result, error in
            guard let self = self else { return }
            if let result = result {
                let text = result.bestTranscription.formattedString
                DispatchQueue.main.async {
                    self.transcript = "USER: \(text)"
                }
                
                // Immediate check for hardware intent
                let lower = text.lowercased()
                if lower.contains("fan") || lower.contains("noise") || lower.contains("memory") || lower.contains("space") || lower.contains("status") {
                    self.recognitionTimer?.invalidate()
                    self.recognitionTimer = Timer.scheduledTimer(withTimeInterval: 0.8, repeats: false) { _ in
                        self.processIntent(text: text)
                    }
                }
            }
            if let error = error {
                print("Speech recognition error: \(error.localizedDescription)")
            }
        }
        
        inputNode.removeTap(onBus: 0)
        
        inputNode.installTap(onBus: 0, bufferSize: 1024, format: hwFormat) { [weak self] buffer, _ in
            guard let self = self, self.isConnected else { return }
            
            let outputFrameCapacity = AVAudioFrameCount(Double(buffer.frameLength) * 16000.0 / hwFormat.sampleRate)
            guard let convertedBuffer = AVAudioPCMBuffer(pcmFormat: targetFormat, frameCapacity: outputFrameCapacity) else { return }
            
            var error: NSError?
            var isEndOfStream = false
            converter.convert(to: convertedBuffer, error: &error) { inNumPackets, outStatus in
                if isEndOfStream {
                    outStatus.pointee = .noDataNow
                    return nil
                }
                outStatus.pointee = .haveData
                isEndOfStream = true
                return buffer
            }
            
            if error == nil {
                self.recognitionRequest?.append(convertedBuffer)
            }
        }
        
        audioEngine.prepare()
        try? audioEngine.start()
        
        DispatchQueue.main.async {
            self.isConnected = true
            self.transcript = "🟢 LIVE SOVEREIGN (Connected)"
        }
    }
    
    private func processIntent(text: String) {
        let lower = text.lowercased()
        if lower.contains("space") && lower.contains("fans") {
            dispatchHardwareTelemetry()
        }
    }
    
    private func dispatchHardwareTelemetry() {
        let task = Process()
        task.launchPath = "/usr/bin/env"
        task.arguments = ["python3", Bundle.main.bundlePath + "/Contents/Resources/telemetry.py"]
        
        let pipe = Pipe()
        task.standardOutput = pipe
        
        // Fallback if resource not found (dev mode)
        var telemetryScriptPath = Bundle.main.bundlePath + "/Contents/Resources/telemetry.py"
        if !FileManager.default.fileExists(atPath: telemetryScriptPath) {
            telemetryScriptPath = "/Users/saurabh/code/motionvector/spacepilot/native/SpaceBar/telemetry.py"
            task.arguments = ["python3", telemetryScriptPath]
        }
        
        do {
            try task.run()
            let data = pipe.fileHandleForReading.readDataToEndOfFile()
            if let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any] {
                let vram = json["metal_vram"] as? String ?? "25.0 GB"
                let thermals = json["thermals"] as? String ?? "42°C"
                var procString = ""
                if let procs = json["top_processes"] as? [[Any]], let top = procs.first, let name = top[0] as? String {
                    procString = name
                }
                
                let response = "The fans are engaged. System thermal is at \(thermals). Top process is \(procString). Allocatable UMA is at \(vram)."
                DispatchQueue.main.async {
                    self.transcript = "SPACE: \(response)"
                }
                speak(response)
            }
        } catch {
            print("Telemetry fetch failed: \(error)")
        }
    }
    
    private func speak(_ text: String) {
        let utterance = AVSpeechUtterance(string: text)
        utterance.voice = AVSpeechSynthesisVoice(language: "en-US")
        utterance.rate = 0.5
        
        DispatchQueue.main.async {
            self.isSpeaking = true
            self.speechSynthesizer.speak(utterance)
        }
    }
    
    func speechSynthesizer(_ synthesizer: AVSpeechSynthesizer, didFinish utterance: AVSpeechUtterance) {
        DispatchQueue.main.async {
            self.isSpeaking = false
        }
    }
}

// MARK: - AppDelegate & StatusItem
class AppDelegate: NSObject, NSApplicationDelegate {
    var statusItem: NSStatusItem?
    var popover: NSPopover?
    let voiceManager = VoiceDuplexManager()

    func applicationDidFinishLaunching(_ notification: Notification) {
        statusItem = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
        
        if let button = statusItem?.button {
            // Draw Official Golden Interceptor Starship as Menu Bar Icon
            let iconImage = NSImage(size: NSSize(width: 22, height: 16), flipped: false) { rect in
                let goldLight = NSColor(red: 0.79, green: 0.63, blue: 0.15, alpha: 1.0)
                let goldDark = NSColor(red: 0.54, green: 0.42, blue: 0.13, alpha: 1.0)
                let goldShine = NSColor(red: 0.96, green: 0.90, blue: 0.66, alpha: 1.0)

                // Lit Top Wing
                let topPath = NSBezierPath()
                topPath.move(to: NSPoint(x: 20, y: 8))     // Nose
                topPath.line(to: NSPoint(x: 2, y: 15))    // Wingtip top
                topPath.line(to: NSPoint(x: 6, y: 9))     // Seam
                topPath.line(to: NSPoint(x: 12, y: 8))    // Center
                topPath.close()
                goldLight.setFill()
                topPath.fill()

                // Shaded Bottom Wing
                let botPath = NSBezierPath()
                botPath.move(to: NSPoint(x: 20, y: 8))     // Nose
                botPath.line(to: NSPoint(x: 12, y: 8))    // Center
                botPath.line(to: NSPoint(x: 6, y: 7))     // Seam
                botPath.line(to: NSPoint(x: 3, y: 1))     // Wingtip bottom
                botPath.close()
                goldDark.setFill()
                botPath.fill()

                // Specular Dorsal Seam
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
            iconImage.isTemplate = false // Keep full two-tone gold specular colors!
            button.image = iconImage
            button.title = ""
            button.imagePosition = .imageOnly
            button.target = self
            button.action = #selector(togglePopover)
        }

        let popover = NSPopover()
        popover.contentSize = NSSize(width: 370, height: 460)
        popover.behavior = .transient
        popover.contentViewController = NSHostingController(rootView: SpaceBarPopoverView(voice: voiceManager))
        self.popover = popover
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

// MARK: - Official SpacePilot Two-Tone Golden Interceptor Ship Shape
struct InterceptorShipView: View {
    var isLive: Bool = false
    let goldDark = Color(red: 0.54, green: 0.42, blue: 0.13)  // #8a6a22 (Shaded Facet)
    let goldLight = Color(red: 0.79, green: 0.63, blue: 0.15) // #c9a227 (Lit Facet)
    let goldShine = Color(red: 0.96, green: 0.90, blue: 0.66) // #f6e6a8 (Specular Edge)

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

            // Top Lit Wing Facet (Light Gold)
            Path { path in
                path.move(to: CGPoint(x: 32, y: 0))    // Nose tip
                path.addLine(to: CGPoint(x: -16, y: -14)) // Upper wing tip
                path.addLine(to: CGPoint(x: -8, y: -2))   // Upper fuselage seam
                path.addLine(to: CGPoint(x: 10, y: 0))    // Center ridge line
                path.closeSubpath()
            }
            .fill(goldLight)

            // Bottom Shaded Wing Facet (Dark Gold)
            Path { path in
                path.move(to: CGPoint(x: 32, y: 0))    // Nose tip
                path.addLine(to: CGPoint(x: 10, y: 0))    // Center ridge line
                path.addLine(to: CGPoint(x: -8, y: 2))    // Lower fuselage seam
                path.addLine(to: CGPoint(x: -14, y: 12))  // Lower wing tip
                path.closeSubpath()
            }
            .fill(goldDark)

            // Cockpit Dorsal Fin Facet (Specular Highlight)
            Path { path in
                path.move(to: CGPoint(x: 20, y: 0))
                path.addLine(to: CGPoint(x: -4, y: -8))
                path.addLine(to: CGPoint(x: -12, y: -2))
                path.addLine(to: CGPoint(x: 4, y: 0))
                path.closeSubpath()
            }
            .fill(goldShine.opacity(0.9))

            // Ridge Line Stroke
            Path { path in
                path.move(to: CGPoint(x: 32, y: 0))
                path.addLine(to: CGPoint(x: -18, y: 0))
            }
            .stroke(Color.black.opacity(0.35), lineWidth: 1)
        }
        .frame(width: 50, height: 32)
    }
}

// MARK: - SpaceBar Native SwiftUI Popover View (Golden Gateway Edition)
struct SpaceBarPopoverView: View {
    @ObservedObject var voice: VoiceDuplexManager
    @State private var vramUsed: Double = 4.57
    let allocatableVram: Double = 25.0
    let totalPhysicalVram: Double = 32.0

    // spacepilot.dev Official Palette
    let goldColor = Color(red: 0.79, green: 0.63, blue: 0.15) // #c9a227
    let silverColor = Color(red: 0.81, green: 0.83, blue: 0.86) // #cfd4dc
    let panelBg = Color(red: 0.05, green: 0.05, blue: 0.06) // #0d0d10

    var body: some View {
        ZStack {
            // Deep Obsidian Background
            Color.black.ignoresSafeArea()

            VStack(spacing: 16) {
                // Header Bar with Gold Brand Badge & Official Interceptor Silhouette
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
                    Text("42°C · 0 RPM")
                        .font(.system(size: 11, weight: .semibold, design: .monospaced))
                        .foregroundColor(Color.green)
                }

                // Apple Intelligence Glowing Aurora Orb with Two-Tone Gold Interceptor Ship
                ZStack {
                    // Outer Aurora Spin Blur
                    Circle()
                        .fill(
                            AngularGradient(
                                gradient: Gradient(colors: [
                                    Color(red: 0.23, green: 0.51, blue: 0.96), // Cyber Blue
                                    Color(red: 0.54, green: 0.36, blue: 0.96), // Purple
                                    goldColor,                                 // SpacePilot Gold
                                    Color(red: 0.06, green: 0.72, blue: 0.83), // Cyan
                                    Color(red: 0.23, green: 0.51, blue: 0.96)
                                ]),
                                center: .center
                            )
                        )
                        .frame(width: 145, height: 145)
                        .blur(radius: 22)
                        .opacity(voice.isConnected ? 0.95 : 0.45)

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
                        // The Sacred Official Two-Tone Interceptor Ship!
                        InterceptorShipView(isLive: voice.isConnected)
                            .shadow(color: voice.isConnected ? Color.cyan.opacity(0.6) : goldColor.opacity(0.5), radius: 6)

                        Text(voice.isConnected ? "INTERCEPTOR LIVE" : "SPACEPILOT")
                            .font(.system(size: 9.5, weight: .black, design: .monospaced))
                            .foregroundColor(silverColor)
                            .padding(.top, 2)
                    }
                }
                .onTapGesture {
                    if voice.isConnected {
                        voice.disconnect()
                    } else {
                        voice.connect()
                    }
                }

                // Live Intent / Transcript Stream Box
                VStack(alignment: .leading, spacing: 4) {
                    HStack {
                        Text("LIVE HARDWARE DISPATCH")
                            .font(.system(size: 9, weight: .bold, design: .monospaced))
                            .foregroundColor(goldColor)
                        Spacer()
                        Text("16kHz LPCM")
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

                // 25.0 GB UMA Odometer Rail (Golden Tick)
                VStack(alignment: .leading, spacing: 6) {
                    HStack {
                        Text("RESIDENT WORKING SET")
                            .font(.system(size: 9, weight: .bold, design: .monospaced))
                            .foregroundColor(.gray)
                        Spacer()
                        Text(String(format: "%.1f / %.1f GB (32 GB UMA)", vramUsed, allocatableVram))
                            .font(.system(size: 10, weight: .bold, design: .monospaced))
                            .foregroundColor(silverColor)
                    }

                    GeometryReader { geo in
                        ZStack(alignment: .leading) {
                            RoundedRectangle(cornerRadius: 3)
                                .fill(Color.white.opacity(0.08))
                                .frame(height: 6)

                            RoundedRectangle(cornerRadius: 3)
                                .fill(
                                    LinearGradient(colors: [Color.green, goldColor], startPoint: .leading, endPoint: .trailing)
                                )
                                .frame(width: geo.size.width * CGFloat(vramUsed / totalPhysicalVram), height: 6)

                            // The 25.0 GB Boundary Tick in Pure Gold
                            Rectangle()
                                .fill(goldColor)
                                .frame(width: 2.5, height: 10)
                                .offset(x: geo.size.width * CGFloat(allocatableVram / totalPhysicalVram) - 1.25)
                        }
                    }
                    .frame(height: 10)
                }

                Divider()
                    .background(Color.white.opacity(0.1))
                    .padding(.vertical, 2)

                // Stats-style Power & Playback Control Strip
                HStack(spacing: 12) {
                    // Play / Pause Duplex Voice Room
                    Button(action: {
                        if voice.isConnected {
                            voice.disconnect()
                        } else {
                            voice.connect()
                        }
                    }) {
                        HStack(spacing: 6) {
                            Image(systemName: voice.isConnected ? "pause.fill" : "play.fill")
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

                    // Power Off / Quit SpaceBar (Terminates App cleanly)
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
