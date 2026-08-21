# SpacePilot Local GPU Inference Architecture & Engineering Plan

> **Author**: MotionVector Engineering  
> **Status**: APPROVED ARCHITECTURAL BLUEPRINT  
> **Target Scope**: Pluto / SpacePilot Hybrid Orchestrator  
> **Reference Systems**: Magnitude (`magnitude.dev`), Exo (`exo-explore/exo`), Apple MLX, vLLM, llama.cpp

---

## 1. Executive Vision & Problem Statement

### 1.1 The Cloud Spot Bottleneck
While SpacePilot v2.3.0 successfully orchestrates remote spot GPU instances across AWS, Lambda, RunPod, and GCP at \$0.20–\$0.24/hr with preemption failover, **every single user request** (even prompt enhancement, script decomposition, TTS synthesis, or draft previews) currently incurs:
1. **Network roundtrip latency** (200ms – 1,200ms API cold transfers).
2. **Cloud marginal cost** (\$0.01 – \$0.04 per take).
3. **Cloud provider dependency** (availability quotas, spot termination).

### 1.2 The Local GPU Opportunity
Modern developer & creator workstations possess formidable compute:
- **Apple Silicon (M1/M2/M3/M4 Max/Ultra)**: 32 GB – 128 GB of unified zero-copy memory running at 400–800 GB/s bandwidth.
- **NVIDIA Desktop GPUs (RTX 3080/3090/4080/4090/5090)**: 16 GB – 32 GB high-speed GDDR6X/GDDR7 VRAM with FP8/Tensor Cores.
- **Modern AVX-512 / ARM Neon CPUs**: 32 GB – 64 GB system RAM capable of lightweight quantized NLP.

By enabling **Local GPU Inference** inside SpacePilot, MotionVector unlocks **\$0.00 marginal cost**, **zero data transmission latency**, and **fully offline/air-gapped studio workflows**.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                 SpacePilot Hybrid Compute Topology                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│                    ┌──────────────────────────────┐                         │
│                    │   Studio / Web / MCP Client  │                         │
│                    └──────────────┬───────────────┘                         │
│                                   │                                         │
│                                   ▼                                         │
│                    ┌──────────────────────────────┐                         │
│                    │ SpacePilot Arbitrage Router  │                         │
│                    │  • Task VRAM Estimation      │                         │
│                    │  • Hardware Telemetry Probe  │                         │
│                    │  • Cost vs Latency Sorter    │                         │
│                    └──────┬────────────────┬──────┘                         │
│                           │                │                                │
│       [Local Capable]     │                │   [Heavy Diffusion / 4-Take]   │
│       Cost: $0.00         ▼                ▼   Cost: ~$0.04/take            │
│  ┌──────────────────────────────┐    ┌──────────────────────────────────┐   │
│  │   SpacePilot Local Runner    │    │    SkyPilot Spot Mesh            │   │
│  │  • Kokoro TTS (PyTorch/MPS)  │    │  • RunPod L40S ($0.22/hr)        │   │
│  │  • Qwen 2.5 / DeepSeek GGUF  │    │  • Lambda A10G ($0.24/hr)        │   │
│  │  • LTX-2.5 Draft (NF4/GGUF)  │    │  • AWS g5.2xlarge ($0.34/hr)     │   │
│  │  • SPAN 4K Super-Resolution  │    │  • 4-Take Batch Cinema Render    │   │
│  └──────────────────────────────┘    └──────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Competitive & Architectural Audit

### 2.1 Magnitude (`magnitude.dev`)
* **What it is**: An open-source, AI-native terminal agent with an embedded `llama.cpp` C++ inference engine.
* **Key Architecture**:
  1. *Hardware Profiling*: Auto-detects OS architecture, available RAM, GPU type (Apple Metal MPS vs NVIDIA CUDA vs CPU).
  2. *Embedded Runtime*: Bundles precompiled C++ binaries directly inside the package without requiring the user to run Ollama, vLLM, or LM Studio.
  3. *Dynamic Model Recommender*: Recommends specific GGUF quantizations (Q4_K_M vs Q8_0) based on actual free system memory.
* **Takeaway for SpacePilot**: Adopt zero-friction hardware discovery and embedded model loading. Never require the creator to configure external ports or daemons.

### 2.2 Exo (`exo-explore/exo`)
* **What it is**: Distributed P2P local AI cluster engine running across heterogenous devices (e.g. MacBook Pro + Mac Mini + Linux PC).
* **Key Architecture**: Decentralized ring-topology tensor parallelism over local Wi-Fi/LAN.
* **Takeaway for SpacePilot**: Future Phase 4 LAN Discovery — aggregate multiple home/office studio machines into a pooled render farm.

### 2.3 Apple MLX (`ml-explore/mlx`)
* **What it is**: Apple Silicon framework designed for unified zero-copy memory arrays on macOS.
* **Key Architecture**: Outperforms PyTorch MPS for quantized LLM generation and Audio processing on M-series chips (40–60+ tok/s).
* **Takeaway for SpacePilot**: Use MLX / ONNX runtime for native macOS audio synthesis (Kokoro TTS) and script parsing.

