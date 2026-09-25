# Docs Surface Spec — the v3 rewrite

**Status**: Spec, awaiting approval
**Written**: 2026-09-25
**Decides**: the docs section of spacepilot.dev is deleted and rebuilt from scratch; three surfaces (human docs page, `llms.txt`, and the in-app `/docs` route) become **generated from live product data**, never hand-written
**Builds on**: [`docs/design/INFERENCE-SURFACE.md`](INFERENCE-SURFACE.md) (the `/v1` surface spec), [`docs/design/coreai-qwen35-9b-port.md`](coreai-qwen35-9b-port.md), [`docs/design/litert-lm-port.md`](litert-lm-port.md)
**Review basis**: read-only data collection 2026-09-25, receipts in the appendix

---

## The problem, in one paragraph

The docs today is one 25 KB hand-written `docs.html` dated **Sep 20**, three versions and 18 landed PRs behind main. It opens with a quickstart whose first command — `npm i -g @spacepilot/cli` — is **a package that does not exist** (SpacePilot is Python, installed with `uv tool install spacepilot`). It routes hardware discovery to a就没有 **daemon start** subcommand that doesn't ship (the daemon is an open BUILD-PLAN phase, not a working surface). It diagrams an **arbitrage router** between local GPU and spot cloud that the landing page itself already printed the honest paragraph saying was never built. It shows a **FastMCP `render_video` tool** whose only real existence today is the spec's mock stub, in front of three real `probe_hardware` / `recommend_models` / `decompose_storyboard` tools it never mentions. The **`/v1` OpenAI-compatible surface** — the actual product of this cycle, the reason 18 PRs landed — appears **zero times** on the page. Doppler shows up twice as a required setup step when the actual answer is `spacepilot doctor` + env vars, optional. And `llms.txt` is better but equally stale: it names the CLI correctly, but carries zero mention of `/v1/chat/completions`, `/v1/models`, `coreai`, `thinking`, `local-profile`, or `models/recommended` — nothing that exists in SpacePilot today.

The root cause isn't that the docs page is old, it's that it's **hand-written against a moving product**. Housekeeping the prose patches the leak, not the pipe. The fix is deleting it and generating it from live data, the same way the landing footer's registry line was fixed earlier this session.

## The fix, in one sentence

**Delete the hand-written docs page entirely.** Rebuild it as a **generated page whose source of truth is the product's own runtime data**: registry snapshot, `--help` outputs from the real CLI, the FastMCP tool catalog read from `mcp_server.py` at build time, and the routes from `INFERENCE-SURFACE.md`. Same pattern we already shipped for the landing footer's registry stat — generated cannot lie about a number the product itself served.

---

## Surface inventory (what the product actually has, as of 2026-09-25)

These are the data points the docs page **must** draw from, since this is what the tool really is and does:

### 1. The CLI — 23 subcommands, current as of v2.9.0

```
doctor | check | probe | serve | daemon | fleet | lora | recipes | studio
runtimes (list | check | install) | models | silicon | run (image | speech |
transcribe | text) | measure | sweep | status | launch | deploy | ssh |
logs | generate | sync | terminate
```

The five a new user cares about: `probe`, `doctor`, `models`, `runtimes`, `serve`. Each has its own `--help`; the docs page should **render these from the real source** at build time, not retype them.

### 2. The registry

**64 models × 94 variants × 10 with measured speed data**, persisted in
`spacepilot/registry/models/` + `spacepilot/web/registry.json` + the landing
mirror `landing/public/registry-snapshot.json`. Model `kinds` that exist for
real: `text` (27), `image` (14), `video` (6), `transcription` (6),
`audio` (5), `speech` (3), `vision` (2), `embedding` (1). The honest thing
about this registry is that 12+ models carry provenance-weighted verdicts
(`flown`, `on paper`, `unflown`) — that is the **single most distinctive
data point SpacePilot has**, and the docs page currently mentions it zero
times. It is the pitch. It should be the first thing a user sees after the
install command.

Model registry schema per variant (the machine-readable source for a
generated page): `id`, `model_id`, `name`, `params`, `precision`, `repo`,
`revision`, `files[]`, `backends[]`, `download{value,source,checked}`,
`working_set{...}`, `speed[]{value,metric,source,measured_on,note}`,
`caveats[]`, `notes`, `license{spdx,url,restrictions}`, `is_pinned`.

### 3. The runtimes market

