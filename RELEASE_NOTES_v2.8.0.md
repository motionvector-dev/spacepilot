# SpacePilot v2.8.0 Release Notes

**The Narrow Waist for Single-Owner AI Compute Fleets**

SpacePilot dynamically schedules generative workloads across heterogeneous personal and cloud machines based on real, empirical readiness rather than rated hardware specifications.

---

### What's New in v2.8.0

#### 1. Inco AI Splash Runtime & Qwen 3.8
- **Splash Runtime Engine**: Metal-specialized inference engine with fused Metal kernels, 8-bit KV-cache decode, GDN prefill, and native DFlash 2 draft speculative decoding (`spacepilot/registry/runtimes/splash.yaml`).
- **Qwen 3.8 Splash Model Card**: Added model card with Inco AI benchmarks (74 tok/s short, 54 tok/s at 32K context, 123 ms context reopen) mapped into flight plans (`spacepilot/registry/models/qwen3-8-splash.yaml`).

#### 2. Model Registry & Recipe Expansion
- **Meta Muse Glimmer 30B (CoreAI)**: CoreAI recipe with K=4 DFlash speculative drafter, Apple Neural Engine/GPU dispatch, and Meta ATEM XML streaming (`spacepilot/registry/models/muse-glimmer-coreai.yaml`).
- **MiniCPM5-2B**: Registered with flown M1 Max timings for BF16 and MLX 4-bit (`spacepilot/registry/models/minicpm5-2b.yaml`).
- **Desert Ant 12 CoreML/ANE Models**: Comprehensive on-device CoreML/ANE models across STT (Voz), speech denoising (Clear), alignment (Align), and disfluency detection (Uhm).
- **Pinned Model Revisions**: Strict 40-character hex SHA revision pinning enforced across all shipped variants (AuK, Nemotron-3, etc.) verified via `tests/test_model_revisions.py`.

#### 3. Sovereign Inference & Hardening
- **Sovereign Local-First Packaging**: Completely cleaned of hardcoded Doppler and personal credentials (`.env.example`, `LOCAL-SETUP.md`).
- **Ternary Computing Runtimes**: Support for BitNet 2B4T, Bonsai 8B, and energy measurement (`joules_per_token`).
- **Standalone `uv` / `pip` Tool Distribution**: Built with native entrypoints for `spacepilot` and `spacepilot-mcp`.

---

### Quickstart

#### Direct Installation via `uv`
```bash
uv tool install spacepilot
# Or directly from source:
uv tool install git+https://github.com/motionvector-dev/spacepilot.git
```

#### Verification
```bash
# Probe local hardware and memory topology
spacepilot probe

# Verify environment and available runtimes
spacepilot doctor
```
