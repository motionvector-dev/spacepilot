# Technical Specification: SpaceBar Native App Intents, Shortcuts & Apple Intelligence Integration

- **Document ID**: `SP-DESIGN-043`
- **Target Path**: `docs/design/macos-app-intents-apple-intelligence-integration.md`
- **Status**: `PROPOSED / IMPLEMENTATION-READY`
- **Author**: Saurabh Nandwana (SpacePilot Architect)
- **Reference**: Apple Developer Documentation (`AppIntents`, `WidgetKit`, `Apple Intelligence Tool Calling`)

---

## 1. Executive Summary

With the introduction of Apple Intelligence and modern macOS frameworks, **`AppIntents`** serves as the universal integration layer connecting native apps to **Siri, Apple Intelligence Agents, macOS Shortcuts, Spotlight Search, interactive Desktop Widgets, and Finder Quick Actions**.

This specification defines the architecture for **SpaceBar** (`spacebar.app`) to implement native Swift App Intents that communicate with the local **SpacePilot Daemon (Port 8088 / Unix Domain Socket)**. This elevates SpacePilot from a CLI/Web tool into a deeply integrated, first-class Apple Intelligence service across macOS.

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                          MACOS APP INTENTS & AGENT TOPOLOGY                            │
├────────────────────────────────────────────────────────────────────────────────────────┤
│  System Entry Points  │ Siri / Apple Intelligence · Shortcuts · Spotlight · Widgets    │
├───────────────────────┼────────────────────────────────────────────────────────────────┤
│  App Intents Layer    │ Swift 6 AppIntents (GenerateVideo, MountModel, PurgeVRAM, etc.) │
├───────────────────────┼────────────────────────────────────────────────────────────────┤
│  IPC Transport        │ Unix Domain Socket (`/tmp/spacepilot.sock`) / REST localhost   │
├───────────────────────┼────────────────────────────────────────────────────────────────┤
│  SpacePilot Engines   │ Wan 2.1 Engine · mFLUX · SeedVR2 · Kokoro TTS · SpacePilot MCP      │
└───────────────────────┴────────────────────────────────────────────────────────────────┘
```

---

## 2. Core Intent Definitions

SpaceBar exports six primary `AppIntent` classes under the namespace `SpacePilotIntents`:

### 2.1 `GenerateVideoIntent` (Diffusion Pipeline)
Enables Siri and Shortcuts to execute multi-step video diffusion with streaming progress.

```swift
import AppIntents

struct GenerateVideoIntent: AppIntent {
    static var title: LocalizedStringResource = "Generate Video in SpacePilot"
    static var description = IntentDescription("Generates video from text or image prompts using local Metal diffusion engines.")

    @Parameter(title: "Prompt", description: "Text description of the desired video scene")
    var prompt: String

    @Parameter(title: "Model", default: "wan-2.1")
    var model: String

    @Parameter(title: "Frames", default: 81)
    var frames: Int

    @Parameter(title: "Seed", default: nil)
    var seed: Int?

    static var parameterSummary: some ParameterSummary {
        Summary("Generate \(\.$frames) frames video with \(\.$model) from '\(\.$prompt)'")
    }

    func perform() async throws -> some IntentResult & ReturnsValue<URL> & ShowsSnippetView {
        let client = SpacePilotIPCClient.shared
        let job = try await client.dispatchVideo(prompt: prompt, model: model, frames: frames, seed: seed)
        
        // Wait for render completion with streaming progress
        let resultURL = try await client.pollJobCompletion(jobId: job.id)
        
        return .result(
            value: resultURL,
            view: VideoRenderResultSnippetView(videoURL: resultURL, metadata: job)
        )
    }
}
```

---

### 2.2 `MountModelIntent` (Unified Memory Swapper)
Allows voice, shortcuts, or focus filters to pre-warm models into Apple Silicon Unified RAM.

```swift
struct MountModelIntent: AppIntent {
    static var title: LocalizedStringResource = "Mount AI Model into RAM"
    static var description = IntentDescription("Loads model weights into zero-copy Unified Memory.")

    @Parameter(title: "Model Name")
    var modelEntity: ModelEntity

    func perform() async throws -> some IntentResult & ProvidesDialog {
        try await SpacePilotIPCClient.shared.mountModel(modelEntity.id)
        return .result(dialog: "Mounted \(modelEntity.name) into Unified Memory (\(modelEntity.vramFootprint)).")
    }
}
```

---

### 2.3 `PurgeVRAMIntent` (Instant Memory Reclamation)
One-click or automated memory purge to free system RAM for heavy native applications (e.g., Xcode, Final Cut Pro).

```swift
struct PurgeVRAMIntent: AppIntent {
    static var title: LocalizedStringResource = "Purge SpacePilot VRAM"
    static var description = IntentDescription("Dumps all resident AI model weights back to SSD.")

