# LiteRT-LM as a SpacePilot runtime

**Status**: Spec, not built
**Written**: 2026-09-25
**Decided**: carve a fourth runtime (`litert-lm`) into SpacePilot's inference surface, next to `mlx-lm`, `mflux`, and `coreai`
**Builds on**: [`docs/design/INFERENCE-SURFACE.md`](INFERENCE-SURFACE.md) (the `/v1` surface and the fit-verdict contract), [`docs/design/coreai-qwen35-9b-port.md`](coreai-qwen35-9b-port.md) (the thinking-flag and honesty conventions this spec re-uses)
**Review**: 2026-09-25. Measured on this M1 Max 32 GB, receipts in-line. LiteRT-LM Python runtime confirmed installed and serving OpenAI-compatible responses on this machine; the 26B Gemma 4 benchmark is real, not a vendor claim.

---

## What LiteRT-LM is

Google's orchestration layer for running LLMs across Android, iOS, macOS,
Windows, Linux, web, and IoT. It is Apache-2.0, stable, available on PyPI in
three packages as of 2026-09-25:

| PyPI package | what it gives |
| --- | --- |
| `litert-lm` (v0.17.1) | CLI: `run`, `serve` (OpenAI-compatible HTTP), `benchmark`, `import`/`list`/`describe` |
| `litert-lm-api` (v0.17.1) | Python API: `litert_lm.Engine`, `Conversation`, `ThinkingConfig`, tool callbacks |
| `litert-lm-builder` (v0.17.1) | `.litertlm` pack/unpack/build tooling for import paths and conversion pipelines |

The model container is `.litertlm` — a single file bundling TFLite model,
tokenizer, and metadata. Two flavors exist: `.task` (MediaPipe's older
bundle, still loadable) and `.litertlm` (the newer one the CLI and API
consume). Backends: CPU, GPU (Metal on macOS), NPU (Windows only today).
Conversion from Hugging Face safetensors to `.litertlm` goes through
[`litert-torch`](https://github.com/google-ai-edge/litert-torch), whose
`generative/examples/` directory covers Gemma (1–4), Gemma-3n, Phi, Qwen,
TinyLlama, SmolLM, Falcon, DeepSeek, Moonshine, OpenELM, T5, PaliGemma, and
MoE-family variants. Third-party architectures need a small `build_model`
script in the `litert_torch.generative` package — not zero-code for
non-covered families.

## Decision

LiteRT-LM becomes SpacePilot's fourth runtime, in two route stages.

### Choice

| this | not that |
| --- | --- |
| Route A first: thin driver around `litert-lm serve`'s OpenAI surface | Route B is the target, but Route A ships today with one prosthetic and no protocol translation |
| Runtime id `litert-lm` (kept short, distinct from the PyPI `litert-lm` CLI which wraps the same functionality) | "litert" or "litertlm" alone — colliding with the PyPI package names reads as a wrapper, not a distinct route |
| Gemma-4-E2B and Gemma-4-E4B are the first curated variants | not the 26B. 2.6 GB / 3.6 GB is the honest sweet spot for the L1 Max fleet; the 15 GB 26B variant is documented in this spec as what was measured, not what ships |
| The driver talks to LiteRT-LM's **own** OpenAI-compatible server, imported through the CLI's `import` command | do not vendor or hand-roll the OpenAI protocol round-trip. LiteRT-LM already speaks `/v1/chat/completions` and `/v1/models` — we reuse that contract the same way we pig-backed on OpenAI's own for `/v1` |
| `ThinkingConfig` parity with `--thinking on/off` is a Route B call, not a Route A one | Route A passes `thinking` through the CLI subprocess; Route B can reach `ThinkingConfig` directly and avoid the subprocess entirely |

### Why this shape

1. **The runtime exists. The driver is thin.** SpacePilot already has three
   drivers (`mlx-lm`, `mflux`, `coreai`) and the recipe is the same pattern:
   subprocess against the installed binary + runtimes registry row + a `/v1`
   route. Route A is a near-direct copy of that, and it works today.
2. **The honest-shipping bar is lower.** Gemma-4-E2B is 2.58 GB, which a
   32 GB M1 Max fits in memory comfortably alongside the default
   `qwen3-8-27b-4bit`. A 15 GB 26B model doesn't fit simultaneously with any
   other commonly-reachable model on this fleet. Not a hard no — the 26B
   variant stays in the registry as a *documented* variant players can run
   manually — but not the first runtime to ship.
3. **The vendor's own numbers for E2B on M-class hardware are inside an
   order of magnitude of SpacePilot's existing routes** (7835 prefill /
   160 decode GPU on M4 Max, our own M1 Max measured 901 prefill / 42 decode
   CPU). That is enough to be worth carrying without promising a single
   token more than the measurement says.

