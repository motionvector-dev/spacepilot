# LTX-2.5 Deep Dive, Experimentation Matrix & Pluto CLI Audit

This document provides a technical reference for **LTX-2.5** (Lightricks' 22B parameter multi-modal diffusion transformer for synchronized video and audio), a complete **configuration experimentation matrix**, and an architectural audit of the **Pluto CLI / Worker** codebase.

---

## 1. LTX-2.5 Architecture & Capabilities

LTX-2.5 is a foundational Diffusion Transformer (DiT) designed for joint video and audio synthesis with native temporal coherence.

```
┌────────────────────────────────────────────────────────────────────────┐
│                      LTX-2.5 MULTI-MODAL PIPELINE                      │
└────────────────────────────────────────────────────────────────────────┘
                      ┌──────────────────────┐
                      │ Text Prompt / Image  │
                      └──────────┬───────────┘
                                 │
                   ┌─────────────┴────────────┐
                   │ T5-XXL / Vision Encoder  │
                   └─────────────┬────────────┘
                                 │
                ┌────────────────┴────────────────┐
                ▼                                 ▼
   ┌───────────────────────────┐     ┌───────────────────────────┐
   │    Video Latent Stream    │<───>│    Audio Latent Stream    │
   │ (3D Spatial-Temporal DiT) │     │ (Mel-Spectrogram Latents) │
   └─────────────┬─────────────┘     └─────────────┬─────────────┘
                 │ Cross-Modality Attention        │
                 ▼                                 ▼
   ┌───────────────────────────┐     ┌───────────────────────────┐
   │    Spatial-Temporal VAE   │     │    LTX-2 Vocoder (BWE)    │
   │ (1080p / 24fps MP4 Video) │     │   (48kHz Stereo Audio)    │
   └───────────────────────────┘     └───────────────────────────┘
```

### Core Innovations in LTX-2.5
1. **Unified Video + Audio DiT**: Synthesizes synchronized sound effects, dialogue tone, and ambient noise natively aligned with physical actions on screen without secondary audio models.
2. **Spatio-Temporal Guidance (STG)**: An attention-perturbation mechanism that reduces motion blur and high-frequency jitter in fast action scenes.
3. **Modality Isolation Guidance**: Enforces acoustic-visual synchronization by controlling cross-attention strength between video and audio latent branches.
4. **Two-Stage Latent Super-Resolution**: Generates base latents at native resolution (e.g. 544p), followed by `LTX2LatentUpsamplePipeline` for artifact-free 1080p scaling.
5. **Quantized Native Inference (FP8 / TorchAO)**: Drops memory footprint from >50GB down to ~24–30GB VRAM, enabling resident operation on single L40S (48GB) or A100 GPUs.

---

## 2. Comprehensive Experimentation Parameter Matrix

Here is the parameter reference for testing and tuning LTX-2.5 generation quality, camera dynamics, temporal stability, and audio realism.

### A. Spatial & Temporal Dimensions

| Parameter | Type | Valid Range / Formula | Default | Impact & Best Practice |
| :--- | :--- | :--- | :--- | :--- |
| `width` / `height` | `int` | Multiples of 64 (e.g. `1024x576`, `768x512`, `1280x720`) | `1024x576` | Higher resolutions increase VRAM quadratically. For 1080p, use base `960x544` with the Latent Upsampler. |
| `num_frames` | `int` | `((seconds * fps - 1) // 8) * 8 + 1` | `97` (4.0s @ 24fps) | **Strict Invariant**: Must satisfy `(num_frames - 1) % 8 == 0` (e.g. `49`, `65`, `81`, `97`, `121`). |
| `frame_rate` | `float` | `24.0`, `25.0`, `30.0` | `24.0` | 24fps delivers cinematic motion blur; 30fps is crisper for tech/UI demos. |
| `seconds` | `float` | `1.0` to `10.0` | `4.0` | Clips beyond 6s may accumulate subtle drift without high STG or image anchoring. |

---

### B. Multi-Modal Guidance Controls

| Parameter | Type | Range | Recommended | Description & Tuning Guide |
| :--- | :--- | :--- | :--- | :--- |
| `guidance_scale` (CFG) | `float` | `1.0` – `7.5` | `1.0` (distilled)<br>`3.5` (base) | Prompt adherence for video. Keep at `1.0` for distilled checkpoints to avoid burn. |
| `audio_guidance_scale` | `float` | `1.0` – `5.0` | `1.0` (distilled)<br>`3.0` (base) | Controls audio volume, clarity, and adherence to audio cues in the prompt. |
| `stg_scale` | `float` | `0.0` – `2.0` | `0.5` – `1.0` | **Spatio-Temporal Guidance**: Perturbs self-attention to eliminate motion jitter and enhance micro-movements. |
| `stg_blocks` | `list[int]` | `[28]` or `[29]` | `[28]` | Transformer block index where self-attention is short-cut for STG calculation. |
| `audio_stg_scale` | `float` | `0.0` – `1.5` | `0.0` | STG applied to audio spectrogram generation (useful for high-fidelity dialogue). |
| `modality_scale` | `float` | `0.0` – `3.0` | `1.0` – `1.5` | Forces video motion to match audio events (e.g. lips moving when speaking, footsteps timing). |
| `guidance_rescale` | `float` | `0.0` – `1.0` | `0.0` – `0.7` | Eliminates over-exposure and high-contrast burnout when using high CFG (>4.0). |

---

### C. Sampler, Steps & Schedulers

| Parameter | Type | Default | Experiment Options | Technical Notes |
| :--- | :--- | :--- | :--- | :--- |
| `num_inference_steps` | `int` | `30` | `8` (distilled), `25` (standard), `45` (high-detail) | Diminishing returns above 35 steps unless using high CFG. |
| `sigmas` | `list[float]` | None | `DISTILLED_SIGMA_VALUES` | Custom noise schedule. Distilled weights require exact distilled sigmas for 8-step passes. |
| `seed` | `int` | Random | Fixed `int` | Guarantees deterministic temporal seeds for A/B prompt comparisons. |
| `decode_chunk_size` | `int` | `8` | `4`, `8`, `16` | Slices temporal VAE decoding to prevent VRAM spikes during final MP4 export. |

---

### D. Image-to-Video Conditioning

| Parameter | Type | Range | Default | Function |
| :--- | :--- | :--- | :--- | :--- |
| `image` | `PIL / Tensor` | File path | None | Input keyframe. Anchors character appearance, lighting, and spatial composition. |
| `conditioning_scale` | `float` | `0.5` – `1.0` | `1.0` | Strength of initial frame constraint. `1.0` = rigid identity; `0.7` = allows drastic posture changes. |
| `image_noise_scale` | `float` | `0.0` – `0.1` | `0.0` | Adds slight Gaussian noise to image latent to encourage dynamic, non-static camera pans. |

---

## 3. 5 Ready-to-Run Experiment Recipes

### Recipe 1: High-Speed Cinematic Action (Sharp Motion, No Blur)
* **Goal**: Car chase, running, or rapid dancing without motion ghosting.
* **Settings**:
  ```python
  {
      "width": 1024, "height": 576,
      "num_inference_steps": 35,
      "guidance_scale": 3.0,
      "stg_scale": 1.2,                    # High STG sharpens edge transitions
      "spatio_temporal_guidance_blocks": [28],
      "modality_scale": 1.2,
      "guidance_rescale": 0.5
  }
  ```

### Recipe 2: Lip-Sync & Acoustic Synchronization
* **Goal**: Close-up dialogue or musical performance where mouth movements must sync to sound.
* **Settings**:
  ```python
  {
      "width": 896, "height": 512,
      "num_inference_steps": 30,
      "guidance_scale": 2.5,
      "audio_guidance_scale": 3.5,         # Higher audio guidance
      "modality_scale": 2.0,               # Maximizes cross-modal audio-visual attention
      "audio_stg_scale": 0.5
  }
  ```

### Recipe 3: 2-Stage 1080p Ultra-HD Master (Base + Latent Upscaler)
* **Goal**: Studio-grade 1920x1080 resolution without VRAM explosion.
* **Pipeline Workflow**:
  1. Generate base latents via `LTX2Pipeline` at `960x544` with `output_type="latent"`.
  2. Pass latents into `LTX2LatentUpsamplePipeline` with 15 refinement steps.
  3. Decode via tiled spatial-temporal VAE.

### Recipe 4: Rapid 8-Step Distilled Drafts (<6s Render Time)
* **Goal**: Instant storyboard iteration on Mac or spot box.
* **Settings**:
  ```python
  from diffusers.pipelines.ltx2.utils import DISTILLED_SIGMA_VALUES

  pipe(
      prompt=prompt,
      num_inference_steps=8,
      sigmas=DISTILLED_SIGMA_VALUES,
      guidance_scale=1.0,
      stg_scale=0.0
  )
  ```

### Recipe 5: Character Shelf I2V Consistency
* **Goal**: Animating character shelf assets from `~/Desktop/ltx-shelf/`.
* **Settings**:
  ```python
  {
      "image": "~/Desktop/ltx-shelf/char1/Screenshot.png",
      "conditioning_scale": 0.95,
      "image_noise_scale": 0.02,           # 2% noise to unlock dynamic camera motion
      "guidance_scale": 2.0,
      "stg_scale": 0.6
  }
  ```

---

## 4. Pluto CLI & Worker Architecture Audit

We conducted an in-depth audit of [`src/cli.py`](file:///Users/saurabh/code/motionvector/pluto-i2v/src/cli.py), [`src/ltx_worker.py`](file:///Users/saurabh/code/motionvector/pluto-i2v/src/ltx_worker.py), and [`infra/setup_ltx_ec2.sh`](file:///Users/saurabh/code/motionvector/pluto-i2v/infra/setup_ltx_ec2.sh).

### Key Findings & Vulnerability Matrix

| Severity | Component | Finding | Architectural Impact |
| :--- | :--- | :--- | :--- |
| 🔴 **CRITICAL** | `src/ltx_worker.py` | **Duplicate Model VRAM Allocation** | `load_i2v_model()` loads a *second* full 22B pipeline into CUDA, holding both T2V and I2V pipelines simultaneously. Risks CUDA OOM on 48GB cards. |
| 🔴 **CRITICAL** | `infra/setup_ltx_ec2.sh` | **Unpinned Dependencies** | `pip install torchao` installs bleeding-edge versions that break on DLAMI PyTorch (`ScalingType` error). |
| 🟡 **MAJOR** | `src/ltx_worker.py` & `cli.py` | **Hardcoded Invariants** | `stg_scale`, `modality_scale`, `negative_prompt`, and guidance settings are hardcoded in the worker and inaccessible from `pluto generate`. |
| 🟡 **MAJOR** | `src/ltx_worker.py` | **Rigid Concurrency Lock** | Returns HTTP `409 Busy` when `_active >= 1`, rejecting requests instead of using an in-memory queue. |
| 🟢 **MINOR** | `src/cli.py` | **Multipart Upload Implementation** | Uses manual `http.client` string formatting for image upload instead of `urllib3` / standard multipart streams. |
| 🟢 **MINOR** | `src/cli.py` | **Silent Polling Failures** | Polling loop in `cmd_generate` contains empty `except Exception: pass`, masking network drops. |

---

## 5. Detailed Audit Recommendations & Code Patches

### Finding 1: Shared Transformer Memory (Fixing VRAM Double-Allocation)
**Problem**: In `ltx_worker.py`:
```python
# Currently loads TWO separate model copies in VRAM
_pipe = LTX2Pipeline.from_pretrained(...)       # 28 GB VRAM
_pipe_i2v = LTX2ImageToVideoPipeline.from_pretrained(...) # Another 28 GB VRAM -> OOM!
```
**Fix**: Share the underlying `transformer`, `text_encoder`, `vae`, and `vocoder` components between pipelines:
```python
def load_i2v_model():
    global _pipe_i2v, _pipe
    if _pipe_i2v is not None:
        return
    # Reuse identical weights already resident in VRAM
    _pipe_i2v = LTX2ImageToVideoPipeline(
        transformer=_pipe.transformer,
        text_encoder=_pipe.text_encoder,
        tokenizer=_pipe.tokenizer,
        vae=_pipe.vae,
        scheduler=_pipe.scheduler,
        vocoder=_pipe.vocoder,
    )
```

---

### Finding 2: Exposing Advanced LTX-2.5 Controls to CLI
Update `src/cli.py` to expose the new parameter matrix:
```python
gen_p.add_argument("--negative-prompt", type=str, default="blurry, distorted, low quality")
gen_p.add_argument("--stg", type=float, default=0.0, help="Spatio-Temporal Guidance scale (0.0 - 1.5)")
gen_p.add_argument("--modality-scale", type=float, default=1.0, help="Audio-Visual synchronization scale")
gen_p.add_argument("--guidance-scale", type=float, default=1.0, help="Classifier-Free Guidance scale")
gen_p.add_argument("--fps", type=int, default=24, help="Output video frame rate (default: 24)")
```

---

### Finding 3: Pinning Remote Dependencies in `setup_ltx_ec2.sh`
Prevent runtime breaks across different AWS DLAMI images:
```bash
/opt/pytorch/bin/python -m pip install -q \
  "git+https://github.com/huggingface/diffusers@main" \
  "transformers>=4.48.0" \
  "torchao>=0.8.0,<0.12.0" \
  accelerate safetensors sentencepiece protobuf av imageio imageio-ffmpeg Pillow numpy scipy flask
```

---

## 6. Summary Checklist for Pluto v2.0

- [x] LTX-2.5 parameter and multi-modal architecture verified
- [ ] Implement shared component loading between T2V & I2V pipelines
- [ ] Add CLI flags for `--stg`, `--modality-scale`, `--guidance-scale`, and `--negative-prompt`
- [ ] Integrate optional 2-stage latent upscaling (`--upscale-1080p`)
- [ ] Update `setup_ltx_ec2.sh` with pinned dependency versions
