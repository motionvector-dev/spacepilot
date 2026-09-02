# 🛸 SpacePilot Modality Implementation & Registry Architecture Handoff

> **Target Agent / Architect:** GLM-5.3-Flash & Systems Engineering Team  
> **Repository:** `motionvector/spacepilot`  
> **Status:** Active Execution Phase  

---

## 1. The Core Vision: The Sovereign 3-Command Engine + Mac App

SpacePilot bridges raw Apple Silicon hardware truth with multi-modal AI inference.

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                               SPACEPILOT UNIFIED WORKFLOW                              │
├────────────────────────────────────────────────────────────────────────────────────────┤
│  Non-Technical Users ──► [ SpaceBar macOS Popover / App ] ──► 1-Click Resident Docking │
│  Technical / Agents  ──► [ SpacePilot CLI / MCP Tools   ] ──► Sub-Second Orchestration │
│                                      │                                                 │
│                                      ▼                                                 │
│                     [ LOCAL METAL / ANE INFERENCE ENGINE ]                             │
│                     (25.0 GB Allocatable UMA Working-Set)                              │
│                                      │                                                 │
│                        If local memory/compute saturated                               │
│                                      ▼                                                 │
│                     [ TAILSCALE FLEET OFFLOAD (24ms RTT) ]                             │
│                     (Remote RTX 5090 / Cloud Run / Lambda)                             │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. The 10 Modality Registry & CLI Implementation Matrix

Every modality in SpacePilot follows an immutable contract:
1. **Model Recipe (`spacepilot/registry/models/<id>.yaml`)**:
   - Pinned 40-character commit SHA.
   - Exact download bytes from Hugging Face API.
   - Working set memory footprint and measured hardware speed (`realtime_factor`, `tok/s`, `s/it`).
   - Ground-truth negative caveats (`caveat_lookup`).
2. **Execution Driver (`spacepilot/pluto/drivers/<modality>.py`)**:
   - Sub-second cold-to-warm resident memory loading.
   - Clean AOT CoreML / Metal / MLX pipeline.
3. **Reference Example (`examples/<modality>/`)**:
   - Standalone, working developer harness with zero hardcoded credentials.

```
┌──────┬──────────────────────┬───────────────────────────────┬───────────────────────────────┬──────────────────────┐
│ #    │ MODALITY             │ PRIMARY OPEN-SOURCE MODELS    │ EXECUTION RUNTIME             │ REFERENCE HARNESS    │
├──────┼──────────────────────┼───────────────────────────────┼───────────────────────────────┼──────────────────────┤
│ 1    │ `run voice`          │ Gemini Multimodal Live / Bidi │ WebSocket CoreAudio Stream    │ `examples/voice/`    │
│ 2    │ `run transcribe`     │ Moonshine Tiny / SenseVoice   │ Causal ASR / ONNX / Metal     │ `examples/transcribe/`│
│ 3    │ `run speech`         │ Kokoro 82M (48x RTF)          │ PyTorch / CoreML Metal        │ `examples/speech/`   │
│ 4    │ `run music`          │ MiniMax Music / Stable Audio  │ DiT Latent Diffusion          │ `examples/music/`    │
│ 5    │ `run image`          │ FLUX.1 Schnell / Sana 1.6B    │ mflux / Metal Compute         │ `examples/image/`    │
│ 6    │ `run video`          │ LTX-Video / Wan 2.1           │ Metal / Fleet 5090 Offload    │ `examples/video/`    │
│ 7    │ `run upscaler`       │ FlashVSR / Real-ESRGAN        │ PyTorch Metal VSR             │ `examples/upscaler/` │
│ 8    │ `run text` / `code`  │ Qwen 2.5 7B / DeepSeek-R1     │ MLX-LM (42 tok/s)             │ `examples/code/`     │
│ 9    │ `run vlm`            │ Qwen 2.5 VL / MiniCPM-V       │ MLX Multimodal Vision         │ `examples/vlm/`      │
│ 10   │ `run motion`         │ DocIR / CoreAI Latent Vectors │ Vello Compute Shaders (85µs)  │ `examples/motion/`   │
└──────┴──────────────────────┴───────────────────────────────┴───────────────────────────────┴──────────────────────┘
```

---

## 3. The 3 Hardware Invariants for Implementation

1. **Allocatable Working-Set Boundary (`25.0 GB` on 32GB UMA):**
   - Metal's `recommendedMaxWorkingSetSize` is ~78% of physical RAM.
   - Never allow local model allocation above 25.0 GB without triggering **automatic Fleet Offload**.
2. **Negative Provenance Grounding:**
   - Always implement `caveat_lookup` on quant variants (e.g. `Q4_K` timestamp drift).
3. **Zero Secrets in Code:**
   - All cloud fallback routes must resolve through Doppler (`GEMINI_PRIMARY_API_KEY`, `OPENCODE_GO_KEY`).

---

## 4. Current Worktree Branches & Pull Requests

* **PR #88:** `feat/add-multimodal-model-recipes` (29 models / 53 variants / M5 Pro / M6 specs).
* **PR #93:** `docs/apple-silicon-system-specs` (CoreAI, AppIntents, MLX specs).
* **PR #94:** `feat/spacebar-menubar-hud` (SpaceBar modular components).
* **PR #95:** `spike/coreai-latent-vector-validation` (85µs ANE Latent-to-Vector benchmark).
* **PR #96:** `feat/streaming-transcription-recipes` (Moonshine & SenseVoice ASR).
