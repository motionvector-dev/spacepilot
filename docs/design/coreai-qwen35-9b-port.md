# Core AI port: Qwen3.5-9B

**Status:** gated 2026-09-22. Not served. The train item fails at fp16 too (checked 2026-09-22), so that specific failure is a base-model limitation, not a bundle defect. The bundle stays unserved.
**Date:** 2026-09-22
**Review:** 2026-09-22. Swift subprocess, context 8192, a 512-token state gate before serving, no MLX registry row, thinking flag explicit.
**Builds on:** `docs/design/INFERENCE-SURFACE.md` milestone M3, `docs/design/VISION.md`

This is the first Core AI model SpacePilot will run. One checkpoint, one bundle, three gates. A converted model answers through `runtime: "coreai"`. Nothing else in that sentence is in scope.

`docs/design/macos-coreai-provider-backend-runtime.md` (3 Sep 2026) is a sketch. The daemon, the socket, the hot-swap, and the Neural Engine decode path in it were unchecked then and are unchecked now. This spec does not build them.

## Decision

| choice | this spec |
| --- | --- |
| Model | `Qwen/Qwen3.5-9B`, the text decoder |
| Exporter | `john-rocky/coreai-model-zoo` `conversion/export_qwen3_5_decode_pipelined.py` |
| Ship bundle | `int8hu --head-sym --max-ctx 8192` |
| Runner | patched Swift `llm-runner`, one shot, then exit |
| SpacePilot default | stays `qwen3-8-27b-4bit` |
| Generation cap | stays 256 tokens (`MAX_SAFE_TOKENS`) |
| Thinking | off. The template call passes `enable_thinking=False`. The runner takes raw token ids. |

## What was checked

Checked 2026-09-22 against the zoo script on `main` and against a local MLX snapshot.

The script loads `text_config` through `Qwen3_5StatefulForCausalLM.from_hf_memory_efficient`. It turns each linear-attention layer onto `use_loopfree_step`. It quantizes, then `export_to_coreai`, `optimize`, and writes `.aimodel`, `metadata.json`, and a tokenizer. The traced token has frozen `input_ids` of shape `[1, 1]`. `position_ids`, `k_cache`, and `v_cache` grow up to `--max-ctx`. `conv_state` and `rec_state` stay fixed. The script's own note: the GatedDeltaNet `while` loop does not lower on the GPU delegate, so the graph is one token. Prompt tokens repeat that graph. `COREAI_CHUNK_THRESHOLD=1` is how the engine is told to do that. The Swift extra-states patch is required to run the bundle, because the engine otherwise carries two states and this model has four.

The local MLX snapshot `mlx-community/Qwen3.5-9B-4bit` at `8b2b98c00a6b4d291155e4890773ca8f769aee53` has the same decoder shape the zoo used for Ornith-1.0-9B: `qwen3_5`, 32 layers, full attention 16 query / 4 KV heads, head dim 256, linear attention 32 value / 16 key heads, vocab 248320. It also has a vision tower and `mtp_num_hidden_layers: 1`. Ornith's card says that loader skips `model.visual.*`. Whether this checkpoint's MTP weights load or error is not confirmed. The first export command is a dry load that lists skipped keys. If those keys are anything besides `model.visual.*` and `mtp.*`, stop. A decoder change means this spec is wrong.

On this machine (M1 Max, 32 GB, Metal limit 26,800,603,136 bytes, macOS 27.0) the MLX 4-bit copy answered three short prompts with thinking off and temperature 0: load 1.7 s, 55–59 tok/s. That run is the behavior reference. It is not the export input. The export reads the Hugging Face bf16 checkpoint.

Zoo numbers below are theirs, on an M4 Max, dated on their cards. They are not a prediction for this machine.

