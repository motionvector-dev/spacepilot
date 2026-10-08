> Status checked 2026-10-08: design context, not a shipped capability claim.
> Live AWS launch is gated pending a dock budget and worker deployment.
> Default G-family Spot quota is 8 vCPU (account 842954813809, us-east-1).
> Download/load/unload are explicit primitives; the loader serves text on loopback.
> Video requires a separately deployed compatible HTTP backend and remains unflown here.

# Technical Specification: SpacePilot Native Node Inference & SGLang Runtime

## 1. Objective
Transform ad-hoc bash deployment scripts into native, modular SpacePilot product capabilities:
1. `spacepilot launch`: Launches AWS box with cloud-init UserData that installs `spacepilot` on boot.
2. `spacepilot run video`: Runs on the remote GPU instance directly using the native `sglang` runtime.
3. Two-phase model delivery: Immediate non-blocking FL2VA serve (~3-4 min) + background Ref2VA download.

## 2. Architecture & Modules

```
+-- spacepilot/
    +-- registry/runtimes/
    |   +-- sglang.yaml              [Schema 1 runtime definition for SGLang diffusion engine]
    +-- services/
    |   +-- sglang_runner.py         [Execution engine: starts SGLang server, manages two-stage weights, dispatches prompt]
    |   +-- aws_fleet_launcher.py    [Generates production UserData cloud-init script for new EC2 boxes]
    +-- cli.py                       [Binds `spacepilot run video --model ... --backend sglang` and updates launch]
    +-- tests/
        +-- test_sglang_runtime_registry.py
        +-- test_sglang_runner.py
        +-- test_aws_userdata_generation.py
        +-- test_cli_run_video_workflow.py
```

## 3. Specifications

### 3.1 SGLang Runtime Registry (`spacepilot/registry/runtimes/sglang.yaml`)
- Schema: 1
- ID: `sglang`
- Name: `SGLang Diffusion`
- Modalities: `[video, image]`
- Backends: `[cuda]`
- Install: `pip install --pre "sglang[diffusion]" hf_xet`
- Runs: `[minimax-h3]`

### 3.2 Two-Stage SGLang Runner (`spacepilot/services/sglang_runner.py`)
- `ensure_weights(variant, stage="primary")`:
  - Stage 1: Downloads base + active variant (`FL2VA/*`) with 16 workers, excluding `Ref2VA/*`.
  - Stage 2 (async): Detached thread/subprocess downloads `Ref2VA/*` in background while inference server runs.
- `start_sglang_server(model_path, variant, resident_layers=24, quant=None)`:
  - Boots `sglang serve` on port 30010.
  - Polls `http://localhost:30010/health` with timeout.
- `generate_video(prompt, first_frame=None, steps=20, seconds=5.0)`:
  - Dispatches generation request via ComfyUI or direct SGLang REST endpoint.

### 3.3 Node Bootstrap UserData (`spacepilot/services/aws_fleet_launcher.py`)
- `generate_node_userdata(token=None, auto_serve_model=None) -> str`:
  - Installs `uv` and `spacepilot`.
  - Configures `/data` mount and tuning (`blockdev --setra 4096`).
  - Writes token to `/data/.hf_token`.

### 3.4 CLI Integration (`spacepilot/cli.py`)
- `cmd_run` handles `--kind video` or `spacepilot run video`.
- Flags: `--model`, `--prompt`, `--image`, `--steps`, `--seconds`, `--backend` (default: auto from registry).

## 4. Subagent Delegation Plan (TDD)
1. **Subagent 1 (Runtime Registry)**: Add `sglang.yaml` and test schema loading via `load_runtimes()`.
2. **Subagent 2 (UserData Generator)**: Implement and unit-test `generate_node_userdata` in `aws_fleet_launcher.py`.
3. **Subagent 3 (SGLang Runner Service)**: Implement and test `sglang_runner.py` with mock downloads, server lifecycles, and healthchecks.
4. **Subagent 4 (CLI Video Run Command)**: Implement and test `spacepilot run video` in `spacepilot/cli.py` with mock runner.
