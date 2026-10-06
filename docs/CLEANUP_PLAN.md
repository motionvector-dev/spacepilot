# SpacePilot CLI & MCP Cleanup & Restructuring Action Plan

**Date**: 2026-10-07  
**Branch**: `feat/h3-aws-launch` in `/Users/saurabh/code/crew/spacepilot`  
**Status**: READY FOR SURGICAL EXECUTION  

---

## 1. Audit Findings & Line Receipts

### A. CLI Bloat (`spacepilot/cli.py` - 2,512 lines, 22 top-level verbs)
- **Zombie/Refused Verbs**:
  - `generate`: Lines 573-575 call `_refuse_legacy_aws("generate")`.
  - `sync`: Lines 577-579 call `_refuse_legacy_aws("sync")`.
  - `deploy`: Lines 532-536 print refusal and do nothing.
- **Redundant/Deprecated Verbs**:
  - `recipes`: Lines 842-1015 (173 lines) for legacy model recipes superseded by `models`.
  - `lora`: Lines 803-840 (37 lines) calling experimental local LoRA trainer.
- **Mixed Concerns (Benchmark/Paper Research in Orchestrator CLI)**:
  - `sweep`: Lines 2115-2165.
  - `probe`: Lines 2166-2210.
  - `silicon`: Lines 1950-2027.
  - `measure`: Lines 2028-2114.
  - Total research lines: ~260 lines mixed directly into main CLI dispatcher.

### B. MCP Gated/Dead Weight (`spacepilot/mcp_server.py` - 477 lines)
- **Gated Dummy Tools (Always Error)**:
  - `spacepilot_create_checkpoint`: Lines 148-173 (explicit docstring: "GATED 2026-09-22 - checkpoint sync is not implemented; this always errors").
  - `spacepilot_restore_checkpoint`: Lines 197-218 ("GATED 2026-09-22 - checkpoint restore is not implemented; this always errors").
  - `spacepilot_list_checkpoints`: Lines 175-195 (returns empty store).
  - `spacepilot_train_lora`: Lines 262-302 (unsupported job queue).
  - `spacepilot_download_model_recipe`: Lines 230-242 (calls `_mock_download_task` downloading nothing).

---

## 2. Actionable Execution Steps

### Step 1: Prune Zombie Commands from CLI
- Target: `spacepilot/cli.py`
- Remove definitions and argument parser registrations for:
  - `cmd_generate`
  - `cmd_sync`
  - `cmd_deploy`
  - `cmd_recipes`
- Deprecate/hide `lora` from `--help`.

### Step 2: Wire Low-Level Plumbing into CLI
- Add handlers connecting tested services to top-level CLI:
  - `cmd_download(args, cfg)` -> `spacepilot.services.model_downloader.download_weights`
  - `cmd_load(args, cfg)` -> `spacepilot.services.runtime_manager.load_model`
  - `cmd_unload(args, cfg)` -> `spacepilot.services.runtime_manager.unload_model`
- Expose CLI flags:
  - `spacepilot download --model <id> [--stage stage1|stage2|all] [--dest <dir>]`
  - `spacepilot load --model <id> [--weights-dir <dir>] [--backend sglang|vllm] [--port <int>]`
  - `spacepilot unload [--model <id>] [--all]`

### Step 3: Clean & Align MCP Server (`spacepilot/mcp_server.py`)
- Drop dead gated tools:
  - Remove `spacepilot_create_checkpoint`
  - Remove `spacepilot_restore_checkpoint`
  - Remove `spacepilot_list_checkpoints`
  - Remove `spacepilot_train_lora`
  - Remove `spacepilot_download_model_recipe`
- Expose tested, working infrastructure tools for Agents:
  - `spacepilot_download_weights(model: str, stage: str = "all", dest: Optional[str] = None)`
  - `spacepilot_load_runtime(model_id: str, weights_dir: str, backend: str = "sglang", port: int = 30010)`
  - `spacepilot_unload_runtime(model_id: Optional[str] = None, all_models: bool = False)`
  - `spacepilot_get_resident_models()`

### Step 4: Verification Suite
- Run `PYTHONPATH=. .venv/bin/pytest tests/test_cli_launch_workflow.py tests/test_runtime_manager.py tests/test_model_downloader.py tests/test_mcp_server.py`
- Verify `spacepilot --help` renders clean, scannable porcelain + plumbing without zombie commands.