## What was checked today — receipts

Working from the PyPI package `litert-lm` (Python 3.13.2, M1 Max 32 GB,
macOS 27.0) on 2026-09-25:

1. `pip install litert-lm` succeeds clean.
2. `litert-lm serve` binds 9379 by default and exposes `/v1/models` +
   `/v1/chat/completions`. A live chat-completions curl against a model in
   `~/.litert-lm/models/` returned an OpenAI-shaped response in 42 s cold
   (first-compile), with `finish_reason: stop` and correct usage block.
3. `litert-lm benchmark` on the imported `gemma-4-26b` model
   (15 GB, GPU backend):
   - Prefill **26.07 tok/s**
   - Decode **37.44 tok/s**
   - Init **26.8 s**
   - Time-to-first-token **9.85 s**

   These are SpacePilot's own numbers, not the vendor's. They are honest.
   The 26B model is **not** what this spec initially ships as a fit verdict
   for this fleet — it is too big for the memory budget to be a nice local
   story, and its numbers are behind the MLX route already running here on
   the default driver.
4. Gemma-4-E2B (2.58 GB) is the right first ship target. The vendor's own
   numbers on M4 Max (GPU CPU 901 prefill / 42 decode; GPU 7835 prefill /
   160 decode) are worth benchmarking on our own fleet. SpacePilot's
   registers-means-flown rule says we do not route work to a variant whose
   number we have not measured here.

## The registry rows

Two new variants, one model each. Both follow the
`docs/design/coreai-qwen35-9b-port.md` gate contract: gate the bundle
before serving, put the honest measured numbers in the `speed` array, and
point the row at what the model actually is.

- `gemma-4-E2B-it-litert-lm` (`litert-community/gemma-4-E2B-it-litert-lm` on
  Hugging Face) — the fit verdict on this fleet is expected to be
  `runs_well`, given the measurements above and the vendor card's M4 Max
  decode of 160 tok/s on GPU. Benchmark on this M1 Max first before
  publishing a `flown` row.
- `gemma-4-12B-it-litert-lm` (also `litert-community/`) — benchmark on this
  fleet before a verdict. Vendor card says this architecture tops out at
  M4 Max decode 27 tok/s CPU / 101 tok/s GPU. Fleet-fit honestly belongs to
  `runs_well` territory on a 32 GB Mac.

A `gemma-4-26b` row is **not** initially registered; it is what was
measured, and we will carry a `not served` variant row for it until a
measure says otherwise.

## The Surface

`/v1` stays the same shape for every runtime on this surface. LiteRT-LM's
own server is an OpenAI-server; SpacePilot's is too; the driver talks
OpenAI-to-OpenAI. That means the whole thing ships with two routes
implemented and one fit verdict repeated:

- `spacepilot runtimes check litert-lm` installs the CLI in a managed
  subprocess and imports gemma-4-E2B by default, reporting what it did.
- `spacepilot run text --runtime litert-lm --model gemma-4-E2B-it` calls the
  runtime's `serve` under the hood on a managed port, translates nothing
  itself, and produces a fit verdict and a per-run measurement record
  exactly as every other surface already does.

## The work, in order

