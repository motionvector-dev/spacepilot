# SpacePilot Local GPU Inference & Device Capability Recommender

> **Author**: MotionVector Engineering  
> **Status**: APPROVED ARCHITECTURAL BLUEPRINT & SPECIFICATION  
> **Target Scope**: Pluto / SpacePilot Hybrid Orchestrator, CLI, FastMCP Server, Studio Cockpit  
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

## 2. Zero-Dependency Hardware Capability Probe

To match Magnitude’s zero-friction user experience, SpacePilot will probe host hardware without requiring third-party model daemons or elevated permissions.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                   Zero-Dependency Device Profiler                           │
├─────────────────┬──────────────────────────────────┬────────────────────────┤
│ Operating Sys   │ Primary Detection Vector         │ Telemetry Harvested    │
├─────────────────┼──────────────────────────────────┼────────────────────────┤
│ macOS           │ • `sysctl hw.memsize`            │ • Apple Silicon Model  │
│ (Apple Silicon) │ • `sysctl machdep.cpu.brand_str` │   (M1/M2/M3/M4 Pro/Max)│
│                 │ • `ioreg -r -d 1 -k IOGPU`       │ • Unified Memory (GB)  │
│                 │ • `torch.backends.mps.is_avail`  │ • Metal compute units  │
├─────────────────┼──────────────────────────────────┼────────────────────────┤
│ Linux / Windows │ • `pynvml` / `/proc/driver/nv`   │ • GPU Name (RTX 4090)  │
│ (NVIDIA CUDA)   │ • `torch.cuda.get_device_prop`   │ • Total & Free VRAM    │
│                 │ • CUDA Compute Capability        │ • Tensor Core gen (FP8)│
├─────────────────┼──────────────────────────────────┼────────────────────────┤
│ CPU Fallback    │ • `psutil.virtual_memory()`      │ • System RAM headroom  │
│                 │ • CPU instruction set flags      │ • AVX-512 / ARM Neon   │
└─────────────────┴──────────────────────────────────┴────────────────────────┘
```

### Usable VRAM Safety Calculation:
$$\text{Usable VRAM} = (\text{Total Physical VRAM}) \times 0.80 - \text{Display Buffer (1.5GB)}$$
This preserves desktop UI responsiveness, window compositing, and browser performance while running local inference.

---

## 3. Multimodal Model Recommendation Matrix

Pluto evaluates probed hardware against the task taxonomy to recommend optimized weights:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                 Multimodal Model Recommendation Engine                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  [ Category 1: Voiceover & TTS ] (0.3 GB VRAM requirement)                  │
│  ├── Model: Kokoro-82M (ONNX / PyTorch MPS / CUDA)                          │
│  ├── Recommendation Rule: ALWAYS RECOMMENDED (Fits on 100% of devices)      │
│  └── Storage Footprint: ~320 MB                                             │
│                                                                             │
│  [ Category 2: Storyboard & Script Decomposer ] (2.5 GB – 6.0 GB VRAM)      │
│  ├── Low VRAM (8GB–16GB): Qwen 2.5 3B-Instruct (Q4_K_M GGUF · 2.1 GB)       │
│  ├── Mid VRAM (16GB–32GB): DeepSeek-R1-Distill-Qwen-7B (Q4_K_M · 4.8 GB)    │
│  ├── High VRAM (32GB+): Qwen 2.5 14B-Instruct (Q4_K_M · 9.2 GB)            │
│  └── Storage Footprint: 2.1 GB – 9.2 GB                                     │
│                                                                             │
│  [ Category 3: Video Diffusion Engine ] (12 GB – 32 GB VRAM)                │
│  ├── Low VRAM (<16GB): Cloud Spot Fallback Recommended (or 512p NF4)        │
│  ├── Mid VRAM (16GB–24GB): LTX-Video 2.5 (NF4 Quantized GGUF · 11.2 GB)     │
│  ├── High VRAM (32GB–64GB+): LTX-Video 2.5 (FP8 Cinema Draft · 22.4 GB)     │
│  └── Storage Footprint: 11.2 GB – 24 GB                                     │
│                                                                             │
│  [ Category 4: Super-Resolution Upscaling ] (0.8 GB VRAM)                   │
│  ├── Model: SPAN / Real-ESRGAN 4x (TorchScript / ONNX)                      │
│  ├── Recommendation Rule: Fits on all GPUs (Apple MPS / CUDA / CPU)        │
│  └── Storage Footprint: ~64 MB                                              │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. FastMCP Tools & CLI Interface Specifications

### 4.1 FastMCP Tool Specifications (`spacepilot/pluto_mcp_server.py`)

1. **`pluto_probe_hardware()`**:
   - Returns: `{ "os": "darwin", "device": "Apple M3 Max", "vram_total_gb": 64.0, "vram_usable_gb": 49.7, "backend": "metal_mps", "cuda_cores": null, "status": "optimal" }`
2. **`pluto_recommend_models()`**:
   - Returns list of task recommendations with fit scores, memory footprints, and local cache status.
3. **`pluto_download_model(model_id: str, background: bool = True)`**:
   - Manages non-blocking chunked downloads into `~/.cache/pluto/models/` with SHA-256 validation.
4. **`pluto_get_local_status()`**:
   - Returns loaded in-memory weights, current VRAM utilization, active workers, and dispatch metrics.

### 4.2 CLI Command Topology
```bash
# Probe and inspect local device compute
$ pluto hardware

# Inspect recommendations based on current available headroom
$ pluto models recommend

# Download recommended model suites
$ pluto models pull kokoro-82m
$ pluto models pull qwen-2.5-7b-gguf
$ pluto models pull ltx-2.5-nf4
```

---

## 5. Studio Cockpit Integration (`web/cockpit.html`)

1. **Hardware Telemetry HUD**: Real-time VRAM gauge, unified memory ceiling, GPU temperature, and active backend badge (`[ Local: Apple Metal (48GB Free) ]`).
2. **Model Registry Card**: Single-click "Download Recommended Suite" action with visual progress bar and local disk quota tracker.
3. **Studio Create Hybrid Selector**: UI switch between `[ Compute: Auto (Local-First) ]`, `[ Compute: Local Only ($0) ]`, and `[ Compute: SkyPilot Spot Only ]`.

---

## 6. Implementation Milestones

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Implementation Roadmap                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Phase 1: Hardware Telemetry & Capability Probe                             │
│  ├── Deliver spacepilot/device_probe.py & spacepilot/model_recommender.py                 │
│  ├── Expose GET /api/compute/profile & GET /api/compute/models/recommended  │
│  └── Register FastMCP tools: pluto_probe_hardware & pluto_recommend_models  │
│                                                                             │
│  Phase 2: Local Model Catalog & Background Downloader                       │
│  ├── Implement resumable downloader to ~/.cache/pluto/models/ with SHA256   │
│  ├── Add FastMCP tool: pluto_download_model & progress streamer             │
│  └── Cockpit UI Model Registry card with 1-click download actions           │
│                                                                             │
│  Phase 3: Studio Workflow Binding & Auto-Arbitrage Integration              │
│  ├── Connect local Kokoro TTS + local GGUF Decomposer to Studio routes      │
│  ├── Add [Compute: Auto (Local-First)] switch to Create Studio              │
│  └── 100% SLA Pytest suite verifying mock/live probe across platforms      │
│                                                                             │
│  Phase 4: Local LAN Peer Mesh (Exo-Inspired)                                │
│  ├── mDNS zero-config discovery of local network Pluto nodes                │
│  └── Distributed parallel 4-take rendering across LAN workstations          │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```