---

## 3. The 3-Tier Compute Matrix

| Compute Tier | Task Examples | Target Hardware | Engine / Runtime | Cost & Latency |
| :--- | :--- | :--- | :--- | :--- |
| **Tier 1: Lightweight Edge** | • Kokoro-82M Voiceover<br>• Prompt Expansion<br>• EBU R128 Sidechain Mux | Any Mac (M1+)<br>GTX 1660+ / CPU<br>8 GB Sys RAM | PyTorch / ONNX / FFmpeg<br>Qwen2.5-3B GGUF | **\$0.00 / 0.3s** (Instant) |
| **Tier 2: Mid-Range Diffusion** | • Storyboard Decomposer<br>• 1-Take LTX-2.5 Draft (512p)<br>• SPAN 4K Video Upscale | M2/M3/M4 Pro/Max (16GB+)<br>RTX 3080/4070 (12GB+)<br>16–32 GB VRAM | Diffusers MPS / CUDA<br>NF4 / GGUF Quantized<br>DeepSeek-R1-7B | **\$0.00 / 4–8s** (Local Free) |
| **Tier 3: Extreme Batch Cluster** | • 4-Take Director Grid<br>• 4K 60fps Pro Cinema Render<br>• Full FLF2V Morphing | Cloud High-Density Node<br>RunPod / Lambda A100/H100<br>80 GB VRAM | SkyPilot Spot Mesh<br>TensorRT-LLM / vLLM<br>Multi-Worker Docker | **~\$0.04 / 12s** (Spot Mesh) |

---

## 4. Architectural Specification

```
┌─────────────────────────────────────────────────────────────────────────────┐
│               SpacePilot Local Hardware Profiler Engine                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  1. Hardware Probe Layer (platform_probe.py)                                │
│     ├── macOS: sysctl hw.memsize, ioreg (Apple Silicon M-Series Model)      │
│     ├── Linux: nvidia-smi / pynvml (CUDA Core count, VRAM, Driver)          │
│     └── Memory: psutil (Free RAM, Swap headroom, Thermal throttling state)  │
│                                                                             │
│  2. Local Inference Worker (local_worker.py)                                │
│     ├── Kokoro TTS Worker: Fast in-memory torch/onnx voice synthesis         │
│     ├── GGUF LLM Worker: llama-cpp-python / MLX-LM context runner           │
│     └── Video Worker: Local LTX-2.5 diffusion plate renderer                │
│                                                                             │
│  3. SpacePilot Arbitrage Policy (arbitrage.py)                              │
│     IF Task == "audio_voiceover" -> ROUTE_LOCAL                             │
│     IF Task == "enhance_prompt"   -> ROUTE_LOCAL                             │
│     IF Task == "storyboard" AND Local_VRAM >= 8GB -> ROUTE_LOCAL            │
│     IF Task == "video_4take" OR Local_VRAM < 16GB -> ROUTE_SKYPILOT_SPOT   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 5. Engineering Roadmap & Milestones

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Implementation Roadmap                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Phase 1: Hardware Telemetry & Capability Probe                             │
│  ├── Implement GET /api/compute/local-profile endpoint                     │
│  ├── Expose Metal MPS, CUDA VRAM, and RAM telemetry in Cockpit UI           │
│  └── Deliver zero-dependency platform detection module                      │
│                                                                             │
│  Phase 2: Local Audio & NLP In-Process Workers                              │
│  ├── Mount in-process Kokoro TTS audio generator ($0 cloud spend)           │
│  ├── Add local llama.cpp / MLX fallback for Storyboard Decomposer           │
│  └── Unit tests verifying offline execution without network connectivity    │
│                                                                             │
│  Phase 3: Hybrid Arbitrage Router in Studio Create                          │
│  ├── Add [Compute: Auto (Local-First) ▾] selector in create.html            │
│  ├── Real-time cost estimator updating PatchCard ($0.00 Local vs Spot)      │
│  └── Automatic failover from Local VRAM OOM to SkyPilot Spot                │
│                                                                             │
│  Phase 4: Local LAN Peer Mesh (Exo-Inspired)                                │
│  ├── mDNS zero-config discovery of local network Pluto nodes                │
│  └── Distributed parallel 4-take rendering across LAN workstations          │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 6. Verification & SLA Standards

1. **Security & Isolation**: Local model files are stored strictly under `~/.cache/pluto/models/` and verified with SHA-256 hashes.
2. **Graceful Fallback**: Any local VRAM allocation error (CUDA OOM / Metal OOM) immediately logs warning and auto-delegates to SkyPilot spot compute without failing the user's render job.
3. **100% Test SLA**: All hardware probe and router modules covered by pytest integration tests in `tests/test_local_inference.py`.
