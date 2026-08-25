# SpacePilot 🚀

**Status**: Current
**Verified**: 2026-08-22 via `python -m pytest tests/ -q` (172 passed, 57.81s) and `gh pr list`
**Supersedes / Superseded by**: none

> **"SpacePilot pilots your generative cinema."**

**SpacePilot** is the high-performance generative cinema workstation and compute toolkit for macOS Apple Silicon and Linux/CUDA. A modular studio web UI (`/create`, `/cockpit`, `/studio`, `/oven.html`), native FastMCP tool server, and CLI on the host machine are backed by polymorphic DiT generative engines (LTX-Video 2.5, Wan2.1, HunyuanVideo) and in-process local execution drivers.

---

## Architecture & Modular Components

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     SpacePilot Modular Platform Topology                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  1. Compute Provider Modules (Pluggable Execution Runtimes)                 │
│     ├── Local Host Driver: Apple Metal MPS / CUDA / CPU ($0.00 / Zero Cloud)│
│     ├── Local Execution: Apple Metal MPS / CUDA / CPU                       │
│     └── Hardware Probe: Auto-detects VRAM headroom & recommends models      │
│                                                                             │
│  2. Generative Model Modules (Polymorphic BaseVideoEngine Adapters)         │
│     ├── LTX-Video 2.5: 13B DiT (Spatial % 32, 8k+1 frames)                  │
│     ├── Wan2.1 (1.3B & 14B): 3D Causal VAE (Spatial % 16, 4k+1 frames)      │
│     ├── HunyuanVideo: 13B dual-stream DiT cross-attention (720p/1080p)      │
│     ├── Speech & VO: In-process Kokoro-82M ONNX with -16 LUFS sidechaining  │
│     └── Narrative: In-process GGUF screenplay deconstruction & 3D vectors   │
│                                                                             │
│  3. Agentic Protocol & Tool Modules                                         │
│     ├── FastMCP Tool Server (spacepilot/pluto_mcp_server.py): 12+ tools for AI     │
│     ├── DocIR 2.0 Edit Protocol: Byte-exact, reversible patch operations   │
│     └── WebSocket PTY Bridge: Live interactive shell & worker streaming    │
│                                                                             │
│  4. UI Component Modules (Zero-Build Obsidian UI)                           │
│     ├── Create Studio (/create): Camera Compass, Dual Keyframe, VO Ducking │
│     ├── Cockpit (/cockpit): Live Host Telemetry, Model Hub                  │
│     ├── Oven (/oven.html): Real-time 5-Lane ADLC Swarm Kanban Board         │
│     └── Director (/studio): Multi-track NLE timeline & asset inspector      │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Setup & Secrets

```bash
# Environment setup (Conda or venv)
conda activate local-ml-py311   # Default recommended ML env at ~/miniconda3
pip install -r requirements.txt
```

Secrets are centrally scoped with **Doppler**, project `unfoundbox`, config `dev_personal` at `~/code`:
```bash
doppler run -- spacepilot studio
```

**`LOCAL_WORKER_TOKEN`** is required for gated compute operations. The GPU worker requires it, and all mutating POST endpoints enforce `X-SpacePilot-Token`.

---

## Running the Studio

```bash
doppler run -- spacepilot studio          # or: python spacepilot/web_api.py
```

Serves the Web UI and API on:
* **Primary URL**: **`http://spacepilot.localhost:8088`**
* **Local Loopback**: **`http://localhost:8088`** (or `http://127.0.0.1:8088`)

### Studio Pages:
* **Create Studio**: `http://spacepilot.localhost:8088/create`
* **Cockpit & Model Registry**: `http://spacepilot.localhost:8088/cockpit`
* **Oven Swarm Kanban**: `http://spacepilot.localhost:8088/oven.html`
* **Director NLE**: `http://spacepilot.localhost:8088/studio`

---

## API Routes & Security Gate

Every endpoint that spends compute or creates assets is gated by `X-SpacePilot-Token` (`require_token`). Read-only and telemetry routes stay open.

