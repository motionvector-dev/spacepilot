# SpacePilot — product thesis

---
status: draft
authority: normative
decided_at: 2026-08-24
last_verified_at: 2026-08-24
owners: [founder]
supersedes: the federated-inference-exchange framing in DECISION-INBOX.md
---

## The sentence

**SpacePilot is the toolkit an AI agent uses to run ML work on your own fleet.**
It knows what your machines can actually run, whether the compressed version still
does the job, and it runs it there.

## The insight

The glue is commodity. A box is a box — keys, a connection, spawn a process. The
weights are the same Hugging Face download everyone pulls. Wiring fifteen providers
and benchmarking a thousand boxes is plumbing, not a product; LiteLLM, SkyPilot and
Ollama already own that.

The value is not breadth. It is **knowledge and honesty**: given this hardware and
this job, what runs, does the quantised build still work, and did it really run.

## We build the tools, not the agent

The intelligence is a general model the caller brings — Claude, or whatever comes
next. Frontier reasoning is commodity and gets cheaper every month. So we do not
build reasoning. We build what a smart caller cannot get on its own:

- It is **blind** — it cannot see your VRAM, thermals, or what is loaded now.
- It is **amnesiac** — it does not remember last week's measurement.
- Its facts are **stale** — its training does not know this month's model releases.
- It cannot **act or verify** — it cannot run the job or check the output is real.

Every tool supplies exactly one of those gaps.

## The toolkit — the agent's loop

| Verb | Tool | Today |
| --- | --- | --- |
| **Perceive** | `probe` — see the hardware | have; AMD/Vulkan blind |
| | `fleet_status` — nodes up, what is warm, live free VRAM | gap |
| **Know** | `model_lookup`, `fit_check` | have; recommender reads mock data |
| | `caveat_lookup` — does the compressed build still do task X | data model exists, thin |
| | `measurement_lookup` — real speed/memory on this system tier | have; 2 measured |
| | `derivative_graph` — given a base model, what quants exist | gap |
| | `license_check` — commercial-safe | gap |
| **Decide** | `recommend` — job → model + node | have; wire to real registry |
| | `cost_estimate` — $ and latency, warm vs cold | gap |
| | `plan_pipeline` — chain steps, place each | gap |
| **Do** | `run` per modality | audio + image local; video AWS-only |
| | `dispatch_to_node` — reach another machine | **gap — the core one** |
| | `launch` / `terminate` / `deploy` cloud | have (AWS) |
| | `cache_model` — real download + checksum | currently mock |
| | `warm` — preload weights on a node | gap |
| **Verify** | `measure` + record | have |
| | `verify_output` — real, or a mock/failure | gap |
| **Improve** | `lora_train` | have |
| | `eval` — score a model on a task | gap |

Two guards run under all of it: a **budget/idle-kill** ceiling (partial), and
**honest failure** — a tool that lies is worse than a missing one.

## The moat is three tools

Everything else exists somewhere. These do not:

1. **`caveat_lookup`** — the q4 build fits *and its word-timestamps were never
   trained*, so your filler-word cut silently breaks. Nobody publishes this.
2. **warm-state awareness** — a node already holding the weights answers in
   seconds; a cold one costs 20–50s to load. Cost-only routing gets this wrong.
3. **`verify_output`** — the difference between "it ran" and "it returned a
   test-pattern tagged success".

They are what make the agent a competent MLOps engineer in your fleet instead of a
confident wrong one.

## What is true today

Verified from source, 2026-08-24:

- **Works:** local Apple-Silicon inference (mflux image, Kokoro TTS, optional GGUF
  LLM) and one AWS spot GPU running real LTX video, launched by a bash script.
- **Probe:** solid on Mac (Apple + Intel) and NVIDIA-Linux; VRAM-blind on AMD/ROCm;
  no Vulkan.
- **Registry:** 17 models / 25 variants / 7 runtimes. Sizes are API-real; most
  memory figures are `estimated`; speeds are mostly `declared`. Two models carry
  `measured` numbers, on one machine (M1 Max 32GB).
- **No fleet.** No Tailscale, no cross-machine dispatch, no multi-substrate
  orchestration.
- **Live mocks that lie:** `skypilot_orchestrator.py` (fake IPs, fabricated
  failover), `model_recommender.py` (mock catalog and downloader), the
  `spacepilot/engines/*` video engines (render a test pattern, tag it success).
  These must be deleted or gated before v1.1.

