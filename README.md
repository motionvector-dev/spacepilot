# 🎙️ space-voice (mvec-voice)

> **VoicePilot**: Native macOS real-time, full-duplex voice pair-programming assistant powered by the Google Gemini Multimodal Live API.

`space-voice` is part of the MotionVector modular modality ecosystem:
* `space-voice` (Real-Time Voice Assistant)
* `space-video` (LTX / Wan Video Generation)
* `space-audio` / `space-music` (Kokoro / MiniMax Music)
* `space-image` (FLUX / Sana)
* `space-lm` / `space-code` (MLX / Qwen Code)
* `space-transcribe` (Moonshine / SenseVoice Streaming ASR)
* `space-motion` (2D/3D Vello & Vector Render Engine)
* `space-mvec` (Ultimate Multi-Agent Collaboration Substrate)

---

## ⚡ Features

* **Sub-200ms Full-Duplex Voice**: Bidirectional WebSockets streaming 16kHz linear PCM audio directly with Gemini Live.
* **Instant Interruption (Barge-In)**: Interruption events instantly latch and clear playback buffers when you speak mid-sentence.
* **Asynchronous Tool Execution**: Gemini dispatches live local commands while speaking:
  - `git_status` / `git_diff`: Live workspace state inspection.
  - `read_file`: Surgical code reading.
  - `run_spacepilot_cli`: Direct bridge to `spacepilot probe`, `spacepilot run`, and local telemetry.
* **Zero Hardcoded Secrets**: Fully managed via Doppler (`GEMINI_PRIMARY_API_KEY` / `GOOGLE_API_KEY`).

---

## 🚀 Quickstart

### 1. Prerequisites
Ensure you have `sox` / PortAudio installed on macOS:
```bash
brew install portaudio
```

### 2. Installation
```bash
cd /Users/saurabh/code/motionvector/mvec-voice
doppler run --project unfoundbox --config dev_personal -- pip install -e .
```

### 3. Launch Voice Assistant
```bash
doppler run --project unfoundbox --config dev_personal -- mvec-voice
```

---

## 🔮 Coming Soon: Native SpacePilot Integration

Soon `space-voice` will be deployable directly via the **SpacePilot CLI / MCP tool**:

```bash
# 1. Probe & check audio hardware
spacepilot probe audio

# 2. Run standalone voice assistant
spacepilot run voice --live

# 3. Or invoke through MCP in Claude / Antigravity / OpenCode
spacepilot_run_voice(mode="duplex")
```

---

## 🔒 Security & Secrets

* **Zero Secrets Committed**: No API keys, credentials, or session tokens are committed to this repository.
* Doppler securely resolves `GEMINI_PRIMARY_API_KEY` at runtime.
