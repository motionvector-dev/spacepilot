# SpacePilot — Vision

Running AI should be easy. Free, when your own machine can do the job.
When it can't, renting one — RunPod, Modal, an API provider — should be just
as fast and just as simple, no fuss. SpacePilot is the layer that makes that
call for you. It watches what your machines can actually do right now, tracks
the AI world as it changes, and picks the best way to run a workload: on a
machine you own, one you rent by the hour, or an API you pay per call. Local
when possible, rented or managed when useful, always your call on money. This
is a grand vision, and we don't build the whole thing on day one. We start
small. (Saurabh, 2026-09-02; `docs/design/CONCEPT.md`)

## The three surfaces

| surface | repo | license and money |
| --- | --- | --- |
| CLI + MCP server | this repo | open source |
| web cockpit, Tauri wrapper later | this repo | open source |
| macbar (SpaceBar menu bar app) | its own repo, to be created | free by default, paid tier later if the value earns $5/month |
| spacepilot.dev | `../spacepilot-landing` | site |

(`AGENTS.md`)

## Where it is today

- The CLI does real work on this machine: `spacepilot probe`, `spacepilot models`, `spacepilot run image/speech/transcribe/text` (`spacepilot/cli.py`).
- Image generation runs today on Apple Silicon through mflux, in its own conda env. Speech and transcription run through the API. (`README.md`, "What works today")
- Video does not run yet. The engines and routes exist, but every render is a mocked ffmpeg test pattern, not a real model. (`README.md`, "What does not")
- A FastMCP tool server exposes the same actions to agents, not just humans at a terminal. (`spacepilot/pluto_mcp_server.py`)
- The web UI already has four zero-build surfaces: `/create`, `/cockpit`, `/studio`, `/oven.html`. (`README.md`, architecture diagram)
- Every endpoint that spends compute or money requires a token — `require_token`, checked by `test_compute_endpoints_all_require_the_token`. Read-only routes stay open. (`AGENTS.md`, Conventions)

## Where it goes next

Agents take over from the CLI. Chat becomes the way a human talks to
SpacePilot, with the cockpit sitting alongside showing the data. Not ChatGPT
for local AI — that, plus observability for your fleet, local and remote.
Datadog for your machines, not just a chat box. (Saurabh, 2026-09-02)

macbar's headline feature is duplex voice, OpenAI-voice style — you talk,
it talks back, either of you can interrupt. It runs locally when it can, on
a ladder:

1. **On device** — Apple's on-device foundation model, about 3B parameters by Apple's own report, through the FoundationModels framework. (machinelearning.apple.com/research/apple-foundation-models-tech-report-2025)
2. **Still local, bigger** — CoreAI/CoreML for open models like Qwen when the on-device model isn't enough. Apple's server model in Private Cloud Compute is reachable through the same framework; Apple publishes no parameter count for it, and waives the cloud cost only for App Store Small Business Program developers. (developer.apple.com/apple-intelligence/, developer.apple.com/private-cloud-compute/)
3. **Off the machine** — a rented box or an API provider, when the machine can't do it at all.

(Saurabh, 2026-09-02; `docs/design/macos-coreai-provider-backend-runtime.md`;
`docs/design/macos-app-intents-apple-intelligence-integration.md`)

**The unlock for free Apple silicon models is two doors, and MCP fits both.**
Door one, the app calls the model: the FoundationModels framework gives
"direct access to Apple Foundation Models, on device and in Private Cloud
Compute," and lets the app register `Tool`s the model can call; an MCP bridge
sits there, as one such Tool. Door two, the model calls the app: App Intents
"connects your app to Apple Intelligence and Siri AI through schemas,
recognizable structures built on years of language model training," so Siri,
Shortcuts and Spotlight understand a request in natural language and act on
macbar with no model call and no cost to us. For a voice app on a Mac, door
two is the bigger one, because Siri is the voice surface the user already
has. The four intents in the App Intents spec are door two; the voice engine
ladder above is door one. (developer.apple.com/apple-intelligence/,
developer.apple.com/videos/play/wwdc2025/286/;
`docs/design/macos-app-intents-apple-intelligence-integration.md`)

The web cockpit gets the same idea through MCP and WebMCP, so a browser agent
can operate the cockpit without reading pixels. WebMCP is a Web Machine
Learning Community Group draft, not a standard yet; Chrome runs an origin trial
from Chrome 149, Edge has one too, Firefox and Safari do not ship it. PR #23
serves the trial token; `web/onboard.html` carries the first hooks;
`motionvector-dev/webmcp-demo` is the working proof.
(github.com/webmachinelearning/webmcp, developer.chrome.com/docs/ai/webmcp)

The paper's registry work — the evidence lattice, the execution graph, the
readiness-aware planner — is what makes step 1 possible: knowing what's
actually ready on this machine before asking it to do anything.
(`../spacepilot-landing/paper/spacepilot-paper.pdf`, Sections 3.1–3.4)

Distributed inference across owned machines — several Macs over Thunderbolt 5
— is a further-out design, not a shipped feature.
(`docs/design/macos-distributed-inference-and-training-with-mlx.md`)

## What stays free, what may be paid

- CLI and MCP server: open source, always. (`AGENTS.md`)
- Web cockpit, and its Tauri wrapper later: open source. (`AGENTS.md`)
- macbar: free by default. A paid tier comes later, only for problems solved
  or value delivered that's big enough a Mac user in the West won't mind
  spending $5 a month. (Saurabh, 2026-09-02)
- Compute itself is never free by fiat. Renting a box or calling an API costs
  real money, shown before you spend it, never a silent default.
  (`docs/design/CONCEPT.md`, "Money is loud")

## Pointers

- `docs/design/CONCEPT.md` — the product thesis: ships, docks, providers, the honesty rules.
- `docs/design/RUNTIME-CAPSULES.md` — how a local runtime gets built, verified, and trusted.
- `docs/design/HARDWARE-LANDSCAPE.md` — what's changing in AI hardware and why the scheduler has to care.
- `docs/design/macos-coreai-provider-backend-runtime.md` — the `coreai` execution provider design.
- `docs/design/macos-app-intents-apple-intelligence-integration.md` — Siri, Shortcuts, Spotlight, Apple Intelligence.
- `docs/design/macos-distributed-inference-and-training-with-mlx.md` — Thunderbolt 5 clustering across owned Macs.
- `../spacepilot-landing/paper/spacepilot-paper.pdf` — SpacePilot V2, the full research case for the execution graph (Saurabh Nandwana, Aug 2026).
- `../space-voice` — a cheap Gemini-Live prototype of the duplex-voice idea. Review it; rebuild from scratch if it fights the plan. (`AGENTS.md`)
- `~/code/unfoundbox/ml-ai/coreai-models`, `coreai-optimization`, `coreai-torch` — Apple's own Core AI checkouts: export recipes, compression, and the PyTorch-to-Core-AI bridge.
