# SpacePilot 🚀

**Status**: Current
**Verified**: 2026-09-02 via the `tests` CI run on main (771 passed, 4 skipped,
run `33631068854`) and reading the tree directly.
**Supersedes / Superseded by**: none

> **"You decide what to run. SpacePilot decides how and where."**

**SpacePilot** runs AI models on the machine in front of you and says honestly
what fits before you download it. One surface, every modality: text and chat,
embeddings, speech and transcription, image, and video. Text and embeddings
are the newest routes — a pinned MLX route on Apple Silicon, an
OpenAI-compatible `/v1` surface — added 2026-09-02 because AgentWorth and
SpaceBar need them; every route gets a fit verdict from the model registry and
a measurement written for every run. Work the machine cannot hold goes to a
rented box. A CLI, a FastMCP tool server and a zero-build web UI (`/create`,
`/cockpit`, `/studio`, `/oven.html`) are three windows onto one state.

---

## First run

The canonical install, upgrade, runtime, Qwen text, and MCP instructions live
in [`docs/LOCAL-SETUP.md`](docs/LOCAL-SETUP.md). Keep one pipx control-plane
installation; inference runtimes use separately configured interpreters.

```bash
pipx install --force .                            # install or replace one CLI
spacepilot probe                                  # what this machine can run
spacepilot models                                 # which models run here, with the fit verdict
spacepilot run text --prompt "explain unified memory" --yes
```

What works today:

- **Text** on Apple Silicon, via a pinned MLX-LM route (`spacepilot run text`, and `POST /v1/chat/completions`).
- **Embeddings** on the same MLX route, 1024-dim, `POST /v1/embeddings` — in this PR.
- **Speech and transcription** via the API (`spacepilot serve`).
- **Image** on Apple Silicon, via mflux in its own conda env (`spacepilot runtimes check mflux` shows the route).

The `/v1` surface, the shared fit verdict and the per-call measurement record
are specified in [`docs/design/INFERENCE-SURFACE.md`](docs/design/INFERENCE-SURFACE.md).

### Video

What does not: **video**. The engines and routes exist, but every render is a
mock — an ffmpeg test pattern, not a real model run.

Video is a dock workload: it counts as real when it runs on a rented GPU end to
end. The generative cinema workstation is the longer-term aim, not a
description of what this repo does today.

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
│     ├── LTX-Video 2.5: spec only — no inference runs, route refuses 501    │
│     ├── Wan2.1 (1.3B & 14B): spec only — no inference runs, route refuses  │
│     ├── HunyuanVideo: spec only — no inference runs, route refuses         │
│     ├── Speech & VO: In-process Kokoro-82M ONNX with -16 LUFS sidechaining  │
│     └── Narrative: In-process GGUF screenplay deconstruction & 3D vectors   │
│                                                                             │
│  3. Agentic Protocol & Tool Modules                                         │
│     ├── FastMCP Tool Server (spacepilot/mcp_server.py): 17 tools for AI     │
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
* **Cockpit & Model Registry (legacy, vanilla JS)**: `http://spacepilot.localhost:8088/cockpit`
  — this is what `spacepilot/app.py` actually mounts and serves today.
* **Oven Swarm Kanban**: `http://spacepilot.localhost:8088/oven.html`
* **Director NLE**: `http://spacepilot.localhost:8088/studio`
* **Human documentation**: `http://spacepilot.localhost:8088/docs`
* **MCP Streamable HTTP v1**: `http://spacepilot.localhost:8088/mcp/v1/`
* **Cockpit v1 (React, `ui/`)**: not yet wired into `spacepilot/app.py`'s
  static mount. Run separately as a Vite dev server —
  `http://127.0.0.1:5173/cockpit` under `mvec-local` (`docs/LOCAL-TEST.md`).
  Whether it replaces the legacy cockpit above, and when, is still an open
  product call.

---

## API Routes & Security Gate

Every endpoint that spends compute or creates assets is gated by `X-SpacePilot-Token` (`require_token`). Read-only and telemetry routes stay open.

| Route | Method | Auth | Purpose |
| :--- | :--- | :--- | :--- |
| `/api/generate` | `POST` | Yes | Video generation. No local execution path exists; refuses with a failed job status unless a remote GPU worker is running. |
| `/api/generate/multi-engine` | `POST` | Yes | Video generation across the three DiT engines. Refuses with 501 — none of them run inference; the mock test-pattern render this route used to serve was removed. |
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

## FastMCP Server Tools (`spacepilot/mcp_server.py`)

Native FastMCP tools exposed to Cursor, Claude Code, and Antigravity:

* `spacepilot_probe_hardware`: Probes host GPU VRAM and compute headroom.
* `spacepilot_recommend_models`: Returns task-matched model catalog for current device.
* `spacepilot_decompose_storyboard`: Deconstructs screenplay into 3D camera vector scene beats.

The Studio process hosts the canonical loopback-only Streamable HTTP transport
at `/mcp/v1/`. The `spacepilot-mcp` command remains the stdio fallback for
clients that cannot use HTTP.

---

## Test Suite

Local pytest needs the project interpreter (see `AGENTS.md`, Interpreter) —
`python3` on the primary dev machine resolves to base conda, which lacks
fastapi. CI on the self-hosted lenovo runner is the gate; the run on the
commit this README was last checked against passed
**771 tests, 4 skipped** (`gh run view <run-id>` on main for the current
number — do not trust a hardcoded count here, it goes stale fast):

```bash
<project-python> -m pytest tests/ -v
```

Covers:
- Polymorphic DiT engine adapters (LTX, Wan 1.3B/14B, HunyuanVideo). Mock renders only —
  every BaseVideoEngine path used to write an ffmpeg test pattern; the route that served
  it now refuses with 501 instead, and no real video generation runs here yet.
- In-process Kokoro TTS and GGUF narrative drivers.
- Device capability probing and safety headroom calculations.
- FastMCP tool wrappers.
- REST API security token enforcement on all mutating routes.
- Frontend JavaScript syntax validation and HTML escaping.

---

## Directory Layout

```
spacepilot/                   The package (flattened from spacepilot/pluto/, #101)
├── cli.py                    CLI command router
├── app.py                    FastAPI app factory — mounts web/ as the served frontend
├── web_api.py                Studio entry point (python -m spacepilot.web_api)
├── mcp_server.py              Native FastMCP tool server, 17 tools
├── device_probe.py           Cross-platform hardware profiler
├── model_recommender.py      Model catalog & dynamic fit scoring
├── model_registry.py         Registry loader — variants, caveats, provenance
├── measurements.py           Measurement corpus (LOG) reader/writer
├── substrate.py               DirectLocal / DaemonClient wire-shaped dispatch
├── local_workers.py          Local in-process worker memory manager (LRU)
├── engines/                  Video DiT engine specs — none run inference yet
│   ├── base.py                BaseVideoEngine ABC & EngineSpec
│   ├── ltx_engine.py           LTX-Video 2.5 (spec only)
│   ├── wan_engine.py           Wan2.1 1.3B/14B (spec only)
│   ├── hunyuan_engine.py       HunyuanVideo (spec only)
│   └── registry.py             Engine lookup & fallback registry
├── drivers/                   In-process local execution drivers
│   ├── mflux_driver.py         Image — mflux, own conda env, subprocess-only
│   ├── mlx_lm_driver.py        Text — MLX-LM, the working `run text` route
│   ├── whisper_cpp_driver.py   Transcribe — measured, working
│   ├── kokoro_driver.py        Speech (TTS) — ONNX, working
│   ├── mlx_embed_driver.py     Embeddings — MLX, `/v1/embeddings`
│   └── gguf_driver.py          GGUF screenplay deconstruction
├── daemon/                    Fleet daemon — UDS + Tailscale peers, Ed25519,
│                               signed LOG gossip (identity.py, fleet.py, log.py)
├── storyboard_decomposer.py   Screenplay-to-shot decomposition
├── ltx_worker.py              Remote PyTorch resident worker (EC2/Cloud)
└── api/routes/                 16 route modules: assets, audio, billing,
                                checkpoints, compute, engines, generate, gpu,
                                health, inference, lora, measurements, recipes,
                                runtimes, storyboard, views
ui/                           React 19 cockpit v1 / SpaceBar-web (landed #106/#107).
                               Not wired into spacepilot/app.py's static mount —
                               run separately via Vite, see docs/LOCAL-TEST.md.
web/                          Zero-build UI actually served by spacepilot/app.py
├── index.html / app.js       Director NLE & Asset matrix
├── create.html / create.js    Create Studio
├── cockpit.html / cockpit.js  Cockpit (legacy, vanilla JS — currently what's live)
├── oven.html                  Kanban board
└── app.css                   Design system
native/SpaceBar/              macOS menu-bar app (Swift), see docs/LOCAL-TEST.md
infra/                         GPU startup scripts, IAM
tests/                         Pytest suite — 771 passed, 4 skipped on main as of
                               CI run 33631068854 (2026-09-02); re-check before citing
docs/                          Architecture blueprints, plans, and research
```
