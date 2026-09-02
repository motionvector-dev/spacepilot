# SpacePilot — the inference surface

**Status**: Spec, partly built
**Written**: 2026-09-02
**Builds on**: `docs/design/CONCEPT.md` (honesty rules), `docs/design/VISION.md`

Coding models and embeddings are the lead workload. This is the HTTP surface
they run on, the one fit verdict every surface repeats, and the record each
call leaves behind.

The surface is deliberately OpenAI-shaped. Every coding agent already speaks
it, so an existing tool points at `http://localhost:8088/v1` and works. What
SpacePilot adds is not a better port — it is knowing what fits before the
download and what actually happened after.

## Routes

All three live on the existing FastAPI app (`spacepilot/app.py`, port 8088),
behind the same loopback-only middleware as everything else.

| route | method | token | what it does |
| --- | --- | --- | --- |
| `/v1/models` | GET | no | Every registry variant that a local driver can serve, each with its fit verdict. Read-only, so it stays open like `/api/measurements`. |
| `/v1/chat/completions` | POST | yes | One bounded generation. Streaming or not. |
| `/v1/embeddings` | POST | yes | Embeds one string or a list of them. |

The two POSTs take `X-SpacePilot-Token` through `require_token`, because they
spend compute. `test_compute_endpoints_all_require_the_token` walks the app and
will fail if either is added without it.

## Shapes

Request bodies are the OpenAI ones. `model`, `messages`, `max_tokens`,
`temperature`, `stream` for chat; `model`, `input` for embeddings. Unknown
fields are rejected rather than ignored, so a caller never believes a knob took
effect when it did not.

Responses are the OpenAI ones plus one extra object, namespaced so no client
parser trips on it:

```json
{
  "id": "chatcmpl-…", "object": "chat.completion", "model": "qwen3-8-27b-4bit",
  "choices": [{"index": 0, "message": {"role": "assistant", "content": "…"},
               "finish_reason": "stop"}],
  "usage": {"prompt_tokens": 12, "completion_tokens": 24, "total_tokens": 36},
  "x_spacepilot": {
    "verdict": {"level": "runs_well", "reason": "uses 72% of the memory available to models",
                "headroom_bytes": 7480000000},
    "system_id": "apple-m1-max-32gb",
    "runtime": "mlx-lm",
    "revision": "3e6447f082e89cc7f0bc6e5441afd38dfce760ff",
    "run_id": "0f3c…", "tokens_in": 12, "tokens_out": 24, "wall_seconds": 12.04
  }
}
```

`revision` is the resolved commit of the weights that ran, not the repo id. A
repo id moves; that is the whole reason the registry pins revisions.

Streaming is SSE. Each event is a `data: ` line carrying one
`chat.completion.chunk`, and the stream ends with `data: [DONE]`. The last
chunk before `[DONE]` carries `usage` and the full `x_spacepilot` block — the
numbers only exist once generation finishes.

## Model id to driver

A `model` value is a registry **variant id** (`qwen3-8-27b-4bit`), not a repo
path. Resolution:

```
model id ──▶ registry variant ──▶ recipe ──▶ fit_verdict
                                     │
                                     ├─ mlx-lm driver   (metal, first choice)
                                     └─ gguf driver     (intended fallback, not wired)
```

The gguf fallback is named because it is the plan, not because it exists.
`spacepilot/drivers/gguf_driver.py` today is a screenplay decomposer with a
fixed output shape, not a chat driver; wiring it to `/v1` is M3 work. Until
then `/v1/models` marks every unwired variant `served: false` and the POST
routes refuse it, rather than quietly answering with a model nobody asked for.

- Unknown id → **404**, listing what `/v1/models` would have said.
- Known id, `wont_fit` → **409**, body carries the verdict. Never a silent
  downgrade to a smaller model, and never a silent fall through to a rented
  box: renting is a decision (`CONCEPT.md`, "Money is loud").
- Known id, fits, weights not cached → **409** naming the download command.
- Driver failure → **502**, with the driver's own message. Not a 200 with an
  apology in the content.

## One verdict, three surfaces

```python
fit_verdict(model_id: str, system: DeviceProfile) -> dict
# {"level": "runs_well" | "runs_slowly" | "wont_fit",
#  "reason": str, "headroom_bytes": int | None}
```

One function, in `spacepilot/verdict.py`. `/v1/models`, `spacepilot models`,
and the MCP tool `spacepilot_recommend_models` all call it, so all three say the
same words. Before it, they did not: the CLI printed `fits`/`tight`, the MCP
tool printed "Optimal Local Execution", and the API said nothing at all.