    func perform() async throws -> some IntentResult & ProvidesDialog {
        let freedGB = try await SpacePilotIPCClient.shared.purgeVRAM()
        return .result(dialog: "Purged \(freedGB) GB from Unified Memory. All 32 GB RAM is now available.")
    }
}
```

---

### 2.4 `UpscaleMediaIntent` (SeedVR2 Video Super-Resolution)
Finder Quick Action & Services menu hook for upscaling dropped media.

```swift
struct UpscaleMediaIntent: AppIntent {
    static var title: LocalizedStringResource = "Upscale Video with SeedVR2"
    
    @Parameter(title: "Input Video File")
    var file: IntentFile

    @Parameter(title: "Scale Factor", default: 4)
    var scale: Int

    func perform() async throws -> some IntentResult & ReturnsValue<IntentFile> {
        let outputFile = try await SpacePilotIPCClient.shared.upscale(file: file, scale: scale)
        return .result(value: outputFile)
    }
}
```

---

## 3. Apple Intelligence Semantic Schema (`AppEntity`)

To allow Apple Intelligence to reason about local models and past generations, SpaceBar registers entities with semantic attributes:

```swift
struct ModelEntity: AppEntity {
    static var defaultQuery = ModelEntityQuery()
    static var typeDisplayRepresentation: TypeDisplayRepresentation = "AI Model"

    var id: String
    var name: String
    var task: String // "video_diffusion", "audio_tts", "image_generation"
    var vramFootprint: String
    var format: String // "FP16 Metal", "Q4_K"

    var displayRepresentation: DisplayRepresentation {
        DisplayRepresentation(title: "\(name)", subtitle: "\(format) · \(vramFootprint)")
    }
}

struct ModelEntityQuery: EntityStringQuery {
    func entities(matching string: String) async throws -> [ModelEntity] {
        return try await SpacePilotIPCClient.shared.listModels(matching: string)
    }
    
    func entities(for identifiers: [String]) async throws -> [ModelEntity] {
        return try await SpacePilotIPCClient.shared.getModels(ids: identifiers)
    }
}
```

---

## 4. macOS Shortcuts App Provider (`AppShortcutsProvider`)

SpaceBar pre-registers automatic, discoverable Shortcuts in macOS:

```swift
struct SpaceBarShortcutsProvider: AppShortcutsProvider {
    static var appShortcuts: [AppShortcut] {
        AppShortcut(
            intent: GenerateVideoIntent(),
            phrases: [
                "Generate a video with \(.applicationName)",
                "Create an AI video in \(.applicationName)",
                "Render video scene with SpacePilot"
            ],
            shortTitle: "Generate Video",
            systemImageName: "film"
        )
        AppShortcut(
            intent: PurgeVRAMIntent(),
            phrases: [
                "Purge AI VRAM in \(.applicationName)",
                "Free SpacePilot memory"
            ],
            shortTitle: "Purge AI RAM",
            systemImageName: "memorychip"
        )
    }
}
```

---

## 5. Spotlight Search & Desktop Widget Integration

### 5.1 Spotlight Search Action (`CSSearchableIndex`)
* When user types `"Wan 2.1"` or `"FLUX"` in Spotlight (`⌘ + Space`), Spotlight displays the model card with direct App Intent buttons: `[ Mount ]` and `[ Benchmark ]`.

### 5.2 Interactive WidgetKit Control Center
* **Live Activity / Dynamic Island**: Shows real-time denoising progress during 81-frame video generations.
* **Interactive Control Center Button**: 1-click `Purge VRAM` or `⚡ Max Fan Boost` directly in macOS Control Center.

---

## 6. IPC Protocol: Swift App Intents to Python Daemon

Communication between the sandboxed Swift app shell and the Python `spacepilot` daemon operates over a high-performance **Unix Domain Socket**:

```
[ Swift AppIntent Runtime ]
             │ (JSON-RPC over /tmp/spacepilot.sock)
             ▼
[ spacepilot.daemon.server ] (FastAPI / Uvicorn Socket Server)
             │
             ├─► /api/generate ──► spacepilot.engines.wan_engine
             ├─► /api/gpu ───────► spacepilot.device_probe (SMC/IOKit)
             └─► /api/vram/purge ─► spacepilot.drivers.base.unload_all()
```

---

## 7. Delivery Milestones

| Phase | Milestone | Deliverable |
| :--- | :--- | :--- |
| **Phase 1** | IPC Socket Protocol | Fast local Unix Domain Socket bridge in `spacepilot/daemon/server.py` |
| **Phase 2** | Swift AppIntents Suite | 6 core intents in `SpaceBar/Intents/*.swift` |
| **Phase 3** | Siri & Shortcuts Integration | `AppShortcutsProvider` registration and Siri voice prompts |
| **Phase 4** | Interactive Widgets | Control Center toggles & Desktop HUD dials via `WidgetKit` |