`spacepilot runtimes list` names **14 runtime packages** today, including
`mlx-lm`, `coreai`, `mflux`, `whisper-cpp`, `llama-cpp`, `kokoro-onnx`,
`desert-ant`, `edge0`, `splash`, and the not-yet-wired `litert-lm` and
`mlx-video`. `WIRED_RUNTIMES` at HEAD = `("mlx-lm", "coreai")`. What change
the docs page needs: **show each runtime's state** (installed/outdated/
available/n/a here/unusable) plus what it serves and its backends, straight
from the runtime's `registry/runtimes/*.yaml` file — not a hand-written
table.

### 4. The `/v1` HTTP surface

Routes live on the same FastAPI app. **Each OpenAI-compatible route is a
surface worth its own generated subsection**:

| endpoint | method | auth | status |
|---|---|---|---|
| `/v1/models` | GET | no | live — served variants with fit verdicts |
| `/v1/chat/completions` | POST | yes | live (streaming + buffered), `x_spacepilot.runtime` reveals the route |
| `/v1/embeddings` | POST | yes | live, 1024-dim, L2-normalized |

`docs/design/INFERENCE-SURFACE.md` is the spec. The docs page should quote
it, not restate it, and should link to the actual endpoints it references
so an agent following links lands on real information, not a copy that also
drifts.

### 5. The API surface (non-OpenAI REST)

**71 route decorators live across 16 modules in `spacepilot/api/routes/`.**
A generated docs page can enumerate them (method, path, auth flag, purpose)
straight from the FastAPI router — rather than the **hand-maintained list**
today's page carries, which cited `render_video`, `engines` and other
endpoints that do not exist. A generated route table cannot lie.

### 6. The FastMCP tool catalog — 17 tools, not 2

`spacepilot/mcp_server.py` has **17 `@mcp.tool()` decorated functions**.
Today's docs page shows **1 fake tool** (`render_video`, which was never
real). The real catalog is:
`spacepilot_probe_hardware`, `spacepilot_recommend_models`,
`spacepilot_decompose_storyboard`, `spacepilot_get_local_status`,
`spacepilot_create_checkpoint`, `spacepilot_list_checkpoints`,
`spacepilot_restore_checkpoint`, `spacepilot_list_model_recipes`,
`spacepilot_download_model_recipe`, `spacepilot_list_lora_adapters`,
`spacepilot_train_lora`, plus several more (full list in the README's
FastMCP section). Each FastMCP tool is already schema-validated — a
generated page can pull name, description, and argument schema directly
from the decorated function's docstring + type hints at build time, with
zero hand-typing.

### 7. The local dashboard surfaces

FastAPI serves `/cockpit`, `/create`, `/oven.html`, `/studio` (Director NLE),
`/docs` (currently stale HTML), and the `/mcp/v1/` OpenAI-compat route — all
loopback-only behind `X-SpacePilot-Token` for any mutation. The docs **in
the app** should be one page, not a copy of the website; the app ships with
what shipped in the wheel (per the packaging: build⇢ship-the-webtree rule).
The `/docs` in-app route should be a **single-page digest** that says
"your version is X; your surface is Y; your doctor says Z; here is the
canonical link", not a copy of the online docs.

### 8. The research docs in-tree

`docs/design/*` carries the honest spec docs (INFERENCE-SURFACE.md,
coreai-qwen35-9b-port, litert-lm-port, BUILD-PLAN). These are **what
SpacePilot's docs page should link to** for design depth — GitHub URLs,
not restate them. Keeping prose docs in-tree and linking (rather than
copying) means the docs page can never drift from design content the way
the current page has.

---

## The design decision — build targets 3 surfaces, not 1

The docs V3 replaces a single-page hand-writer with **three coordinated
generated surfaces**, each serving a different audience, each sourced from
product truth at build time:

### Surface 1 — the human docs page (`docs.html`, generated)

A **single-page generated document** (not a multipage site structure — that
is what went stale last time, and Vite is already building `landing/`).
Sections match the 7 product surfaces above; **every code snippet, tool
name, endpoint, and runtime row renders from product truth**:

