# LTX-Video 2.5 / 0.9.8 — Full Capability Research
> Research compiled: 2026-08-21 | Sources: GitHub, HuggingFace Diffusers, Lightricks docs, ComfyUI ecosystem

---

## 1. Image Conditioning — Start & End Frames

**Yes — LTX supports BOTH a start image AND an end image simultaneously.**

This is called **First-Last Frame (FLF2V)** or **"sandwich" conditioning**. It is one of the flagship features of the model.

### How it works

```python
from diffusers import LTXConditionPipeline
from diffusers.pipelines.ltx.pipeline_ltx_condition import LTXVideoCondition
from diffusers.utils import load_image

pipe = LTXConditionPipeline.from_pretrained("Lightricks/LTX-Video-0.9.5", torch_dtype=torch.bfloat16)
pipe.to("cuda")

img_first = load_image("first_frame.png")
img_last  = load_image("last_frame.png")

# num_frames must satisfy (N-1) % 8 == 0, e.g. 161
cond_first = LTXVideoCondition(image=img_first, frame_index=0,   strength=1.0)
cond_last  = LTXVideoCondition(image=img_last,  frame_index=160, strength=1.0)

video = pipe(
    prompt="Describe the transition motion...",
    conditions=[cond_first, cond_last],
    num_frames=161,
    height=480, width=832,
).frames[0]
```

- **`strength`**: 0.0–1.0. 1.0 = strict adherence. 0.7 = more creative interpolation.
- **Prompt guidance**: Describe the *motion/transition*, not just the scene.
- **Pluto Studio status**: ❌ Not implemented — only single `image_path` (start frame) is supported.

---

## 2. Full LTX-Video 0.9.8 Feature Matrix

| Feature | Available | Pluto Studio Status |
|---|---|---|
| **Text-to-Video (T2V)** | ✅ | ✅ Implemented |
| **Image-to-Video (I2V, single start frame)** | ✅ | ✅ Just added in PR |
| **First-Last Frame / FLF2V (start + end image)** | ✅ | ❌ Missing |
| **Multi-keyframe conditioning (N images at N frame indices)** | ✅ | ❌ Missing |
| **Video Extension (forward — extend a clip)** | ✅ | ❌ Missing |
| **Video Extension (backward — prepend to a clip)** | ✅ | ❌ Missing |
| **Video-to-Video (V2V / style transfer)** | ✅ | ❌ Missing |
| **Draft Mode (distilled, 8 steps)** | ✅ | ✅ Just added in PR |
| **Long video up to 60s (multi-prompt temporal chunking)** | ✅ (13B 0.9.8) | ❌ Missing |
| **Latent upscaler pipeline (multiscale)** | ✅ `LTXLatentUpsamplePipeline` | ❌ Missing (4K upscaler is pixel-space only) |
| **IC-LoRA: Depth control** | ✅ | ❌ Missing |
| **IC-LoRA: Pose control** | ✅ | ❌ Missing |
| **IC-LoRA: Canny/edge control** | ✅ | ❌ Missing |
| **IC-LoRA: In-Outpainting** | ✅ | ❌ Missing |
| **IC-LoRA: Detailer (upscale+sharpen)** | ✅ | ❌ Missing |
| **Standard LoRA (style, character)** | ✅ | ❌ Missing |
| **FP8 quantized weights** | ✅ | ❌ Not offered as option |
| **Multi-prompt (evolving scene text)** | ✅ | ❌ Missing |
| **STG (Spatio-Temporal Guidance)** | ✅ | ⚠️ `stg_scale` param exists but not exposed in UI |
| **Synchronized Audio+Video (LTX-2)** | ✅ LTX-2 only | ❌ Missing |
| **Native 4K / 50fps** | ✅ LTX-2 only | ❌ |

---

## 3. Key Parameters We Have But Don't Expose Properly

