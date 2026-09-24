# SpacePilot 🚀

[![PyPI](https://img.shields.io/badge/PyPI-spacepilot-2.9.0-blue)](https://pypi.org/project/spacepilot/)
[![Python](https://img.shields.io/badge/python-3.11%2B-informational)](https://pypi.org/project/spacepilot/)
[![License](https://img.shields.io/badge/license-Apache--2.0-green)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-1057%20passing-brightgreen)](.github/workflows/tests.yml)

> **You decide what to run. SpacePilot decides how and where.**

**SpacePilot** runs AI models on the machine in front of you and tells you
honestly what fits before you download it. One surface, every modality: text
and chat, embeddings, speech and transcription, and image — with a per-run
measurement record for each. Work the machine cannot hold goes to a rented box
with the same honesty checks on both sides. A CLI, a FastMCP tool server, and
a zero-build web UI are three windows onto one state.

Works today on Apple Silicon (Metal) and extends cleanly to CUDA and CPU.
The `/v1` surface is OpenAI-compatible, so anything that already speaks
`chat/completions` or `embeddings` can point at it.

---

## Why SpacePilot

Two things this project does not do:

1. **It does not guess.** Every model card is either *flown* — a real, dated
   measurement on a named machine — *on paper*, with the cited source — or
   *unflown*, which the registry names as a rule applied to a parameter
   count. Most registries pretend the third category does not exist. This
   one puts a number on it.
2. **It does not hide behind an API.** The `/v1` OpenAI-compatible surface
   means other tools can use SpacePilot without learning a new format. The
   heterogeneity it manages (local Lance/CUDA/CPU, rented spot, remote box)
   is the point.

The narrow waist that makes this useful: SpacePilot is a **decision layer
and orchestration layer** — not a model, not a serving framework. It reads
your fleet, ranks what fits, and routes your work honestly. It never invents
a number.

---

## What works today

| surface | surface | route |
| --- | --- | --- |
| **Text** | Apple Silicon | `spacepilot run text`, pinned MLX-LM route |
| **Text (OpenAI-compatible)** | Any | `POST /v1/chat/completions` |
| **Embeddings** | Apple Silicon | `POST /v1/embeddings`, 1024-dim |
| **Speech (TTS)** | Any | In-process Kokoro-82M ONNX |
| **Transcription** | Any | whisper.cpp, measured, working |
| **Image** | Apple Silicon | mflux, own venv, subprocess-only |
| **Video** | — | **Not yet** — routes exist, refuse with 501. Mock test-pattern real render is gone. |

The `/v1` surface is specified in [`docs/design/INFERENCE-SURFACE.md`](docs/design/INFERENCE-SURFACE.md).

### Honest boundary

Video here is real in name and honest in report: the engine routes exist as
specs, and the CLI tells you that. It is the longer-term aim, not a
description of this repo today.

---

## Install

```bash
uv tool install spacepilot            # from PyPI — the canonical install
```

Or with pip:

```bash
pip install spacepilot
```

Then:

```bash
spacepilot probe                      # what this machine can run
spacepilot models list                # which models run here, with the fit verdict
spacepilot doctor                     # check environment and dependencies
```

No account, no API key, no port opened. Full setup guide:
[`docs/LOCAL-SETUP.md`](docs/LOCAL-SETUP.md).

---

## Quickstart

Start the combined web UI + API on localhost:

```bash
spacepilot serve
```

Then open:

- **Cockpit** — `http://localhost:8088/cockpit` — live hardware telemetry,
  the model hub, and the save spot-billing path.
- **Create Studio** — `http://localhost:8088/create` — the create surface.
- **Developer docs** — `http://localhost:8088/docs`.

The Cockpit and other pages reflect whatever this machine actually is —
including the honest "we don't know" state when a probe returns no answer.

---

## Your first run

The CLI overlay of the first probe looks like the landing page's "fifteen
seconds, start to measured": it asks permission before reading anything, it
reports what it read, and it stays honest about gaps.

```bash
spacepilot probe
```

What this returns on a given machine is a *records* entry in
`registry/measurements/<your machine>/`, timestamped, source-attributed, and
reusable. Nothing in that flow phones home.

---

## Architecture at a glance

```
┌─────────────────────────────────────────────────────────────────────┐
│                    SpacePilot Platform Topology                     │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  1. Compute Provider Modules (pluggable execution runtimes)          │
│     ├── Local Host Driver — Apple Metal MPS / CUDA / CPU             │
│     ├── Hardware Probe — auto-detects usable VRAM, names the source  │
│     └── Rented spots, docks, and managed APIs (cost-accounted)       │
│                                                                     │
│  2. Generative Model Modules                                         │
│     ├── LTX-Video 2.5, Wan2.1, HunyuanVideo — spec only; routes      │
│     │   refuse 501 until real inference exists                       │
│     ├── Speech & VO — In-process Kokoro-82M ONNX                     │
│     └── Narrative — GGUF screenplay deconstruction                   │
│                                                                     │
│  3. Agentic Protocol & Tool Modules                                  │
│     ├── FastMCP tool server (`spacepilot/mcp_server.py`)             │
│     ├── DocIR 2.0 Edit Protocol — byte-exact reversible patches      │
│     └── WebSocket PTY bridge — live shell & worker streaming         │
│                                                                     │
│  4. UI Component Modules (zero-build, no bundler)                    │
│     ├── Create Studio `/create`                                      │
│     ├── Cockpit `/cockpit`                                           │
│     ├── Oven Swarm Kanban `/oven.html`                               │
│     └── Director NLE `/studio`                                       │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### Where the code lives

```
spacepilot/               The package — CLI, FastAPI app factory, drivers,
                          daemon, registry, measurement store
├── drivers/              Per-runtime execution drivers — MLX-LM (text),
│                         mflux (image), whisper.cpp (transcribe),
│                         Kokoro (speech), GGUF (narrative)
├── api/routes/           16 route modules; mutating routes go through
│                         require_token; read-only stays open
├── engines/              Video DiT engine specs — none run inference yet
├── web/                  Zero-build UI actually served by app.py (ships
│                         in the wheel — a uv tool install used to 500)
├── registry/             The model registry: variants, provenance,
│                         measurements, systems
│                         registry/models + systems + measurements
├── docs/design/          The architecture and inference-surface docs
tests/                    Pytest suite — do not trust a hardcoded count
                          in any doc, check CI for the current number
landing/                  The spacepilot.dev landing (deploys to Vercel)
native/SpaceBar/          macOS menu-bar app (Swift), separate cadence.
                          Moved to motionvector-dev/spacebar (carve-out
                          landed 2026-09-24); this directory will be
                          removed once the extraction settles.
```

---

## Configuration & secrets

Environment variables are the interface, or any secrets manager. Never
commit secrets; `.env.example` is the reference of what a deployment needs.

```bash
export LOCAL_WORKER_TOKEN="your-token"        # gated worker endpoints
```

---

## API & MCP

### HTTP API

Every endpoint that spends compute or creates assets is gated by
`X-SpacePilot-Token`. Read-only and telemetry routes stay open.

Surfaces worth knowing:

- `/v1/chat/completions` — OpenAI-compatible chat
- `/v1/embeddings` — embeddings
- `/api/compute/local-profile` — hardware capability telemetry (usable VRAM with its source)
- `/api/compute/models/recommended` — task-based fit verdicts for this machine
- `/healthz` — dependency-free liveness
- `/docs` — the developer portal

### MCP

`spacepilot-mcp` is a stdio MCP server for Cursor, Claude Code, and
Antigravity. The Studio process also hosts a loopback-only Streamable HTTP
transport at `/mcp/v1/`.

---

## Tests

```bash
python -m pytest tests/ -q
```

Do not trust a hardcoded test count in any doc — CI on the current `main`
is the number that counts. The suite covers the DiT engine specs (mock
renders only, honestly labelled), the working TTS/transcription/embedding
drivers, device probing, the `/v1` surface, and the FastMCP tools.

---

## Roadmap

Honest about what's in and what is not:

- **Works now**: hardware probing with named sources, model fit verdicts,
  compatibility across 88 variants, runtime installs that show what they
  will move before they move it, speech locally, OpenAI-compatible `/v1`.
- **Not yet**: video on your own silicon, scheduling across more than one
  ship at a time, a daemon that runs persistently outside the CLI.
- **Adjacent, separate package later**: SpaceBar (macOS menu bar app) ships
  its own release. A CLI install should not pull in a macOS tray app.

---

## Contributing

Issues and PRs welcome. Two rules from [`AGENTS.md`](AGENTS.md) that keep
this honest:

- **Execution over ceremony.** Skip bureaucratic process. Bias toward
  working code with receipts.
- **Strict tests before implementation** on production paths: reproduce red
  → fix green → refactor. Exploratory spikes are exempt until they land in
  production paths.

Run the tests locally before opening a PR. CI runs on a self-hosted lenovo
runner and is the gate.

---

## License

[Apache 2.0](LICENSE) — same license as the registry's Apache-family model
weights so everything under this roof stays redistributable.

---

## Links

- **PyPI**: [`spacepilot`](https://pypi.org/project/spacepilot/)
- **Source**: [motionvector-dev/spacepilot](https://github.com/motionvector-dev/spacepilot)
- **Landing**: [spacepilot.dev](https://spacepilot.dev)
- **Docs portal**: [spacepilot.dev/docs](https://spacepilot.dev/docs)
- **Design paper**: [spacepilot.dev/paper](https://spacepilot.dev/paper)
- **Releases**: [motionvector-dev/spacepilot/releases](https://github.com/motionvector-dev/spacepilot/releases)