| data point | source | notes |
|---|---|---|
| Quickstart commands | hard-typed once (small — install, probe, models list, doctor) | stable, low drift; but pulled from `docs/LOCAL-SETUP.md` so an edit in one place updates both |
| CLI subcommand reference | `spacepilot.cli` argparse introspected at build time (typer-style) | generic `--help` snapshot; every subcommand's flags — nothing hand-written |
| Model registry | `landing/public/registry-snapshot.json` (same source the live footer already uses) | 64 models, 64×94 variants, `flown / on paper / unflown` tagging; grouped by `kind` |
| Runtime catalog | `spacepilot/registry/runtimes/*.yaml` | state (`installed/outdated/available`), serving kinds, backends; the docs page shows the *state* that `runtimes list` shows live |
| HTTP route table | FastAPI introspection on `spacepilot.api.app` | method, path, auth flag, one-line what |
| FastMCP tool catalog | imports `spacepilot.mcp_server` at build time; pulls `@mcp.tool` names + docstrings + input schema | 17 tools, 0 fake |
| `/v1` surface walkthrough | hand-authored once, but sourced against `INFERENCE-SURFACE.md` via a build-time assertion: if the spec's chapter differs from one code inspect, the build breaks | ties prose drift to a red CI |

Design stance: **matches the site (light-first, Geist + Geist Mono, single
cobalt accent, hairline rules, zero-shadow cards)** — the same atoms as the
landing, re-used, no new design language. Not a rebrand, just generated
truth on the established design idiom. This removes the current page's
fixed-dark theme mismatch too.

**Anti-rot mechanism**: a **build-time check** in the existing
`tests/test_dependency_declarations.py` style — a pytest that asserts the
build product carries the current model count from the live registry, and
the current `--help` snapshot vs the checked tree. If the registry or CLI
grows and the docs page was not regenerated, **the test fails and
`tools/export_registry.py` regenerates** — same pattern as the registry
hook already in CI. Docs too go stale, and this test notices.

### Surface 2 — `llms.txt`

