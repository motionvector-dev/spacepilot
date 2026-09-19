# SpacePilot — Vision

Running AI should be easy. Free, when your own machine can do the job. When it
can't, renting one — RunPod, Modal, an API provider — should be just as fast
and just as simple. SpacePilot makes that call for you: it watches what your
machines can do right now, tracks the AI world as it changes, and picks where a
workload runs — a machine you own, one you rent by the hour, or an API you pay
per call. Local when possible, rented when useful, always your call on money.
This is a grand vision and we don't build it on day one. We start small.
(Saurabh, 2026-09-02; `docs/design/CONCEPT.md`)

## The three surfaces

| surface | repo | license and money |
| --- | --- | --- |
| CLI + MCP server | this repo | open source |
| web cockpit, Tauri wrapper later | this repo | open source |
| macbar (SpaceBar menu bar app) | its own repo, to be created | free by default, paid tier later if the value earns $5/month |
| spacepilot.dev | `../spacepilot-landing` | site |

(`AGENTS.md`)

## Where it is today

One surface, every modality: text and chat, embeddings, speech and
transcription, image, upscaling, music, and video (`docs/design/CONCEPT.md`
already names ships/docks/providers as modality-agnostic — this is that
thesis applied). Text and embeddings are the newest routes on it, added
2026-09-02 because AgentWorth and SpaceBar need them. Nothing is demoted;
each modality's state is stated honestly below.

- **Text** — works. `spacepilot run text` generates through MLX-LM from a pinned Qwen snapshot, bounded and one-shot (`spacepilot/services/text_execution.py`, `spacepilot/drivers/mlx_lm_driver.py`); a GGUF route sits beside it (`spacepilot/drivers/gguf_driver.py`). Also `POST /v1/chat/completions`.
- **Embeddings** — works, added in this PR: same MLX route, `POST /v1/embeddings`, same fit verdict and measurement record (`docs/design/INFERENCE-SURFACE.md`).
- **Image** — works, on Apple Silicon through mflux, in its own conda env.
- **Speech and transcription** — works, through the API. (`README.md`, "What works today")
- **Video** — mock. Every render today is an ffmpeg test pattern, not a model (`README.md`, "What does not"). The engines and routes are plumbing for the day a real render lands, not a claim that anything generates video now.
- The CLI does real work here: `spacepilot probe`, `spacepilot models`, `spacepilot run image/speech/transcribe/text` (`spacepilot/cli.py`).
- A FastMCP tool server gives agents the same actions. (`spacepilot/mcp_server.py`)
- The web UI has four zero-build surfaces: `/create`, `/cockpit`, `/studio`, `/oven.html`. (`README.md`, architecture diagram)
- Every endpoint that spends compute or money needs a token — `require_token`, checked by `test_compute_endpoints_all_require_the_token`. Read-only routes stay open. (`AGENTS.md`, Conventions)

### Dock workloads

A dock is a rented machine — RunPod, Modal, a GPU by the hour — one of the
three places any modality's workload can run (`docs/design/CONCEPT.md`).
Heavy work runs where it fits, local or rented; that's a placement decision
per job, not a statement about which modality matters. Video today runs
nowhere for real, so its engines and routes are plumbing for the day a dock
runs them end to end.

## Where it goes next

The moat is not the server. Ollama and LM Studio already serve a port, and
serving a port is a solved problem. What nobody does is tell you what fits
before the download and what it did after: the registry that pins which
weights, at which revision, under which licence; the fit verdict that grades a
model against your machine, not a spec sheet; the measurement corpus that
records what ran, how fast, on a busy box or an idle one; and honest placement
across ships and docks, so "rent one" arrives with a price attached. Coding
models are where that pays first — a developer runs them all day, cares what
they cost, and can tell a good answer from a slow one.

Agents take over from the CLI. Chat becomes how a human talks to SpacePilot,
with the cockpit alongside showing the data. Not ChatGPT for local AI — that,
plus observability for your fleet, local and remote. Datadog for your machines,
not just a chat box. (Saurabh, 2026-09-02)

