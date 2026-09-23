# Handoff: Qwen3.5-9B Core AI port

**Date:** 2026-09-22
**Spec:** `docs/design/coreai-qwen35-9b-port.md`
**State:** the bundle exists and the gates have run. It is not served.

Read the spec for the rules. This page is where the work stopped.

## Do this next

Do not register the variant. Do not add `coreai` to `WIRED_RUNTIMES`. The train gate failed on a wrong number.

The wrong number is not a bundle defect. On 2026-09-22 the Hugging Face fp16 checkpoint itself answered the identical G2 prompt (token ids verified equal to the bundle's, see `gates/g2_hf_ref.py`) with "2 hours and 11 minutes" — same three lines, same off-by-two. The record is `gates/g2_hf.json` and `gates/g2_hf_rendered.txt`. The failure is in the base model's minutes-to-h/m step, not in the int8 export, and no quantization change fixes it. Why the MLX 4-bit run got 2 h 13 min is a separate open question and stays open: the 4-bit blobs are 79-byte stubs, so a rerun means a fresh download.

Int4 is not the next export. The spec keeps int8 as the ship until a long gate passes, and this int8 bundle has not passed — but the failing item fails the checkpoint itself, not just the bundle.

Int4 is not the next export. The spec keeps int8 as the ship until a long gate passes, and this int8 bundle has not passed.

## What already landed

| thing | where |
| --- | --- |
| CLI honesty PR, not merged | https://github.com/motionvector-dev/spacepilot/pull/167 branch `feat/local-text-cli-honesty` at `b3ab31a` |
| Spec, driver, this handoff | uncommitted on that branch |
| Default text model | still `qwen3-8-27b-4bit` |

The PR is thinking-off, a failed row for an unclosed `<think>`, route readiness, and the download bar. It also registers MiMo, Gemma 4 26B-A4B, Maple, Bonsai, and LFM. It does not register Qwen3.5-9B.

Uncommitted, and not wired:

- `spacepilot/drivers/coreai_driver.py`
- `spacepilot/drivers/coreai_tokenize.py`
- `tests/test_coreai_driver.py` (2 passed, 2026-09-22, no model load)

## The bundle

| fact | value |
| --- | --- |
| Checkpoint | `Qwen/Qwen3.5-9B` @ `c202236235762e1c871ad0ccb60c8ee5ba337b9a`, Apache-2.0 |
| Export | `int8hu --head-sym --max-ctx 8192` |
| Bundle | `~/code/unfoundbox/ml-ai/qwen35-9b-coreai-exports/qwen3_5_9b_decode_int8hu_block32_sym/` |
| Weights | `main.mlirb`, 10,469,493,277 bytes |
| Loader skip | 333 `model.visual.*` keys and 15 `mtp.*` keys. Text is `model.language_model.*` plus the untied `lm_head.weight`. |
| Runner | `~/code/unfoundbox/ml-ai/coreai-models/.build/out/Products/Release/llm-runner` |
| Benchmark | same directory, `llm-benchmark` |
| Engine | Apple `coreai-models` `3f109ef`. `coreai-pipelined`. `COREAI_CHUNK_THRESHOLD=1` |

The zoo extra-states patch does not apply to `3f109ef`. It does not need to. That engine already accepts 2 to 4 states (Apple commit `6329412`, 2026-08-03). The first runner call still has to compile the bundle. Later calls hit the cache, about 3 to 4 seconds to load.

The overlay used for the export is a detached worktree, not the clean Apple checkout:

- zoo: `~/code/unfoundbox/ml-ai/coreai-model-zoo`
- overlay worktree: `~/code/unfoundbox/ml-ai/coreai-models-qwen35-export` at `b1cb71b`, patch applied
- Apple checkout left at `3f109ef`: `~/code/unfoundbox/ml-ai/coreai-models`
- Python for the export: that checkout's `.venv` (torch 2.9.0; Core AI asked for 2.11; the export finished anyway)

The download of the bf16 shards was anonymous. `hf_xet` is installed there. `HF_TOKEN` was not set. The MLX bake-off used a different repo, `mlx-community/Qwen3.5-9B-4bit` @ `8b2b98c`. Those weight blobs are 79-byte stubs now. Do not plan a rerun on them.

## Gates

Transcripts: `~/code/unfoundbox/ml-ai/qwen35-9b-coreai-exports/gates/`

Greedy, thinking off, one model at a time. The engine refused `--save-logits`, so this is not a forced-token logit walk. G1 and G3 compare 16 generated tokens with the Hugging Face continuation.

| gate | result |
| --- | --- |
| G1 | Pass. Same text as Hugging Face. Decode 35.7 tok/s on 16 tokens. Prefill 6.6 tok/s on 17 tokens. |
| G2 code | Pass. `second_largest` is correct. 11.2 tok/s, 51 tokens. |
| G2 train | Fail. 133 minutes, then "2 hours and 11 minutes". HF fp16 gives the same wrong answer (`gates/g2_hf.json`), so this item fails the base model, not the bundle. |
| G2 NVIDIA | Pass. Refused. No invented close. |
| G3 | Pass. 692-token prompt, next 16 tokens match Hugging Face. Prefill 16.7 tok/s, decode 17.7 tok/s. |

`enable_thinking=False` was passed. The official template still writes a closed empty `<think></think>` before the answer. That is the off switch, not a stuck trace.

## Left alone

- Gemma 4 26B-A4B. MoE block, 128 experts, global head dim 512. A later port.
- A 16-token prefill graph. This bundle prefills one token at a time.
- SpaceBar. Still read-only.
- The money path. No dock, no rental.
- The 3 Sep daemon sketch, `docs/design/macos-coreai-provider-backend-runtime.md`. Not this port.