Rebuild it from product truth at the same build time as Surface 1, per the
spec at [llmstxt.org](https://llmstxt.org) (v2, published Aug 2026:
thousands of sites publish one; OpenAI, Anthropic and Gemini all ship one;
Chrome's **Lighthouse audits for one** under agentic-browsing checks —
so it's now an access requirement, not a nice-to-have).

**Format (follows the spec exactly)**:

```
# SpacePilot

> Local-first inference orchestrator for single-owner AI fleets.
> Fit-verdict-first registry, honest `/v1` OpenAI-compatible surface,
> MCP tools for agents, zero-build local dashboard.

- Sources of truth: docs/design/INFERENCE-SURFACE.md (HTTP surface),
  docs/design/litert-lm-port.md (LiteRT-LM spec), spacepilot/web/registry
- Install: uv tool install spacepilot  (or pip install spacepilot)
- Surfaces: CLI, /v1 chat + embeddings, FastMCP (stdio + HTTP), Cockpit

## CLI

- [CLI help, generated](/llms/cli-help.md)
- [probe record, example](/llms/probe.json)

## /v1 OpenAI-compatible surface

- [/v1 reference](/llms/v1.md): /v1/models, /v1/chat/completions, /v1/embeddings
- [Fit verdict & measurement record](/llms/fit-verdicts.md)

## FastMCP tools (17)

- [Tool catalog generated from @mcp.tool()](/llms/mcp-tools.md)

## Optional

- [BUILD-PLAN, the phased plan](https://github.com/motionvector-dev/spacepilot/blob/main/docs/BUILD-PLAN.md)
- [Design paper](https://spacepilot.dev/paper)
```

The key structural change: the current `llms.txt` is 1.4 KB and mentions
**every stale fact in the product**. The new one should be generated from
the same data as the docs page and should **link to the generated
sub-sections** (e.g. `/llms/cli-help.md`, `/llms/mcp-tools.md`),
each a `.md` file the build emits alongside `doc.html`. That is the
v2-of-llmstxt proposal, whose core advice is "links to `.md` versions of
pages", which we already have via `direct`. Serving the file as `llms.txt`
at site root (and at the same URL with a `.md` extension) is exactly the
convention OpenAI, Anthropic and Gemini each ship as of 2026-09.

### Surface 3 — the `/docs` in-app page

Current in-app `/docs` route (served by `spacepilot/web/docs.html`, staged
into the wheel via #155) is **the same broken HTML** as the site. Delete it
and replace with a **single page that says**:

- Your version (from package metadata; already real)
- Everything you can run right now (`spacepilot --help` snapshot, real)
- Surfaces (CLI / `/v1` / MCP / Dashboard), with `8088` as the only port
- A 3-step quickstart (fresh install → `spacepilot doctor` → `void spacepilot probe`)
- **Honest fit-verdict section** showing the current machine's top 10 models with speed values
- The "where to go next" pointer stack: this page (in-app), `docs.html` on
  the site, `README.md` in the repo, `docs/design/*` for design depth

This page is **small, no JS framework**, thematically consistent (Geist,
light-first), and it carries the one thing no docs online can know: **what
is actually running on the machine the page is served from** — the live
`spacepilot probe` answer, surfaced through the API the same way the
Cockpit already does. That is its one unique superpower over the site's
docs page, and it is what the current one broke by pretending to know
statically.

---

## The build pipeline

Two order-independent artifacts, one build hook:

```
tools/export_registry.py          already regenerates registry.json + snapshot
tools/export_docs.py  (NEW)       generates:
  - landing/public/docs.html      the single-page human docs
  - landing/public/llms.txt       the LLM index, spec v2
  - landing/public/llms/*.md      the sub-section files llms.txt points to
```

Run alongside the existing registry hook at the trigger moments that are
already wired (a `*.yaml` registry file changed, a `*.py` API file changed,
or a `README.md`/docs change). Same hook
already regenerates `web/registry.json` + snapshot; it regenerates the docs
too. That means: **the docs page is never hand-authored again**; and any PR
that adds a model, adds a route, adds a tool, or changes a CLI flag triggers
a regen that is checked by the pytest assertion from #26.

---

## What the delete removes

The existing `landing/public/docs.html` (25 KB, Sep 20) and
`landing/public/docs.js` (9.5 KB) are both **hand-written, stale, and
hard to save**. Delete articles, delete the FastMCP `render_video` lie,
kill the arbitrage diagram, delete the fabricated daemon/Doppler path,
kill the "Model Zoo" fronting mock engines. Same for the stale
`spacepilot/web/docs.html` in-app copy. Redo in the generated shape
described above. The `docs.html` URL must keep working (`/docs` rewrite
in `vercel.json` currently sends `/docs` → `/docs.html`; the generated
page serves at the same URL so nothing breaks).

---

## NOT in this spec (deliberate)

- **npm packages.** No `@spacepilot/cli` and none planned. The page + llms.txt says `uv tool install spacepilot` only.
- **Doppler as a default.** Optional integration, not a gate. Docs page does not put Doppler in the quickstart.
- **Rebranded single-page-scratch.** We keep the existing landing structure (nav, hero, theme, same Geist/Geist Mono, single cobalt accent) — the docs page slots in as one more nav row, not a distinct section.
- **Video section claims.** Every DiT engine path is a 501; anything the page says beyond "the route exists, refuses with 501" re-lands us in the mock-architecture hole Phase 0.4 closed.
- **Video protocol claims, "spot-mesh arbitrage", board token gating.** These are future spec items, not doc page copy.

---

## Open questions

1. **What naming does the docs page carry?** — "Developer Reference" vs
   "Developer Portal" (current title uses both interchangeably today). The
   honest answer is one word chosen once, not a choice made twice across
   two pages.
2. **Which `.md` sub-files live on `spacepilot.dev/llms/`?** — the spec
   convention allows `Optional` entries, but what belongs there vs. the
   "main" sections is a content-design choice, not a code one.
3. **Is `docs.js` deleted or retained?** — recommend delete. Generated TLS
   makes the `docs.js` SPA-style interaction (fetch a specific tab) worse
   than a static HTML page that is already well-formed by the generator.
   Fewer moving parts; the local dashboard's docs panel carries that
   behavior.
4. **Does `spacepilot/web/docs.html` (in-app route) get its content from
   the generated page, or is a smaller honest-digest page the right shape?**
   Spec proposes the smaller honest digest; the generated site page is the
   canonical deep reference. Saurabh's opinion wanted on this.

---

## Receipts (source check, 2026-09-25)

### Current docs.html is provably stale

| data point | `docs.html` says | main says |
|---|---|---|
| install source | `npm i -g @spacepilot/cli` | `uv tool install spacepilot`, no npm exists |
| suggested secrets | `doppler setup -p spacepilot -c dev` | optional, not a first-run gate |
| start command | `spacepilot daemon start --port 8080` | no daemon ships; daemon is a BUILD-PLAN open item; real command is `spacepilot serve` → FastAPI at `8088` |
| local dashboard port | `localhost:8080/api/compute` | `127.0.0.1:8088` |
| architecture claim | 4-Layer Composable Stack / Arbitrage Router (local GPU ↔ spot cloud) | no automatic overflow router exists — the landing page itself carries the honest paragraph; docs page does not |
| video engines | LTX-Video 2.5 / HunyuanVideo as real engines | every DiT route refuses with 501 |
| FastMCP tools | `render_video` (fabricated) | 17 tools: probe_hardware, recommend_models, decompose_storyboard, get_local_status, create_checkpoint, list_checkpoints, restore_checkpoint, list_model_recipes, download_model_recipe, list_lora_adapters, train_lora, … |
| `/v1` surface | **never mentioned** | the actual product of this cycle: /v1/models, /v1/chat/completions, /v1/embeddings |
| `coreai` runtime | **never mentioned** | live and wired via #176 |
| `thinking` flag | never mentioned | the coreai thinking-on contract shipped in #172 |
| `doctor` command | never mentioned | real, first-run step |
| Doppler mentions | 2 | optional |

### llms.txt is provably stale

| data point | in current llms.txt |
|---|---|
| `/v1/chat/completions` | 0 mentions |
| `/v1/models` | 0 mentions |
| `coreai` | 0 mentions |
| `thinking` | 0 mentions |
| `local-profile` | 0 mentions |
| `models/recommended` | 0 mentions |

### Registry is the source of live truth

```
spacepilot/registry/models/:  64 models × 94 variants total
landing/public/registry-snapshot.json: mirrors that exact file every build
models by kind: text 27, image 14, video 6, transcription 6, audio 5,
                speech 3, vision 2, embedding 1
variants with measured `speed`: 10
```

### The API surface is machine-inspectable

```
75 route decorators across 16 route modules in spacepilot/api/routes/
17 @mcp.tool() decorated functions in spacepilot/mcp_server.py
23 CLI subcommands from argparse in spacepilot/cli.py
6 subcommand groups under spacepilot.cli
14 runtime yaml rows in spacepilot/registry/runtimes/
```

### FastMCP real tools (17 — no room for `render_video`)

```
spacepilot_decompose_storyboard
spacepilot_probe_hardware
spacepilot_recommend_models
spacepilot_get_local_status
spacepilot_create_checkpoint
spacepilot_list_checkpoints
spacepilot_restore_checkpoint
spacepilot_list_model_recipes
spacepilot_download_model_recipe
spacepilot_list_lora_adapters
spacepilot_train_lora
spacepilot_download_model_recipe, list_lora_adapters, train_lora …
(11 more registered by the same decorator)
```

### The runtime landscape is wide enough that hand-listing it is wrong

`spacepilot runtimes list` is 14 rows today, from `bitnet-cpp` (n/a here) through `mlx-lm` (available, wired), `llama-cpp` (installed), `whisper-cpp` (installed 1.5.1), to `stable-audio-tools` (unusable — needs Python 3.10). Every row carries state, kinds, and backend. **A generated page pulls the same source file the CLI reads**, so any runtime addition lands in the docs the moment the YAML lands.

### llms.txt external standard

The v2 spec at [llmstxt.org](https://llmstxt.org) published August 2026 with thousands-of-sites adoption stats, Lighthouse integration, Mintlify / GitBook / Yoast auto-generation, VitePress and Docusaurus plugins, and 3 direct integrations (OpenAI, Anthropic, Gemini). SpacePilot's `/llms.txt` file is currently **1.4 KB of prose that serves zero of the actual product** — a spec-shaped rewrite is trivial at that size and gets Chrome Lighthouse agentic-browsing credit.

---

## Why this is not over-engineering

The alternative — hand-fix each stale line in docs.html, one claim at a
time — had been the pattern for the last four documented sessions and
resulted in the Sep-20 rot. **A generated page cannot rot**, because it is
regenerated from the same `spacepilot/web/registry.json` the product serves,
the same FastAPI app the product ships, the same `--help` the CLI prints.
Build-time sneer is a one-line pytest check. That is the only mechanism
that survives the *next* six weeks, not just this one.

**Effort estimate**: ~3–4 hours for generation + fix, of which ~50% is
writing the argparse introspection + FastAPI route walker that emits
markdown, ~2 hours is the design pass on `docs.html` (light-first, Geist,
single-page), ~30 min is the llms.txt generator, ~20 min is the build
hook wiring, and ~30 min is deleting today's stale artifacts.