### STG Scale (`stg_scale`)
- **What it does**: Spatio-Temporal Guidance — training-free method that skips attention layers to create an implicit "weak model" for guidance. Improves temporal consistency and motion quality.
- **Recommended values**:
  - `0.0` = disabled (for distilled model — it doesn't need STG)
  - `0.5–1.0` = balanced (good for draft)
  - `1.0–2.0` = strong guidance for complex motion
  - `> 2.0` = over-guided, may reduce diversity
- **Pluto Studio status**: Parameter exists in backend, slider exists in create page but hidden/not prominent

### Modality Scale (`modality_scale`)
- **What it does**: Controls how faithfully the generated video adheres to the conditioning image(s). Higher = closer to input image, lower = more creative.
- **Recommended**: `1.0` default, `0.5–1.5` practical range
- **Pluto Studio status**: Backend has it, not exposed in any UI

### `conditioning_strength`
- **What it does**: Per-conditioning-item strength for each keyframe anchor
- **Pluto Studio status**: Not exposed — hardcoded to 1.0 internally

---

## 4. What We Should Build Next (Priority Order)

### Priority 1 — High impact, low effort
**A. First-Last Frame (FLF2V) in Creator**
- Add a second "End Frame" dropzone in `create.html`
- Backend: pass both `image_path` (frame 0) and `end_image_path` (frame N-1) to worker
- Worker: uses `LTXVideoCondition` with `frame_index=num_frames-1` for end image
- UI badge: `🔀 Interpolate` mode

**B. Expose STG Scale + Modality Scale in UI**
- Simple sliders, already wired in backend
- Draft mode auto-sets STG to 0.0, Pro auto-sets to 1.0

### Priority 2 — Medium impact, medium effort
**C. Video Extension (Extend Clip forward)**
- In Pro Studio: right-click a Take → "Extend 4s" 
- Backend: passes existing MP4 as `conditioning_media` at frame 0, generates N more frames
- Creates seamless continuation

**D. Latent Upscaler Pipeline**
- Replace current pixel-space 4K upscaler with `LTXLatentUpsamplePipeline`
- Better temporal consistency, less flicker, same VRAM cost

**E. Multi-prompt (Evolving Scene)**
- In Creator: add a timeline bar where user types different prompt per segment
- Backend: uses `--conditioning_media_paths` with frame timestamps

### Priority 3 — Big features
**F. IC-LoRA Controls (Depth / Pose / Canny)**
- User uploads reference video → choose control type → depth/pose drives motion
- `LTX-Video-ICLoRA-depth-13b-0.9.7`, etc.
- Needs 48GB VRAM (L40S) to run comfortably

**G. FP8 Quantized Model Option**
- Add `fp8` toggle in cockpit config
- Loads `ltxv-13b-0.9.8-distilled-fp8.safetensors`
- ~30% VRAM reduction, ~same quality on L40S

**H. LTX-2 Audio+Video**
- Entirely new model (LTX-2, 22B), weights not yet public
- Monitor Lightricks GitHub for release

---

## 5. Frame Count Rules (Critical)

The model requires `num_frames` to satisfy:
```
(num_frames - 1) % 8 == 0
```
Valid values: 1, 9, 17, 25, 33, 41, 49, 57, 65, 73, 81, 89, 97, 105, 113, 121 (5s @ 24fps), 241 (10s), 481 (20s)...

Our current backend does: `((raw_frames - 1) // 8) * 8 + 1` ✅ Correct.

Resolution must be divisible by 32.

---

## 6. Model Versions Available Right Now

| Model | Size | Speed | Quality | Use case |
|---|---|---|---|---|
| `ltxv-2b-0.9.8-distilled` | 2B | Very fast | Good | Draft/preview |
| `ltxv-13b-0.9.7-distilled` | 13B | Fast (8 steps) | High | Default Pro |
| `ltxv-13b-0.9.7-distilled-fp8` | 13B FP8 | Fastest | High | Low VRAM Pro |
| `ltxv-13b-0.9.8-distilled` | 13B | Fast | Highest | Current best |
| `ltxv-13b-0.9.8-dev` | 13B | Slow (30+ steps) | Reference | Max quality |

**Currently Pluto uses**: The worker references `ltxv-13b-0.9.8-distilled` config — good choice.
