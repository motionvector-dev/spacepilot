# Technical Specification: SpacePilot CLI Hierarchy Modernization & Deprecation Pruning

**Date**: 2026-10-07  
**Branch**: `feat/h3-aws-launch`  
**Status**: APPROVED FOR TDD IMPLEMENTATION  

---

## 1. Problem Statement
The current SpacePilot CLI (`spacepilot/cli.py`) registers 21 top-level verbs in its root argument parser. This creates cognitive bloat for both human users and AI agents:
1. **Deprecated commands still exposed**: `recipes` (superseded by `models`), `lora` (incomplete experimental trainer), and `check` (redundant alias for `doctor`).
2. **Benchmark & research clutter**: `measure`, `sweep`, and `silicon` pollute the primary orchestrator namespace.
3. **Missing standard CLI flags**: `spacepilot --version` returns an unhandled argument error.

---

## 2. Target Production Architecture

The modernized CLI organizes operations into three tiers:

### A. Top-Level Orchestrator Commands (11 Verbs)
- **Lifecycle & Workflows**:
  - `launch`: Provision AWS Spot GPU instance tailored to model working sets.
  - `run`: Execute multimodal inference (`run video`, `run text`, `run image`, `run speech`, `run transcribe`).
  - `status`: Show local or cloud instance state, VRAM usage, and health.
  - `terminate`: Terminate active EC2 instance to stop billing.
- **Atomic Inference Primitives**:
  - `download`: Download model weights to disk cache (staged or full).
  - `load`: Mount weights into resident runtime daemon (SGLang/vLLM).
  - `unload`: Reclaim GPU VRAM by evicting active runtime.
  - `models`: Inspect model registry, variants, and fit verdicts.
- **Diagnostics & Daemon**:
  - `doctor`: Audit local accelerators, dependencies, and cloud credentials.
  - `probe`: Detect hardware topology and output system telemetry.
  - `serve`: Launch combined web portal and local API.

### B. Grouped Subcommand: `spacepilot bench`
Internal research and benchmarking tools are consolidated under `spacepilot bench`:
- `spacepilot bench measure`: Time execution metrics (`seconds_per_step`, `tokens_per_second`).
- `spacepilot bench sweep`: Run declarative measurement sweeps across hardware.
- `spacepilot bench silicon`: Inspect known Apple Silicon/NVIDIA silicon hardware parts.

### C. Standard Global Flags
- `--version`: Output package version (`spacepilot 2.9.0`).
- `-v` / `--verbose`: Enable debug logging and full stack traces.
- `--live` / `--plain`: Toggle TUI update renderer.

---

## 3. Implementation Plan

1. **Delete Deprecated Verbs**:
   - Remove `cmd_recipes` and the `recipes` subparser.
   - Remove `cmd_lora` and the `lora` subparser.
   - Remove alias `check`.
2. **Consolidate Benchmarks**:
   - Add subparser `bench` with nested subcommands: `measure`, `sweep`, `silicon`.
   - Wire backward-compatible forwarding if `measure`/`sweep`/`silicon` are invoked directly, or route cleanly under `bench`.
3. **Add `--version`**:
   - Add `parser.add_argument("--version", action="version", version=f"spacepilot {__version__}")`.
4. **Update Dispatch Map & Tests**:
   - Update `build_parser()` and `dispatch` dictionary.
   - Add test suite `tests/test_cli_modernization.py` asserting clean verb hierarchy and `--version`.
5. **Verify Full Test Suite**:
   - Run pytest across all test modules.