## What v1.1 is

Not "wire N substrates" and not "build a cockpit". A **small, honest MCP toolset
over the real fleet** — for the handful of jobs the first user (MotionVector's video
agent) actually runs:

1. `probe` sees all three of our machines, including the AMD/Vulkan one.
2. `recommend` reads the real registry, not the mock catalog.
3. `dispatch_to_node` reaches another machine over Tailscale.
4. Every mock deleted or gated so no tool returns fake success.

A **default agent** rides on top so a human can use it out of the box; power users
bring their own. Substrate keys we hold: AWS (driver), Modal, RunPod (keys only,
drivers are ~100-line adapters written once).

## What this retires

- **The inference exchange** — settlement, capacity payments, spot arbitrage,
  warm-residency markets. Those are a platform's problems. An assistant advises and
  executes on a fleet you already have; it does not run a marketplace.
- **"We build the smart layer."** The smart layer is the caller's. We build the
  tools and the ground truth under them.

## The cockpit

The cockpit is not a dashboard. It is the **shared surface where the human and the
agent collaborate over WebMCP** — the human sees what the agent sees, steers, and
approves; the agent calls the same tools. Neither is pinned to one machine, because
Tailscale is *only* transport: the fleet is reachable from wherever the cockpit
runs. The cockpit survives v1.1 as this collaboration window, not as a control panel
the human drives alone.

## Caveats, in depth

A caveat is the moat because of *what kind of fact it is*: **negative information
about someone else's artifact.** "This q4 build is worse at typography" is a fact the
uploader has no reason to publish and the host has no reason to surface — it is
adversarial to their own supply. That structural disincentive is why the gap exists
and stays open. We collect the one fact the ecosystem is built not to say.

- **A caveat is a task-specific quality measurement.** Same shape as a speed
  measurement — a fact about `(variant, capability)` with `measured | inferred |
  declared` provenance. Not "flux-q4 is good" but "flux-q4 · typography · degraded"
  and "flux-q4 · photoreal · preserved". The caveat ledger and the measurement store
  are one object with two value types.
- **Two production paths — this is the cron-vs-real-code line.**
  - *Structural* caveats derive from the compression method + base model without
    running anything (distillation → word-timestamps `untrained`; aggressive quant →
    text/fine-detail `degraded` before photoreal). They generalize across models. A
    **scheduled agent** produces them: diff model cards, walk the derivative graph,
    read the method, emit *candidate* caveats — always `inferred`, never `measured`.
  - *Empirical* caveats need an `eval` run on the fleet; they catch the surprises a
    method cannot predict. **Real code**, expensive, run only on variants that
    matter. Promotion to `measured` requires this run.

  The curator proposes; the fleet confirms.
- **Consumption is three verbs:** reject a variant for a task, warn the human,
  substitute a better-preserved variant. That needs a small **capability taxonomy**
  — the finite list of tasks a caveat can be about (word-timestamps, text-rendering,
  temporal-consistency, multilingual, instruction-following…). That taxonomy is the
  schema the whole moat hangs on; write it down once.

## The default agent

Not a model we ship — the thesis forbids building reasoning. The default agent is a
bundled **configuration**: a system prompt + the SpacePilot MCP toolset + a pointer
to whatever inference the user has keys for. Model-agnostic; swap the model freely.

- **Two modes decide it.** Headless agent-to-agent (MotionVector's video agent) needs
  no default — the caller is the agent. Human-in-cockpit needs a brain behind the
  WebMCP surface, or "use SpacePilot" means "first wire up an agent" — dead on
  arrival.
- **The tools carry the correctness, so the model choice is de-risked.** Because
  `probe`, `caveat_lookup` and `verify_output` return honest ground truth, even a
  modest default model gives a correct answer — it cannot hallucinate VRAM the tool
  reports. Building tools not reasoning is what makes the caller interchangeable.
- **The system prompt is an asset.** It operationalizes the conscience: probe before
  you recommend, check caveats before you promise, verify before you report success.
  The honest-failure guard lives half in the tools and half in the agent's
  instructions to trust them over its own priors.
- **v1.1:** a BYO-key default agent (persona + tool-wiring). Running that agent *on
  the fleet* — a local model for cheap/private reasoning, escalating to a frontier
  model for hard calls — is a later recursion.