| bundle | their size | their M4 Max | gate they published |
| --- | --- | --- | --- |
| Ornith-1.0-9B int8hu, same script | 9.8 GB | 48.3 decode / 48.5 prefill tok/s | 24/24 short, engine 12/12 |
| Ornith-1.0-9B int4lin | 7.5 GB | 58.9 / 59.0 tok/s | same short gate only |
| Qwen3.5-0.8B pipelined int8 | ~1 GB | ~204–210 tok/s | 16/16 |
| Qwen3.5-0.8B custom Metal kernel | | 58.5 tok/s | slower than the pipelined graph |
| Qwen3.5-0.8B Neural Engine | | 14.7 tok/s | slower than the GPU |

Ornith's card keeps int8 as the ship because the int4 gate is short, and a Gemma 4 vision port passed a short int4 gate that failed at a few hundred tokens. Base Qwen3.5-9B has not been shown to tolerate int4.

## Out of scope

- Gemma 4 26B-A4B. Its config has `enable_moe_block`, 128 experts, top 8, and global head dim 512. The zoo's Gemma scripts do not build that block. The 12B already needed a custom kernel for the wide head (`apple/coreai-models#27`).
- A 16-token prefill function. The Qwen3.8 vision bundle measured 86 tok/s prefill against 16 tok/s for the one-token graph. Chunks of 32 overflowed fp16 in that scan. That function is a later spec.
- Int4 as a ship candidate. It can be exported beside int8. It does not become the served variant in this spec.
- Neural Engine, speculative decode, LoRA, a resident server, a daemon, a socket.
- Changing the default text model.
- SpaceBar. It stays read-only. No new daemon route.
- The money path. No dock, no rental, no provider call.
- Registering the MLX 4-bit snapshot. Separate decision. This variant is the `.aimodel`.

## Bundle

```
Qwen/Qwen3.5-9B  (bf16, pinned revision)
        |
        |  text_config only
        v
int8 per-block-32 body, fp16 embed / conv / norms
int8 absmax per-block-32 on the untied head  (--head-sym)
        |
        v
exports/qwen3_5_9b_decode_int8hu_block32_sym/
        *.aimodel
        metadata.json
        tokenizer/
```

Command, from the zoo's Ornith recipe with the id swapped:

```
export_qwen3_5_decode_pipelined.py int8hu --head-sym \
    --hf-id Qwen/Qwen3.5-9B --max-ctx 8192
```

`--max-ctx` is the graph's dynamic limit, not the generation cap. Eight full-attention layers with 4 KV heads of dim 256 at 8192 tokens is a few hundred MB of cache. The weight bundle is the resident cost. Expect about 10 GB, from Ornith's 9.8 GB of the same shape. Confirm by `stat` after export. Do not copy 9.8 GB into the registry until the file exists.

The export needs macOS. `coreai-core` is tied to the OS build. The Linux build box cannot run it. Start only when this laptop is free to get hot. One model in memory. No second export beside it.

License text is copied from the model card at the pinned revision. The registry row does not land if that card is not a license this repo already accepts as open source.

## Gate

The bundle is not done when the file exists. It is served only when all three gates pass on this machine, one model resident, thinking off, temperature 0. G1 and G2 still run. They are not enough on their own.

**G1. Tokens.** Teacher-forced top-1 against the Hugging Face model for 16 decode steps, plus one greedy continuation of at least 12 tokens. Same bar the zoo published for this script family. A mismatch fails the bundle. Record the prompt ids, both token lists, and the revision in the note.

**G2. The three prompts already run on MLX.** A Python function `second_largest(nums)`. A train from 14:40 to 17:05 with a 12 minute stop (answer 2 h 13 min). A request for the NVIDIA close on 2026-09-18, which must refuse. The Core AI answer has to agree with the MLX answer on the facts. Wording can differ. A wrong number, or a made-up close, fails the bundle — but the correct answer is checked against Hugging Face first. Checked 2026-09-22: the fp16 checkpoint itself answers this item wrong ("2 hours and 11 minutes", `gates/g2_hf.json` in the export dir). The item fails the base model, and no re-export fixes it. If the gate is rerun, the expectation for this item is already known-bad on both sides, and the comparison should proceed on the other two G2 items.

