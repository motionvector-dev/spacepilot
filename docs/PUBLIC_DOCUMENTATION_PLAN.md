# SpacePilot Public Documentation Architecture & Editorial Specification

> **Status:** Approved  
> **Target Release:** v2.8.0  
> **Route:** `/docs` (`http://spacepilot.localhost:8088/docs`)  
> **Design Philosophy:** MotionVector Obsidian (Achromatic luminance, True-Black #000/#09090b, Zinc neutrals, crisp SVG architectural flowcharts, zero AI slop).

---

## 1. Editorial Charter & Tone
- **Audience:** Senior AI engineers, creative directors, pipeline TDs, and autonomous agent authors.
- **Tone:** Authoritative, high signal-to-noise, concrete numbers, byte-exact reproducible commands.
- **Zero-AI-Slop Invariant:** No generic filler ("In the rapidly evolving world of AI"). Every paragraph must state what a component does, its VRAM footprint, cost delta, or latency characteristics.

---

## 2. Information Architecture & Sections

### Section 1: Quickstart & Day-0 Setup
- **60-Second Setup:** Conda / venv initialization, Doppler secret ingestion (`LOCAL_WORKER_TOKEN`).
- **Hardware Autodetection:** Zero-dependency host probe (`sysctl` Apple Silicon, PyTorch MPS, NVIDIA NVML).
- **Your First Take:** Running a $0.00 local LTX draft take vs a SkyPilot $0.012 spot take.

### Section 2: Core Platform Invariants
- **Local-First / Spot Mesh Hybrid Architecture:** Hardware safety headroom formula ($V_{usable} = 0.80 \times V_{total} - 1.5\text{GB}$).
- **DocIR 2.0 Edit Protocol:** Reversible, byte-exact patch operations with zero state corruption.
- **Wholesale Compute Arbitrage:** Live 1s billing odometer vs 20x proprietary SaaS subscription markups.

### Section 3: Model Zoo & DiT Engine Matrix
- **LTX-Video 2.5:** 13B DiT, spatial multiples of 32, $(8k+1)$ frame pacing, STG guidance.
- **Wan2.1 (1.3B & 14B):** 3D Causal VAE temporal $4\times$ and spatial $8\times$ compression, $(4k+1)$ frames.
- **HunyuanVideo:** 13B dual-stream DiT cross-attention text/visual pipelines at 720p/1080p.
- **Kokoro-82M TTS:** 24kHz in-process speech synthesis with $-16\text{ LUFS}$ sidechain ducking.
- **SPAN-4K Super-Resolution:** Spatial-temporal upscaling master plate pipeline.

### Section 4: Agentic FastMCP Reference
- **Client Connections:** STDIO and SSE endpoints for Claude Desktop, Cursor, Antigravity, and custom agent harnesses.
- **Tool Catalog:** Complete schemas, parameter bounds, and JSON responses for all 12+ FastMCP tools.
- **Agent Workflow Recipes:** End-to-end screenplay deconstruction to 4-take batch rendering.

### Section 5: Interactive REST API Reference
- **Security & Token Gating:** `X-Pluto-Token` authentication for mutating compute routes.
- **Route Catalog:** Request/response schemas, error status codes, and code tabs (Python SDK, cURL, TypeScript).

### Section 6: SkyPilot Spot Mesh & Multi-Cloud Infrastructure
- **Declarative YAML:** `infra/skypilot.yaml` multi-cloud resource orchestration.
- **Spot Preemption Failover:** Zero-data-loss checkpoint recovery and automated cloud arbitrage.
