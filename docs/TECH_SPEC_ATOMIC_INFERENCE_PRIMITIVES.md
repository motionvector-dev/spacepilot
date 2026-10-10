# Tech Spec: Atomic Inference Primitives (`download`, `load`, `unload`) & Workflow Integration

**Date**: 2026-10-07  
**Branch**: `feat/h3-aws-launch`  
**Status**: APPROVED FOR TDD IMPLEMENTATION  

---

## 1. Architectural Philosophy: Plumbing vs. Porcelain

SpacePilot adheres to strict separation between composable plumbing commands and high-level workflow commands:

+-- PORCELAIN (High-level ergonomics, opinionated automation)
|   +-- `spacepilot launch`  : Auto-provisions GPU box, seeds UserData, runs download + warm load.
|   +-- `spacepilot run`     : Submits inference request to warm resident backend.
|
+-- PLUMBING (Low-level atomic primitives, composable, zero-magic)
    +-- `spacepilot download`: Pulls model weights to local storage from HF/ModelScope/S3 with staging/filters.
    +-- `spacepilot load`    : Mounts local weights into backend memory/VRAM (SGLang, vLLM, ComfyUI).
    +-- `spacepilot unload`  : Gracefully terminates resident runtime and frees VRAM.

---

## 2. Low-Level Primitives Specification

### 2.1 `spacepilot download`
Pulls weights for a given model or variant to disk with support for staged multi-phase downloads (e.g. stage1 FL2VA vs full repo).

```bash
spacepilot download --model <model-or-variant> [--dest <path>] [--stage <stage>] [--concurrency <int>]
```

- **Arguments**:
  - `--model`: Model ID or variant ID (e.g. `minimax-h3`, `minimax-h3-fl2va-fp8`, `ltx-2.5`).
  - `--dest`: Destination folder (default: `~/.cache/spacepilot/models/<model_id>/<variant_id>`).
  - `--stage`: Download phase (`all`, `stage1`, `stage2`). Default: `all`.
    - `stage1`: For models like MiniMax H3, downloads only `FL2VA/*` necessary for base generation (~3 min).
    - `stage2`: Downloads auxiliary weights like `Ref2VA/*`.
  - `--concurrency`: Number of parallel download threads (default: 16).
- **Behavior**:
  - Uses `hf_transfer` / `huggingface_hub` when available, falling back to standard streaming.
  - Idempotent: Skips existing valid files using size / SHA checks.
  - Returns JSON summary or prints progress.

### 2.2 `spacepilot load`
Loads model weights from local disk into an active inference runtime daemon.

```bash
spacepilot load --model <model-or-variant> [--weights-dir <path>] [--backend <sglang|vllm|comfyui>] [--port <int>] [--tp <int>] [--daemon]
```

- **Arguments**:
  - `--model`: Model or variant ID to determine default runtime flags, entrypoint, and config.
  - `--weights-dir`: Path to weights on disk (default: resolved from model cache).
  - `--backend`: Runtime engine (`sglang`, `vllm`, `comfyui`, `transformers`). If unspecified, reads default from model registry.
  - `--port`: Local HTTP/gRPC port to serve (default: 30010 for SGLang, 8000 for vLLM, 8188 for ComfyUI).
  - `--tp`: Tensor parallelism degree (default: 1, or auto-selected from GPU count).
  - `--daemon`: Run in background detached mode, writing PID to `~/.spacepilot/run/<model>.pid`.
- **Behavior**:
  - Verifies local weights presence before starting.
  - Spawns backend process and monitors readiness healthcheck endpoint (`/health` or `/v1/models`).
  - Records resident model state in local state registry (`~/.spacepilot/resident.json`).

### 2.3 `spacepilot unload`
Evicts active model from VRAM and shuts down the runtime process.

```bash
spacepilot unload [--model <model-or-variant>] [--port <int>] [--all]
```

- **Behavior**:
  - Sends graceful SIGTERM to backend daemon PID or `/v1/shutdown` endpoint.
  - Verifies GPU memory reclamation via `nvidia-smi` query if available.
  - Clears entry in `~/.spacepilot/resident.json`.

---

## 3. Modular Code Architecture & File Layout

All primitives live in clean, single-purpose service modules in `spacepilot/services/`:

```
spacepilot/
+-- services/
|   +-- model_downloader.py       # Download engine (HF hub, staged filters, aria/hf_transfer)
|   +-- runtime_manager.py        # Process supervisor (load, unload, healthchecks, PID tracking)
|   +-- gpu_recommender.py        # Hardware recommendation logic
|   +-- aws_fleet_launcher.py     # EC2 spot provisioning & UserData generation
|   +-- user_preferences.py       # Local config persistence
+-- cli.py                        # Exposes `download`, `load`, `unload`, `launch`, `run`
+-- registry/models/              # Declarative YAML specs
tests/
+-- test_model_downloader.py      # Unit tests with mocked HF hub & stage filters
+-- test_runtime_manager.py       # Unit tests with mocked subprocess & healthchecks
+-- test_cli_plumbing.py          # CLI integration tests for download/load/unload
```

---

## 4. Subagent Work Packages (TDD Plan)

### Package 1: `Downloader Engine` (`spacepilot/services/model_downloader.py`)
- **Responsibility**: Implement `download_weights(variant, dest_dir, stage="all", concurrency=16)`.
- **Test File**: `tests/test_model_downloader.py`.
- **Requirements**:
  - Handle staging patterns (e.g. `patterns_include=["FL2VA/**"]` for stage 1).
  - Test mock download calls, directory creation, and return paths.

### Package 2: `Runtime Manager` (`spacepilot/services/runtime_manager.py`)
- **Responsibility**: Implement `load_model(...)`, `unload_model(...)`, `get_resident_models()`.
- **Test File**: `tests/test_runtime_manager.py`.
- **Requirements**:
  - Command line construction for `sglang.launch_server`, `vllm`, and `comfyui`.
  - Process lifecycle management (PID tracking, poll health endpoint, kill/terminate).
  - Test process startup, timeout handling, and cleanup.

### Package 3: `CLI Plumbing Wiring` (`spacepilot/cli.py`)
- **Responsibility**: Wire `cmd_download`, `cmd_load`, and `cmd_unload` subcommands in `spacepilot/cli.py`.
- **Test File**: `tests/test_cli_plumbing.py`.
- **Requirements**:
  - Test CLI argument parsing and dispatching to services with mocked dependencies.
