# SpacePilot Backend Engineering Session Report
**Date:** August 21–22, 2026  
**Session Focus:** SpacePilot Full-Stack Backend Refactor & Autonomous Roadmap Delivery  
**Target Repository:** `motionvector-dev/pluto`  
**Oven Kanban Status:** Fully Synchronized & Review-Ready  

**Status**: Context-only
**Verified**: 2026-08-22 (by `gh pr list` and a live test run — see correction block below)
**Supersedes / Superseded by**: none

---

## Correction — added 2026-08-22

This report is a record of what things looked like on August 21–22. Since then,
every PR it lists has moved. Here is the true state, as of 2026-08-22, verified
with `gh pr list`:

| PR # | This report called it | Actual state, 2026-08-22 |
| --- | --- | --- |
| #9  | Approved (Score 96) | **Merged** |
| #10 | Review Ready | **Merged** |
| #11 | Review Ready | **Merged** |
| #12 | Review Ready | **Merged** |
| #13 | Review Ready | **Merged** |
| #15 | Review Ready | **Merged** |

All six PRs are merged into main. Nothing in the Pull Request Fleet Summary or
the Kanban section below reflects that — read them as a snapshot of a past
moment, not current status.

The test count in Section 6 is also stale. This report says 55 (web_api)
plus five more suites passing. The full suite, run 2026-08-22, is **172
passed, 0 failed**, in 57.81s (`python -m pytest tests/ -q`). Treat any test
count in the body below as superseded by that number.

---

## 1. Executive Summary

During this session, we completed the **full architectural overhaul of the SpacePilot backend**, transitioning from a single monolithic 2,577-line file (`src/web_api.py`) into a production-grade, typed, modular FastAPI package layout (`src/pluto/`).

In addition to the zero-regression architectural refactor, we completed and published **5 major wave features and developer tools** across isolated Git worktrees, backed by unit test suites and registered FastMCP tools.

---

## 2. Pull Request Fleet Summary

```
┌───────┬───────────────────────────────┬────────────────────────────────────────────────────────┬─────────────────────┐
│ PR #  │ Branch                        │ Feature Scope                                          │ Review Status       │
├───────┼───────────────────────────────┼────────────────────────────────────────────────────────┼─────────────────────┤
│  #9   │ feat/backend-modular-refactor │ FastAPI Package Modularization (src/pluto/)            │ Approved (Score 96) │
│  #10  │ feat/lora-studio-engine       │ 1-Click LoRA Studio & PEFT Hot-Swap Engine             │ Review Ready        │
│  #11  │ feat/model-recipes-importer   │ Top Model Leaderboard Recipes & Quantized Importer     │ Review Ready        │
│  #12  │ feat/polar-x402-payments      │ Polar.sh MoR Webhooks & x402 Agent Micropayments       │ Review Ready        │
│  #13  │ feat/checkpoint-r2-sync       │ Spot Training Checkpoint Sync & R2/S3 Auto-Resume      │ Review Ready        │
│  #15  │ feat/cli-doctor-serve         │ CLI Doctor HUD, Serve Command & Phase 1C Archival      │ Review Ready        │
└───────┴───────────────────────────────┴────────────────────────────────────────────────────────┴─────────────────────┘
```

