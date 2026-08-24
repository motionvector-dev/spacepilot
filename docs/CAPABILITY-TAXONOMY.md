# Capability taxonomy — the schema caveats hang on

---
status: draft
authority: normative
decided_at: 2026-08-24
last_verified_at: 2026-08-24
owners: [founder]
depends_on: THESIS.md (the caveat ledger is the moat)
---

A caveat says whether a compressed or derived model variant still does a specific
job. This file is the finite list of *jobs* — the capabilities a caveat can be
about — with the standard metric for each and what is known to break it.

Researched 2026-08-24 across text, audio, image and video, every claim cited to a
primary source. Findings and the source list are in the PR thread; the load-bearing
citations are inline below.

## The one principle behind the whole thing

For every modality, **the headline metric is blind to the capability that breaks
first.**

- Perplexity looks fine while **code and reasoning** collapse.
- WER looks fine while **word-timestamps** break.
- Per-frame FID looks fine while the **video flickers**.
- Overall image quality looks fine while **text inside the image** garbles.

That blindness is why a registry of measurements is not enough and the caveat ledger
has to exist. **A caveat names its own metric.** We never certify a variant on the
aggregate; we certify each capability on the metric that can actually see it.

## What a caveat record is

A caveat attaches to a `(variant, capability)` pair, not to a model.

| Field | Meaning |
| --- | --- |
| `variant` | the specific artifact — base model + method + degree |
| `capability` | one slug from the taxonomy below |
| `status` | `preserved` \| `degraded` \| `untrained` \| `absent` |
| `metric` | the standard metric that measures this capability |
| `method` | **the compression scheme, not the bit-width** (see rule) |
| `provenance` | `measured` \| `inferred` \| `declared` |
| `detail` | one human sentence + evidence link |