macbar's headline feature is duplex voice — you talk, it talks back, either
of you can interrupt. It runs locally when it can, on a ladder:

1. **On device** — Apple's on-device foundation model, about 3B parameters by Apple's own report, through FoundationModels. (machinelearning.apple.com/research/apple-foundation-models-tech-report-2025)
2. **Still local, bigger** — CoreAI/CoreML for open models like Qwen when the on-device model isn't enough. Apple's Private Cloud Compute server model comes through the same framework; Apple publishes no parameter count for it and waives the cloud cost only for App Store Small Business Program developers. (developer.apple.com/apple-intelligence/, developer.apple.com/private-cloud-compute/)
3. **Off the machine** — a rented box or an API provider, when the machine cannot do it at all.

(Saurabh, 2026-09-02; `docs/design/macos-coreai-provider-backend-runtime.md`;
`docs/design/macos-app-intents-apple-intelligence-integration.md`)

**The unlock for free Apple silicon models is two doors, and MCP fits both.**
Door one, the app calls the model: FoundationModels lets the app register
`Tool`s the model can call, and an MCP bridge sits there as one. Door two, the
model calls the app: App Intents lets Siri, Shortcuts and Spotlight understand
a request and act on macbar, with no model call and no cost to us. On a Mac
door two is the bigger one — Siri is the voice surface the user already has.
(developer.apple.com/apple-intelligence/,
developer.apple.com/videos/play/wwdc2025/286/;
`docs/design/macos-app-intents-apple-intelligence-integration.md`)

The web cockpit gets the same idea through MCP and WebMCP, so a browser agent
can operate it without reading pixels. WebMCP is a community-group draft, not a
standard: Chrome runs an origin trial from Chrome 149, Edge has one, Firefox
and Safari do not ship it. PR #23 serves the trial token, `web/onboard.html`
carries the first hooks, `motionvector-dev/webmcp-demo` is the working proof.
(github.com/webmachinelearning/webmcp, developer.chrome.com/docs/ai/webmcp)

The paper's registry work — evidence lattice, execution graph, readiness-aware
planner — is what makes this possible: knowing what is ready before asking.
(`../spacepilot-landing/paper/spacepilot-paper.pdf`, Sections 3.1–3.4)
Distributed inference across owned Macs over Thunderbolt 5 is a further-out
design, not a shipped feature.
(`docs/design/macos-distributed-inference-and-training-with-mlx.md`)

## What stays free, what may be paid

- CLI and MCP server: open source, always. Web cockpit and its later Tauri
  wrapper too. (`AGENTS.md`)
- macbar: free by default. A paid tier comes later, only if the value is worth
  $5 a month to a Mac user in the West. (Saurabh, 2026-09-02)
- Compute is never free by fiat. Renting a box or calling an API costs real
  money, shown before you spend it, never a silent default.
  (`docs/design/CONCEPT.md`, "Money is loud")

## Pointers

- `docs/design/CONCEPT.md` — the product thesis: ships, docks, providers, honesty rules.
- `docs/design/INFERENCE-SURFACE.md` — the `/v1` routes, the fit verdict, embeddings.
- `docs/design/RUNTIME-CAPSULES.md` — how a local runtime is built, verified, trusted.
- `docs/design/HARDWARE-LANDSCAPE.md` — what's changing in AI hardware.
- `docs/design/macos-coreai-provider-backend-runtime.md` — the `coreai` provider design.
- `docs/design/macos-app-intents-apple-intelligence-integration.md` — Siri, Shortcuts, Spotlight.
- `docs/design/macos-distributed-inference-and-training-with-mlx.md` — Thunderbolt 5 clustering.
- `../spacepilot-landing/paper/spacepilot-paper.pdf` — SpacePilot V2, the execution graph (Saurabh Nandwana, Aug 2026).
- Apple's Core AI reference checkouts: `coreai-models`, `coreai-optimization`, `coreai-torch` (export recipes, compression, the PyTorch bridge).