| Route | Method | Auth | Purpose |
| :--- | :--- | :--- | :--- |
| `/api/generate` | `POST` | Yes | Queue LTX-Video generation run (Spot GPU or local mock). |
| `/api/generate/multi-engine` | `POST` | Yes | Polymorphic generation on Wan2.1 (1.3B/14B), Hunyuan, or LTX-2.5. |
| `/api/audio/synthesize-local` | `POST` | Yes | In-process Kokoro TTS audio synthesis (-16 LUFS normalized). |
| `/api/audio/mix-ducked` | `POST` | Yes | Voiceover & background music dynamic sidechain ducking. |
| `/api/narrative/decompose-local` | `POST` | Yes | In-process GGUF screenplay deconstruction into 3D camera shots. |
| `/api/compute/models/download` | `POST` | Yes | Download model weights to `~/.cache/spacepilot/models/`. |
| `/api/gpu/launch` · `/terminate` | `POST` | Yes | Spot GPU infrastructure lifecycle management. |
| `/api/compute/local-profile` | `GET` | No | Hardware capability telemetry (backend, usable VRAM headroom). |
| `/api/compute/models/recommended` | `GET` | No | Curated model recommendations scored for host hardware. |
| `/api/engines` | `GET` | No | Complete catalogue of available video DiT engines. |
| `/healthz` | `GET` | No | Dependency-free process liveness check. |
| `/api/status` | `GET` | No | Live GPU worker and fleet status telemetry. |

---

## FastMCP Server Tools (`spacepilot/pluto_mcp_server.py`)

Native FastMCP tools exposed to Cursor, Claude Code, and Antigravity:

* `spacepilot_probe_hardware`: Probes host GPU VRAM and compute headroom.
* `spacepilot_recommend_models`: Returns task-matched model catalog for current device.
* `spacepilot_decompose_storyboard`: Deconstructs screenplay into 3D camera vector scene beats.

---

## Test Suite (100% SLA)

```bash
/Users/saurabh/miniconda3/envs/local-ml-py311/bin/python -m pytest tests/ -v
```

**172 passing tests**, 0 failed, in 57.81s (verified 2026-08-22). Covers:
- Polymorphic DiT engines (LTX, Wan 1.3B/14B, HunyuanVideo spatial/temporal constraints).
- In-process Kokoro TTS and GGUF narrative drivers.
- Device capability probing and safety headroom calculations.
- FastMCP tool wrappers.
- REST API security token enforcement on all mutating routes.
- Frontend JavaScript syntax validation and HTML escaping.

---

## Directory Layout

```
bin/pluto                       CLI launcher & command router
src/
├── web_api.py               SpacePilot Studio FastAPI server & web UI router
├── pluto_mcp_server.py         Native FastMCP tool server
├── device_probe.py             Zero-dependency cross-platform hardware profiler
├── model_recommender.py        Model catalog & dynamic fit scoring engine
├── local_workers.py            Local in-process worker memory manager (LRU)
├── engines/                    Polymorphic Video DiT Engine Subsystem
│   ├── base.py                 BaseVideoEngine ABC & EngineSpec
│   ├── ltx_engine.py           LTX-Video 2.5 adapter
│   ├── wan_engine.py           Wan2.1 (1.3B & 14B) adapter
│   ├── hunyuan_engine.py       HunyuanVideo 13B dual-stream adapter
│   └── registry.py             Engine lookup & fallback registry
├── drivers/                    In-Process Local Execution Drivers
│   ├── base.py                 InferenceDriver ABC & DriverSpec
│   ├── kokoro_driver.py        Kokoro TTS ONNX driver (-16 LUFS ducking)
│   └── gguf_driver.py          GGUF screenplay deconstruction driver
├── storyboard_decomposer.py    Screenplay-to-shot decomposition
├── ltx_worker.py               Remote PyTorch resident worker (EC2/Cloud)
└── pluto/api/routes/           Modular FastAPI backend, live on main: 14 route
                                 modules (assets, audio, billing, checkpoints,
                                 compute, engines, generate, gpu, health, lora,
                                 recipes, storyboard, views, __init__)
web/                         Zero-build Obsidian UI
├── index.html / app.js      Director NLE & Asset matrix
├── create.html / create.js     Create Studio (Camera Compass, Dual Keyframe)
├── cockpit.html / cockpit.js   Cockpit (Host Hardware HUD, Model Registry)
├── oven.html                   Live 5-Lane ADLC Swarm Kanban Board
└── app.css                  Obsidian design system
infra/                          GPU startup scripts, IAM
tests/                          Pytest integration test suite (172 tests)
docs/                           Architecture blueprints, plans, and research
```