### Links to Pull Requests
- 🔗 **[PR #9: FastAPI Modular Package Refactor](https://github.com/motionvector-dev/pluto/pull/9)**
- 🔗 **[PR #10: 1-Click LoRA Studio & PEFT Hot-Swap Engine](https://github.com/motionvector-dev/pluto/pull/10)**
- 🔗 **[PR #11: Top Model Leaderboard Recipes & Quantized Importer](https://github.com/motionvector-dev/pluto/pull/11)**
- 🔗 **[PR #12: Polar.sh MoR Webhooks & x402 Micropayments](https://github.com/motionvector-dev/pluto/pull/12)**
- 🔗 **[PR #13: Spot Checkpoint Sync & Cloudflare R2 / S3 Auto-Resume](https://github.com/motionvector-dev/pluto/pull/13)**
- 🔗 **[PR #15: CLI Doctor HUD, Serve Command & Phase 1C Archival](https://github.com/motionvector-dev/pluto/pull/15)**

---

## 3. Architectural Deliverables

### A. The Modular `src/pluto/` Package

The monolith has been decomposed cleanly into domain boundaries:

```
src/pluto/
├── __init__.py                   # Package exports & v2.8.0 metadata
├── app.py                        # FastAPI create_app() factory with lifespan watchdog
├── core/
│   ├── config.py                 # Pydantic Settings consolidating all os.getenv
│   └── utils.py                  # Subprocess & path containment resolve_output
├── api/
│   ├── deps.py                   # require_token & idle activity watchdog hooks
│   └── routes/
│       ├── health.py             # /healthz, /api/token, /api/status, /api/live-reload
│       ├── compute.py            # Hardware probe, model recommendations & download
│       ├── recipes.py            # /api/compute/recipes (Top Model Leaderboard)
│       ├── lora.py               # /api/lora/* (PEFT LoRA Studio & Hot-Swap Registry)
│       ├── checkpoints.py        # /api/checkpoints/* (Snapshot & Preemption Auto-Resume)
│       ├── billing.py            # /api/billing/* (Polar.sh Webhook & x402 Micropayments)
│       ├── engines.py            # DiT engines (LTX-2.5, Wan2.1, Hunyuan)
│       ├── storyboard.py         # 3D camera vector & narrative screenplay decomposers
│       ├── gpu.py                # Spot lifecycle, Cockpit telemetry, WebSocket shell
│       ├── generate.py           # Video generation, extend, 4K upscale, vector plate master
│       ├── audio.py              # In-process Kokoro TTS, MLX music, sidechain ducking (-16 LUFS)
│       ├── assets.py             # Asset streaming, thumbnails, upload sanitization
│       └── views.py              # Director, Create, Cockpit, Oven, Docs HTML views
└── services/
    ├── audio.py                  # Kokoro ONNX, loudnorm_two_pass & peak limiting
    ├── generation.py             # Generation models, schemas & worker HTTP headers
    ├── gpu_lifecycle.py          # Double-checked locking status cache & spot manager
    ├── lora.py                   # PEFT LoRA training manager & progressive loss telemetry
    ├── model_catalog.py          # Hardware allocation recipes & background weight downloader
    ├── checkpoint_sync.py        # Multi-cloud snapshotting & preemption auto-restore
    ├── polar_billing.py          # Polar HMAC-SHA256 signature verifier & x402 engine
    ├── image_utils.py            # Multipart parser, image header dimensions & sanitization
    └── watchdog.py               # Auto-shutdown background idle loop
```

### B. Core Security & Concurrency Guarantees
1. **Constant-Time Token Validation**: `secrets.compare_digest` prevents timing attacks on all administrative routes.
2. **Double-Checked Status Lock**: `threading.Lock()` inside `gpu_lifecycle.py` prevents race conditions during spot polling.
3. **Path Traversal Confinement**: `resolve_output()` in `core/utils.py` confines file reads/writes strictly within `outputs/` and `assets/`.
4. **CORS & Domain Resolution**: Whitelists loopback, `pluto.localhost:8088`, `spacepilot.localhost:8088`, and Caddy HTTPS proxy origins.

---

## 4. Wave Feature Breakdown

### 1. 1-Click LoRA Studio & PEFT Hot-Swap Engine (PR #10)
- **Service**: `src/pluto/services/lora.py`
- **Capabilities**:
  - `LoRAAdapterSpec` schema (DiT target family, rank, alpha, learning rate, steps, trigger tokens).
  - Background async fine-tuning runner with progressive loss curve streaming.
  - Runtime adapter dynamic hot-swap registry.
- **FastMCP Tools**: `pluto_list_lora_adapters`, `pluto_train_lora`.

### 2. Top Model Leaderboard Recipes & Quantized Importer (PR #11)
- **Service**: `src/pluto/services/model_catalog.py`
- **Capabilities**:
  - Pre-calibrated hardware allocation profiles for Wan2.1 (1.3B/14B fp8), HunyuanVideo (GGUF q4), DeepSeek-R1 Distill (8B GGUF), Qwen2.5-VL (7B int4), and LTX-2.5 (fp8).
  - Dynamic hardware matching against Apple Silicon Metal and CUDA VRAM.
  - Background chunked weight downloader with `/progress` streaming.
- **FastMCP Tools**: `pluto_list_model_recipes`, `pluto_download_model_recipe`.

### 3. Polar.sh Webhook Reconciliation & x402 Micropayments (PR #12)
- **Service**: `src/pluto/services/polar_billing.py`
- **Capabilities**:
  - HMAC-SHA256 signature verification for Polar.sh webhook events (`checkout.created`, `subscription.active`, `order.paid`).
  - Credit usage ledger with per-engine generation rate cards (e.g., LTX-2.5 @ $0.005/sec, Hunyuan @ $0.015/sec).
  - Cryptographic x402 payment validation for autonomous AI agents paying in USDC.
- **FastMCP Tools**: `pluto_get_billing_usage`, `pluto_verify_agent_payment`.

### 4. Spot Training Checkpoint Sync & R2/S3 Auto-Resume (PR #13)
- **Service**: `src/pluto/services/checkpoint_sync.py`
- **Capabilities**:
  - Multi-cloud storage adapters: Cloudflare R2, AWS S3, and Local fallback.
  - Atomic checkpoint archiving with SHA-256 integrity verification.
  - Spot preemption recovery engine with auto-restore on instance respawn.
  - Configurable retention policy (`prune_snapshots(keep_best=3, keep_latest=2)`).
- **FastMCP Tools**: `pluto_create_checkpoint`, `pluto_list_checkpoints`, `pluto_restore_checkpoint`.

### 5. CLI Doctor HUD, Serve Command & Phase 1C Archival (PR #15)
- **CLI**: `src/cli.py` (`spacepilot` / `pluto`)
- **Capabilities**:
  - `spacepilot doctor`: Zero-dependency diagnostic HUD verifying Apple Silicon Metal / CUDA VRAM safety margins, system RAM, FFmpeg installation and version, Kokoro ONNX weights cache, AWS CLI profile credentials, and local `.studio_token`.
  - `spacepilot serve`: Direct Uvicorn runner for the FastAPI app factory supporting `--host`, `--port`, and `--reload`.
  - `spacepilot lora` & `recipes`: CLI subcommands for managing weights and adapters.
  - Phase 1C Archival: Moved deprecated legacy prototypes (`server.py`, `produce_welch_master.py`) into `archive/`.

---

## 5. Kanban Board (`web/oven.html`)

The live Oven Kanban board in `web/oven.html` has been updated with all newly delivered PR cards:
- **Review Gate**:
  1. `SpacePilot CLI Doctor, Serve & Archival` (PR #15)
  2. `Polar.sh MoR & x402 Micropayments Engine` (PR #12)
  3. `Spot Checkpoint Sync & R2/S3 Auto-Resume` (PR #13)
  4. `Model Recipes & Quantized Weights Importer` (PR #11)
  5. `1-Click LoRA Studio & PEFT Hot-Swap Engine` (PR #10)
  6. `Zero-Leniency Audit SLA` (Opus Review Passed 100/100)
- **Shipped**:
  - `FastAPI Modular Package Layout (src/pluto/)` (PR #9)

---

## 6. Verification and Test Results

All 6 test suites pass with zero regressions:
- `tests/test_web_api.py` $\rightarrow$ 55 passed (100% backward compatibility)
- `tests/test_lora.py` $\rightarrow$ Passed
- `tests/test_model_recipes.py` $\rightarrow$ Passed
- `tests/test_polar_billing.py` $\rightarrow$ Passed
- `tests/test_checkpoint_sync.py` $\rightarrow$ Passed
- `tests/test_cli_doctor.py` $\rightarrow$ Passed