**G3. State at 512.** A prompt of at least 512 tokens, counted by this tokenizer, then 16 teacher-forced top-1 steps against the Hugging Face model. By then the KV cache and the linear-attention `conv_state` / `rec_state` have both moved. A top-1 miss fails the bundle. This gate runs against the runner directly. It does not raise `MAX_SAFE_TOKENS`. Served generations stay capped at 256.

The rendered prompt for every thinking-off run, including G2 and G3, is saved next to the transcript. It must come from `apply_chat_template(..., enable_thinking=False)`. For this model a template that rejects that argument is a failure. The LFM fallback in `apply_chat` does not apply here. The saved prompt must not contain `<think>` before generation starts.

An unclosed think block is a failure, same rule as `stopped_inside_think` in `spacepilot/services/text_execution.py`. The row's metric value is wall seconds. The speed goes in knobs.

Int4, if exported later, needs G1, G2, and G3 before anyone treats it as a candidate. That run is not part of the first ship.

## How SpacePilot runs it

M3's acceptance is one converted model answering `/v1/chat/completions` with `runtime: "coreai"`. The path is the text path that already exists.

```
variant id
    |
    v
registry  ->  runtime coreai  ->  fit_verdict
    |
    v
CoreAI driver
    |
    v
subprocess argv: patched llm-runner, bundle path, raw token ids, max tokens, temperature
    |
    v
text file + a JSON metrics line on stdout
    |
    v
text_execution records the run
```

`run_cmd` already rejects a shell string. The runner is an argv list. The driver checks the return code. A non-zero exit or an empty file is a failure, not a completed measurement.

One shot. Load, answer, exit. No resident process. This matches MLX today.

The Swift binary is the zoo's `llm-runner` built with `apps/coreai-pipelined-extra-states.patch`, run with `COREAI_CHUNK_THRESHOLD=1`. That subprocess is the M3 runtime. Stock `AIModel.load` does not meet the engine contract this bundle needs. If that binary cannot be built and pointed at by a config key, SpacePilot does not grow a fake runtime. The bundle can still exist. The variant stays unserved, the way `muse-glimmer-coreai` already does (`runtime` is none in `tools/fly.py`).

The driver renders the chat in-process, with `enable_thinking` set to the caller's choice, then passes raw ids (`--raw-tokens`). `--prompt` is the wrong door: the runner applies the Qwen template itself, and that template thinks unless the flag is passed. A Qwen3.5 call that omits `enable_thinking` is a bug.

Served variant id: `qwen3.5-9b-coreai-int8hu`. Runtime id: `coreai`. Backend: `metal`. The revision pin is the Hugging Face commit that was exported. The bundle file's sha256 is a second knob on the measurement. Both, because a rebuild at the same commit can still differ.

Fit uses the measured bundle bytes plus the measured peak from G2. Until G2 has a peak, the level is `unknown`. A guess of 9.8 GB is not a working set.

Calls record two rows under one `run_id` when the answer is real: `tokens_per_second` and `prompt_tokens_per_second`. That matches `text_execution.py` on the honesty branch. `INFERENCE-SURFACE.md` still says one row. The code is the rule for this port. The surface doc should be updated in the same change that serves the route, so the two do not disagree after merge.

`/v1/chat/completions` keeps `require_token`. Unknown fields stay rejected. `x_spacepilot.runtime` is `coreai`. Thinking off is the default. `--thinking on` is the opt-in, and an unclosed think is still a failed row.

`tools/fly.py` gets one flight plan, `needs_gate3=True`, until G1, G2, and G3 have passed on this machine. `tools/export_registry.py --sync` regenerates `web/registry.json` in the same commit. The MLX 4-bit snapshot is not registered in this port.

## Work slices

Each slice is reviewable on its own. None of them launches a rented machine.