| `assess()` says | `fit_verdict` level |
| --- | --- |
| `fits` | `runs_well` |
| `tight` | `runs_slowly` |
| `wont_fit` | `wont_fit` |
| `blocked` (wrong backend) | `wont_fit` |
| `unknown` | `unknown` |

`headroom_bytes` is usable memory minus working set — negative when the model
is larger than the machine, `null` when either number is unmeasured.

**The fourth string is deliberate.** `assess()` returns `unknown` when nothing
measured this machine's memory or this model's footprint. Folding that into one
of the three verdicts would report a guess as a grading, which is the failure
the honesty rules exist to stop. `unknown` is the absence of a verdict, not a
fourth kind of one. See the open questions.

## What every call records

`Measurement` (`spacepilot/measurements.py`) gains three optional fields:

| field | meaning |
| --- | --- |
| `run_id` | uuid4, minted per call. The join key. |
| `tokens_in` | prompt tokens the driver counted, `null` if it could not. |
| `tokens_out` | generated tokens, `null` if it could not. `0` for embeddings. |

Every `/v1` call writes exactly one record, metric `tokens_per_second`. That
makes cost per outcome a join rather than an estimate: AgentWorth holds the
outcome and the run id, SpacePilot holds the tokens, the wall time, the
machine and the weights.

The fields are optional so every record written before today still parses
unchanged. A driver that cannot count tokens writes `null`, never a number
derived from character count. A fabricated token count is worse than a missing
one, because it looks like a measurement.

## Embeddings

Route: mlx-lm, the runtime already installed and already pinned.

Model: **`mlx-community/Qwen3-Embedding-0.6B-8bit`**, revision
`407ad2329cd30702720aafe83f74a1ba30fdfbca`, 649 MB, 1024 dimensions. Its
`config.json` says `model_type: qwen3`, so `mlx_lm.load()` loads it as an
ordinary Qwen3 model. `model.model(tokens)` returns the final normed hidden
states; last-token pooling plus an L2 normalise gives the vector, which is
what Qwen3-Embedding is trained for.

`mlx-embeddings` is **not installed** on this machine and is not a dependency
here. Nothing was invented: the path above is the installed `mlx_lm` 0.31.3.

Verified 2026-09-02 on `local-ml-py311`: weights loaded in 0.81 s, three
strings embedded, cosine 0.87 between two paraphrases and 0.56 between
unrelated sentences, peak memory 0.62 GB. That is a working embedder, not a
plausible-looking one.

## Errors

Every error body is `{"error": {"message": …, "type": …, "code": …}}`, the
OpenAI shape, plus `x_spacepilot.verdict` on a 409 so the caller learns why.
Rules that bind:

- No fabricated token counts, ever. `null` beats a guess.
- A refusal says what would fix it: the download command, the smaller variant.
- A failed run should record a `Measurement` with `status: "failed"`. It does
  not yet — the routes raise and record nothing, so a crash is currently
  invisible to the corpus. M3 closes that.
- No silent fallback to another model, another machine, or a paid API.

## What is installed here

Checked 2026-09-02 on `local-ml-py311`, the repo interpreter:

| package | version |
| --- | --- |
| `mlx.core` | 0.31.2 |
| `mlx_lm` | 0.31.3 |
| `coremltools` | 9.0 |
| `llama_cpp` | 0.3.35 |
| `mlx_embeddings` | not installed |

CoreAI/CoreML is the next rung, not this one. `coremltools` being present is
why M3 is credible, not evidence that anything runs through it — nothing does.

## Milestones

| | scope | acceptance |
| --- | --- | --- |
| **M1** | `fit_verdict`, `/v1/models`, wired into CLI and MCP | one test asserts all three surfaces emit the same level string for the same variant |
| **M2** | `/v1/chat/completions` (both modes), `/v1/embeddings`, Measurement fields | route-shape tests with mocked drivers; token-gate walk covers both POSTs; a recorded Measurement carries `run_id` and both token counts |
| **M3** | Second local runtime: gguf wired for chat, then CoreAI/CoreML | a gguf variant answers `/v1/chat/completions`; a converted model answers with `runtime: "coreai"` |
| **M4** | Dock routing: `wont_fit` offers a rented box with a price | a 409 carries an estimate, and renting still needs an explicit yes |

M1 and M2 ship in this PR. M3 and M4 do not.

## Open questions

- Is `unknown` an acceptable fourth level, given the three-string rule? (yes/no)
- Should `/v1/models` list variants whose weights are not cached? (yes/no)
- Should `/v1/models` stay open, or take the token like the POSTs? (yes/no)
- Is Qwen3-Embedding-0.6B the right default embedder, or should it be larger? (yes/no — yes keeps 0.6B)
