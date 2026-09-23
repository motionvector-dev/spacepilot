# Changelog

All notable changes to SpacePilot are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- `ci`: gate PRs into `main-<date>` merge trains (CI gate on train PRs).
- `docs`: landing install switched to `uv tool install`; agent discovery via `llms.txt`, `AGENTS.md`, public `/docs`.
- `docs`: README first-run section updated to the `uv` quickstart, cites the v2.8.0 release.

### Changed

- `fix(mlx-lm)`: install into its own venv and serve from it.
- `fix(runtimes)`: install runtimes from a pip-less (uv-managed) interpreter.
- `fix(runtimes)`: describing an install must not perform one; a failed isolated install must not take away a working route.
- `fix(packaging)`: ship `web/` in the wheel, stop resolving paths into the install tree, gate the whole web tree, cover the static mount, hoist `state_root`.
- `fix`: version is read from the package instead of being duplicated.

### Fixed

- `fix`: make MCP match HTTP, and report what actually failed.
- `fix(honesty)`: one truth per surface for local status, memory and checkpoints; close the `is_downloaded` bug and unify the refusal idiom.
- `fix(tests)`: stop the suite overwriting the real config; report AWS failures on the shell socket; honest guard roots, real late-auth assertion, bounded socket error.
- `docs(agents)`: local packaging results on a built tree are not trustworthy; rule corrected against a measured experiment.

## [2.8.0] - 2026-09-19

### Added

- Splash Runtime engine: Metal-specialized inference with fused Metal kernels, 8-bit KV-cache decode, GDN prefill, and native DFlash 2 speculative decoding (`spacepilot/registry/runtimes/splash.yaml`).
- Qwen 3.8 Splash model card with Inco AI benchmarks (74 tok/s short, 54 tok/s at 32K context, 123 ms context reopen) mapped into flight plans (`spacepilot/registry/models/qwen3-8-splash.yaml`).
- Meta Muse Glimmer 30B (CoreAI) recipe with a K=4 DFlash speculative drafter, Apple Neural Engine/GPU dispatch, and Meta ATEM XML streaming (`spacepilot/registry/models/muse-glimmer-coreai.yaml`).
- MiniCPM5-2B registered with flown M1 Max timings for BF16 and MLX 4-bit (`spacepilot/registry/models/minicpm5-2b.yaml`).
- Desert Ant 12 CoreML/ANE models across STT (Voz), speech denoising (Clear), alignment (Align), and disfluency detection (Uhm).
- Ternary computing runtimes for BitNet 2B4T, Bonsai 8B, and energy measurement (`joules_per_token`).
- Standalone `uv` / `pip` distribution with native `spacepilot` and `spacepilot-mcp` entrypoints.

### Changed

- Model registry and recipe expansion across Splash, Muse Glimmer, MiniCPM5-2B, and Desert Ant 12.

### Hardened

- Removed hardcoded Doppler and personal credentials (`LOCAL-SETUP.md`, `.env.example`) — sovereign local-first packaging.
- Strict 40-character hex SHA revision pinning enforced across all shipped variants (AuK, Nemotron-3, etc.), verified by `tests/test_model_revisions.py`.