| slice | lands | done when |
| --- | --- | --- |
| 1. Dry load | a note in the PR: skipped keys, pinned HF revision, license id, bundle byte size | skipped keys are only vision and MTP, or the slice stops |
| 2. Export + G1 + G2 + G3 | bundle path on this machine, gate transcript committed under `docs/design/` or the measurement store | all three gates pass, or the failure is written down. The rendered prompt is in the transcript |
| 3. Registry row | model yaml for the Core AI variant only, `runtimes/coreai.yaml`, flight plan, `web/registry.json` | variant resolves; fit is `unknown` until a peak exists; not served |
| 4. Driver | `spacepilot/drivers/coreai_runner.py`, raw-id argv, wired through `text_execution.py` | `spacepilot run text --model qwen3.5-9b-coreai-int8hu` returns the G2 answers, the saved prompt has `enable_thinking=False`, and the rows are real |
| 5. HTTP | route table only if the driver is the same object the CLI uses | one `/v1/chat/completions` call returns `runtime: "coreai"` and 401s without the token |

Slice 4 is the first SpacePilot code that can spend this GPU. Slices 1–3 can merge without it.

## Slice 1 result

Checked 2026-09-22. Pinned `Qwen/Qwen3.5-9B` at `c202236235762e1c871ad0ccb60c8ee5ba337b9a`. License on the model card is Apache-2.0. The four weight shards sum to 19,319,133,532 bytes. They were not downloaded. The index was.

The zoo loader (`Qwen3_5StatefulForCausalLM.from_hf_memory_efficient`) keeps `lm_head.weight` because `tie_word_embeddings` is false, keeps keys under `model.language_model.`, and skips every other key. That split on this index:

| keys | count | loader |
| --- | --- | --- |
| `model.language_model.*` | 426 | load |
| `lm_head.weight` | 1 | load |
| `model.visual.*` | 333 | skip |
| `mtp.*` | 15 | skip |

775 keys. Nothing else is in the index. The skip set is only the vision tower and the MTP block. Slice 1 does not stop the port.

## Gate result

Run 2026-09-22 on this M1 Max, bundle `qwen3_5_9b_decode_int8hu_block32_sym`, `llm-runner` from Apple `coreai-models` `3f109ef`, `COREAI_CHUNK_THRESHOLD=1`, engine `coreai-pipelined`, greedy. The pipelined engine refused `--save-logits` (`does not support returning logits`), so the check is greedy top-1 against the Hugging Face checkpoint, not a forced-token logit walk. Where the 16 tokens match, a teacher-forced walk would have matched too.

| gate | result |
| --- | --- |
| G1 | Pass. 16 greedy tokens decode to the same string as `Qwen/Qwen3.5-9B` at `c2022362`. 35.7 tok/s decode, 6.6 tok/s prefill on 17 prompt tokens. |
| G2 code | Pass. `second_largest` returns the second distinct value or None. |
| G2 train | Fail. The bundle said 133 minutes, then **2 hours and 11 minutes**. 133 minutes is 2 hours and 13 minutes. The MLX run of this checkpoint's 4-bit sibling got 2 hours 13 minutes. A wrong number fails the bundle. |
| G2 NVIDIA | Pass. It refused and did not invent a close. |
| G3 | Pass. After a 692-token prompt the next 16 tokens match the Hugging Face continuation. Prefill 16.7 tok/s, decode 17.7 tok/s. |

The variant is not served. `enable_thinking=False` was passed. This model's template still writes a closed empty `<think></think>` before the answer. An unclosed think did not appear.

## Review decisions

Locked 2026-09-22.

| question | decision |
| --- | --- |
| Runtime for M3 | Patched Swift `llm-runner` subprocess. Ship it. |
| Graph context | 8192. |
| When the variant may be served | After G1, G2, and G3. G3 is a 512-token prompt plus 16 teacher-forced steps. |
| MLX 4-bit row | No. This port registers the Core AI variant only. |
| Chat template | `enable_thinking=False` is a required argument on the Qwen3.5 path. The runner receives raw ids. |