**Status meanings.** `preserved` — as good as the base. `degraded` — measurably
worse but present. `untrained` — the capability was never optimised for this variant
(distillation's signature failure); it may *appear* to work and be quietly wrong.
`absent` — not there at all.

**The method rule.** "Q4" is underspecified and misleading. Across all four
modalities, *how* you compress matters more than the bit count:

- weight-only quant is far safer than weight+**activation** quant, which is safer
  than **KV-cache** quant (LLM: W8A8 destroyed ~92% of HumanEval while weight-only
  Q4 lost 5–22% — [arxiv 2506.22776](https://arxiv.org/pdf/2506.22776)).
- outlier-aware 4-bit (SVDQuant) preserves in-image text that plain NF4 4-bit loses,
  *at the same bit-width* — [arxiv 2411.05007](https://arxiv.org/abs/2411.05007).
- **distillation, quantization and pruning degrade different axes** (below). A
  variant that is both distilled and quantized loses both, independently.

So `method` records the scheme: `quant/weight-only`, `quant/weight+act`,
`quant/kv-cache`, `distill/step`, `distill/knowledge`, `prune`, `vae-tiling`,
`step-cache`, `lora-merge` — plus the degree (`q4_k_m`, `fp8`, `4-step`, `50%`).

## The taxonomy

★ = best-evidenced dissociation, and directly relevant to our first user's jobs.
"Fragile to" names the method that breaks it; a blank means broadly robust.

### text.*  (LLM)

| slug | capability | metric | fragile to |
| --- | --- | --- | --- |
| `text.fluency` | generic language modelling | perplexity (WikiText/C4) | — (but misleading; never certify on this) |
| `text.knowledge` | factual MCQA / understanding | MMLU / MMLU-Pro | — (most robust) |
| `text.long-context` | retrieve across long inputs | RULER, LongBench | ★ 4-bit (to 59%), esp. KV-cache quant |
| `text.instruction-following` | obey format/constraints | IFEval | KV-cache quant (pass-rate → 17%) |
| `text.code` | correct executable code | HumanEval+, LiveCodeBench | ★ weight+activation quant |
| `text.reasoning` | multi-step math/logic | GSM8K, MATH, GPQA | ★ low-bit (errors compound) |
| `text.multilingual` | non-English, low-resource | FLORES-200, MGSM | low-resource under any quant |
| `text.tool-use` | schema-valid function calls | BFCL v3 | KV/activation quant; JSON > string |
| `text.factual-recall` | retrieve stored facts | TriviaQA, NQ | 4-bit; small models most |
| `text.safety` | refuse harm, not over-refuse | HarmBench, XSTest | pruning; zero-shot-quant supply-chain risk |
| `text.agentic` | multi-turn plan + orchestrate | BFCL multi-turn | ★ 4-bit / 50% prune |

### audio.*  (ASR, TTS, VAD, audio-gen)

| slug | capability | metric | fragile to |
| --- | --- | --- | --- |
| `audio.transcription` | correct word sequence | WER / CER | — (q5_1/q8_0, distil all ≤1%) |
| `audio.word-timestamps` | per-word start/end times | timestamp F1 @200ms collar | ★★ **distillation** (heads never trained) |
| `audio.translation` | X→English speech translation | BLEU | distilled-English variants (absent) |
| `audio.multilingual-asr` | per-language ASR | per-lang WER by tier | low-resource under quant/prune |
| `audio.diarization` | who spoke when | DER | distillation (not quant/prune) |
| `audio.tts-naturalness` | human, clear speech | MOS | — (int8 ≈ fp32) |
| `audio.voice-cloning` | speaker-identity fidelity | SMOS / embed cosine | quant (before naturalness) |
| `audio.prosody` | rhythm/intonation/pronunciation | prosody MOS / PER | *unconfirmed — needs eval* |
| `audio.vad-boundary` | onset/offset precision | boundary error (ms) | boundary before detection |
| `audio.audio-gen-quality` | music/SFX high-freq fidelity | FAD, CLAP | aggressive int8 (keep AE fp16) |

`audio.word-timestamps` is the flagship caveat — the one that motivated this whole
product. Distillation optimises text and *segment* timestamps but never the
cross-attention heads word-timing rides on, so distil-whisper transcribes within 1%
WER while word timestamps go quietly wrong — it fits, it's fast, and your
filler-word cut breaks. Structural, so `inferred` with high confidence:
[distil-large-v3.5 disc #6](https://huggingface.co/distil-whisper/distil-large-v3.5/discussions/6),
[training README](https://github.com/huggingface/distil-whisper/blob/main/training/README.md),
[CrisperWhisper 2408.16589](https://arxiv.org/pdf/2408.16589).

### image.*  (diffusion / flow)

| slug | capability | metric | fragile to |
| --- | --- | --- | --- |
| `image.text-rendering` | legible text inside the image | OCR edit-distance (NED) | ★ 4-bit & naive quant (FP8 mostly OK) |
| `image.photorealism` | texture / material fidelity | FID, LPIPS | — (robust to FP8/INT8/Q8) |
| `image.prompt-adherence` | objects, count, spatial, attrs | GenEval, T2I-CompBench++ | — (coarse comp. robust) |
| `image.fine-detail` | hands, faces, boundaries | LPIPS/PSNR vs ref | pruning >30%; low-bit |
| `image.style-diversity` | variety across seeds | DreamSim pairwise dist | ★ **step-distillation** (mode collapse) |
| `image.color-exposure` | hue accuracy, no banding | PSNR/SSIM | FP8/low-bit banding (early) |
| `image.high-res-coherence` | global structure at high res | FID @ resolution | low-bit |

Clean orthogonality: **quant kills `text-rendering`; distillation kills
`style-diversity`.** Different axes, and a Turbo+FP8 variant loses both
independently. [Ideogram PTQ 2606.12280](https://arxiv.org/html/2606.12280v1),
[Distilling Diversity 2503.10637](https://arxiv.org/html/2503.10637v2).

### video.*  (uses VBench's temporal-vs-frame-wise split)

| slug | capability | metric (VBench dim) | fragile to |
| --- | --- | --- | --- |
| `video.frame-quality` | any single frame in isolation | Imaging / Aesthetic Quality | — (robust; **this is the trap**) |
| `video.temporal-consistency` | frame-to-frame stability, no flicker | Temporal Flickering, Motion Smoothness | ★★ FP8/int8 quant, step-cache |
| `video.motion-amount` | how much moves; not near-static | Dynamic Degree | ★ **step-distillation** (motion collapse) |
| `video.identity-coherence` | subject/object stable over time | Subject / Background Consistency | quant jitter, cache drift |
| `video.prompt-adherence` | matches the text | semantic dims + Overall | step-caching (semantic drift) |
| `video.long-stability` | quality holds as length grows | VBench-Long / accumulation | caching, autoregressive drift |
| `video.resolution-detail` | high-freq texture | Imaging Quality | int4 & below; bad VAE seams |

The headline result: quant preserves `video.frame-quality` while wrecking
`video.temporal-consistency`, and per-frame metrics — even FVD — **cannot see it**.
Certify video on per-VBench-dimension deltas vs the fp16 reference, never on
FID/FVD alone. [ViDiT-Q 2406.02540](https://arxiv.org/pdf/2406.02540),
[FVD content-bias, CVPR2024](https://content-debiased-fvd.github.io/).

## Cross-method rule (record this on every caveat)

The three methods degrade different families of capability:

- **Quantization** → text-in-image, video temporal, LLM long-context/code/reasoning.
  Cliff is at 4-bit-and-below; FP8/INT8/Q8 ≈ base for most axes.
- **Step-distillation** → diversity (image), motion (video), word-timestamps and
  long-form timing (audio). Fidelity often survives; the *targeted* axis is fine and
  everything untargeted is `untrained`.
- **Pruning** → fine detail (faces/hands/boundaries), reasoning. Threshold-shaped:
  fine to ~30%, cliff after.

Stacked methods lose stacked axes, independently.

## The v1 starter set

Full coverage is the curator's long job. For v1 — MotionVector's video agent — the
caveats that actually gate real jobs, in order:

1. `audio.word-timestamps` — filler-word cut, caption sync. ★ the flagship.
2. `video.temporal-consistency` — the one per-frame QA can't catch.
3. `image.text-rendering` — titles, lower-thirds, any on-screen text.
4. `video.motion-amount` — distilled video going near-static.
5. `audio.transcription` — record it `preserved` so the agent trusts it.

## How these get populated (ties to the thesis)

- **Structural caveats** — derivable from method + base model, no run needed
  (`audio.word-timestamps` from "distillation never trains the alignment heads").
  The scheduled curator emits these as `inferred`. Cheap, generalizes across models.
- **Empirical caveats** — need an `eval` on the fleet against the metric above.
  Only these earn `measured`. Run them on the variants that matter.

The curator proposes `inferred`; the fleet promotes to `measured`. Provenance is
never skipped.

## Gaps to close (from the research, honestly)

- Quantization effect on `audio.word-timestamps` specifically is **unconfirmed** —
  the distillation story is well-evidenced, the quant story is not. Eval it.
- `audio.prosody` / pronunciation as isolated axes under quant — unconfirmed.
- silero-VAD int8-vs-fp32 parity — no published number; measure on our runtime.
- `text.tool-use` and `text.multilingual` each had one contradicting source — treat
  as model-dependent until we eval.
