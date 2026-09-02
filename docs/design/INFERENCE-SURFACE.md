# SpacePilot — the inference surface

**Status**: Spec, partly built
**Written**: 2026-09-02
**Builds on**: `docs/design/CONCEPT.md` (honesty rules), `docs/design/VISION.md`

Text and embeddings are the newest routes on SpacePilot's inference surface,
added 2026-09-02 because AgentWorth and SpaceBar need them — image, speech,
transcription, and (mock) video already sit on the same surface. This doc is
the HTTP surface text and embeddings run on, the one fit verdict every
surface repeats, and the record each call leaves behind.

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
path. Resolution is a lookup against the registry, not a hardcoded pair —
`spacepilot/routes.py` is the one place that answers it, read by `/v1/models`,
both POST routes, the text and embedding execution services, and `spacepilot
run text --model`:

```
model id ──▶ registry variant ──▶ recipe ──▶ fit_verdict
                                     │
                                     └─ spacepilot.routes.route_for(variant_id)
                                          served when: variant.model_id is in a
                                          WIRED runtime's `runs:` list, and the
                                          variant declares that runtime's backend
                                          (metal, today) ──▶ mlx-lm driver
```

Every text and embedding variant the mlx-lm runtime's `runs:` list names is
served this way, not one hardcoded id each — adding a model to `runs:` (with
a matching registry entry and recipe) is enough for it to show up
`served: true` and answer `/v1/chat/completions`, no code change needed.

`WIRED_RUNTIMES` in `spacepilot/routes.py` is the guard on that: a runtime
can declare `runs:` for a model with no execution path behind it at all —
`llama-cpp.yaml` lists `deepseek-r1-distill-qwen`, but
`spacepilot/drivers/gguf_driver.py` today is a screenplay decomposer with a
fixed output shape, not a chat driver; wiring it to `/v1` is M3 work. Only
runtimes in that list count as served, so `/v1/models` marks every unwired
variant `served: false` and the POST routes refuse it, rather than quietly
answering with a model nobody asked for.

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

## Remote providers

The dock's third rung, arriving early. M1/M2 built the local rungs — mlx-lm
now, gguf and CoreAI later — each earning a fit verdict on this machine.
Renting a box (`CONCEPT.md`'s "money is loud") is the rung after that, still
undesigned. Between them, one thing does not fit the local ladder at all: a
model that never runs on this machine because it is not supposed to — testing
SpaceBar's brain against a strong model while Apple Intelligence is off, or
while the local rungs are not there yet. `claude-sonnet-5` is that: a second
backend behind the same `/v1/chat/completions`, for testing, not a competitor
to the local rungs.

**Dispatch.** `chat_completions` checks the prefix before anything else: a
`model` starting with `claude-` skips the registry, `fit_verdict`, and the
mlx-lm plan entirely and goes to `spacepilot/services/anthropic_provider.py`.
Only `claude-sonnet-5` is wired; any other `claude-*` id is `404
model_not_found`, the same refusal an unknown local id gets — no silent
substitution to whichever Claude model happens to exist.

**No fit verdict.** `fit_verdict` grades whether a model fits *this machine's*
memory. A remote call never touches this machine's memory, so grading it would
answer a question that was not asked. The response and `GET /v1/models` both
carry `x_spacepilot.verdict = {"level": "remote"}` instead of one of the three
local words, plus `x_spacepilot.provider = "anthropic"` so a client can tell
the two backends apart without parsing the model id.

**The key gates everything, including the listing.** `ANTHROPIC_API_KEY` is
read from the environment at request time — never stored on the provider
object, never logged, never placed in a response or error body. `GET
/v1/models` lists `claude-sonnet-5` only when the key is present in this
process's environment; an offline machine must not advertise a model it
cannot serve. A `claude-sonnet-5` request with no key set is `503
provider_unconfigured`, the OpenAI error shape, same as every other refusal on
this surface.

**Refusals are a stop reason, not a crash.** When the SDK reports
`stop_reason == "refusal"`, the route does not return 200 with an apology in
the content — it returns the same OpenAI error shape everything else on this
surface uses, `type: "refusal"`, `code: "refusal"`, with the refusal category
in the message when Anthropic supplied one. Streaming refusals land in-band,
the same way a mid-stream driver failure does on the local path.

**What gets recorded.** Every claude-sonnet-5 call — success or refusal —
writes exactly one `Measurement`, the same contract as the local routes:
`run_id`, `tokens_in`/`tokens_out` from `response.usage` (never estimated from
characters), `metric: "tokens_per_second"`, `runtime_id: "anthropic"`. `value`
is real: this machine timed its own round trip to Anthropic's API, so the
number is measured even though the weights ran somewhere else.
`system_id` names the machine that made the call, not a machine that ran
anything — the join key AgentWorth needs to ask "what did testing on Sonnet
cost" is the same run id either backend writes.

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