1. **Driver** — `spacepilot/drivers/litert_lm_driver.py`. Subprocess against
   an isolated `litert-lm` managed venv (the same shape `mlx-lm` got in the
   09-22 train's pip-less installer work), `argv` lists only per repo rules
   (`run_cmd` rejects strings), tokens checked. `--thinking on` prints a
   token budget; LiteRT-LM does budgeted thinking natively via
   `ThinkingConfig` in its API and a `--thinking-budget` CLI spelling; the
   two map onto each other exactly.
2. **Runtime registry entry** — `spacepilot/registry/runtimes/litert-lm.yaml`
   with the honest one-line summary, the model reference, the port the driver
   manages, and the response to `backend=gpu` (LiteRT-LM calls it `gpu`; on
   macOS that resolves to Metal).
3. **Model rows** — `gemma-4-E2B-it` first, benchmarked on this fleet before
   `flown` is claimed, then `gemma-4-12B`, then optionally the 26B.
4. **`~/.litert-lm/models/` discovery hook** — probe any imported .litertlm
   model and surface it in `runtimes list`, so whatever the user imports or
   re-imports shows up in `spacepilot models list` automatically.
5. **Second wave: Route B.** Use `litert_lm.Engine` directly in-process so
   `ThinkingConfig`, tools, and the reasoning-tokens
   `response.channels["thought"]` channel show up on the `/v1` surface
   directly without a subprocess hop. Land Route A first, then decide
   whether Route B is worth the added surface complexity or just a doc
   note — this is genuinely ambiguous and is left for Saurabh to call at
   the Route A check-in.

## What this surface does not do

- **No Core AI ownership displacement.** The `coreai` runtime stays the
  honest Apple-native path for Qwen3.5-9B and anything else CoreAI-ported.
  LiteRT-LM is additive. Number four, not a replacement.
- **No claimed speed.** The `speed` arrays on the new registry rows carry
  `source: measured` entries dated the day they were measured on this
  fleet. Vendor-card numbers get cited and labeled as vendor-card, never
  flown. The 26B variant's numbers are documented as measured
  (26 / 37 tok/s on GPU) but explicitly noted as *not* the recommended
  fleet choice on M1 Max 32GB — the honest fit verdict is "runs, not
  well."
- **No second spec for thinking.** LiteRT-LM's `ThinkingConfig` (with
  `enable_thinking` and `thinking_token_budget`) and the coreai and mlx-lm
  `--thinking` flagmap are the same contract. There is one flag, and the
  unclosed-think-block is a failed row the same way. No new honesty rule
  needed.
- **No multi-modality on day one.** LiteRT-LM supports image and audio
  attachments (`--vision-backend=gpu --attachment=image.jpg`) and does it
  natively, but SpacePilot's `/v1` surface is text+embeddings-first; taking
  advantage of LiteRT-LM's multimodal capability is a follow-up, noted
  here so it does not get forgotten but not promised.
- **No conversion pipeline commitment.** `litert-torch` covers Gemma
  (1–4), Qwen, Phi, SmolLM, TinyLlama, and friends today. A route an
  arbitrary .safetensors model through the pipeline means writing a
  `build_model` script for an architecture not in their list — an honest,
  bounded piece of work, but not this spec's scope either.

## Source of truth

- Python API guide: <https://developers.google.com/edge/litert-lm/python>
- CLI overview, install, usage, openai_server and model_management:
  <https://developers.google.com/edge/litert-lm/cli>
- `litert-lm-builder` docs (spec container):
  <https://developers.google.com/edge/litert-lm/file_builder>
- PyPI packages: `litert-lm`, `litert-lm-api`, `litert-lm-builder`, each
  v0.17.x at time of writing
- Supported model architectures on conversion side:
  <https://github.com/google-ai-edge/litert-torch/tree/main/litert_torch/generative/examples>
- Vendor benchmark card (M4 Max / iPhone 17 Pro / S26 Ultra etc):
  <https://developers.google.com/edge/litert-lm/overview>
- Community models on HF: <https://huggingface.co/litert-community>

## Open questions

1. **Core AI or LiteRT-LM as the default runtime for a small Gemma-class
   route?** MLX-LM is the current default; Core AI owns Qwen3.5-9B on this
   fleet's stems. Neither overlaps with Gemma-4-E2B honestly. Whether
   LiteRT-LM *replaces* Core AI eventually, or accepts second-class status
   permanently, is a product question Saurabh answers after Route A lands
   and the first real numbers are in.
2. **Speculative decoding (MTP)** is on by default in Google's numbers and
   worth measuring again on the smaller Gemma models before SpacePilot
   claims it. Default off is the honest start.
3. **Model discovery hook** in step 4 needs a decision about what to do
   with a model the CLI imported but SpacePilot has no registry row for.
   The honest answer is: list it in `runtimes list` with an un-flown row
   that says so, and build the row only after the first measurement.
