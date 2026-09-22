# SpacePilot — Build Plan

**Status:** proposed · **Written:** 2026-08-25 · **Verified against:** main `e4b7910`
(after PRs #66/#67/#68) · **Audit:** 12 read-only agents, every claim below carries
file:line evidence · **Supersedes:** the SpacePilot Build Board artifact
(2026-08-23, now stale on ~10 items — see Appendix B).

**Revalidated 2026-09-02** against main `01027f4`, as part of the merge train that
landed this doc. Two things changed underneath it since it was written:

1. **`spacepilot/pluto` was flattened to `spacepilot/`** (#101). Every `pluto/`
   path below is fixed in place to its current location.
2. **Text and embeddings routes added**: `/v1/chat/completions` and
   `/v1/embeddings` landed 2026-09-02, on the same surface as image, speech,
   transcription, and (mock) video (`docs/design/VISION.md`,
   `docs/design/CONCEPT.md`) — needed by AgentWorth and SpaceBar, not a
   demotion of anything else. Video engines remain mock until a real render
   lands; that's an honesty rule, not a priority call, and it doesn't change
   regardless of which modality this quarter's work touches. **PR #111 merged
   2026-09-02**, landing an
   OpenAI-compatible `/v1` surface with fit verdicts (`docs/design/INFERENCE-SURFACE.md`)
   ahead of this plan's Phase 2 — read that doc and the shipped surface
   before starting 2.1-2.3; some of Phase 2 may already be done or need
   re-scoping to extend rather than duplicate it.

**Spot-check against current main, not a re-run of the 12-agent audit:** Phase
0.1-0.3 are done (marked below, with the commit that closed each). Phase
0.4/0.5's cited lines were re-checked and still match current `web/*.js`
exactly. Phases 1, 3, 4, 5, 6 keep their original file:line citations from the
2026-08-25 audit — treat line numbers there as approximate and re-grep before
acting, per the doc's own "evidence expires" standard.

**How to use this doc:** it is a handoff. Each work item names its files, its
acceptance test, and a token estimate. A fresh session can pick any item and act
without re-deriving. Phases are ordered by what blocks the thesis; items inside a
phase are independent unless marked.

---

## The one-paragraph state of the product

The thesis (docs/design/CONCEPT.md) promises: give SpacePilot a workload, it
discovers feasible routes across **ships / docks / providers**, ranks them on
cost/speed/privacy, runs the best one, and every run improves the map. What
exists today: **one ship, one modality, no ranking beyond localhost.**
`spacepilot run image` works end-to-end (mflux on Metal, real measurements,
honest refusals) and is the product's quality bar. Everything else is either
absent (docks: zero code; providers: zero code; scheduler: a comment at
`spacepilot/model_registry.py:115`) or actively fabricating success (the legacy
video studio and half the cockpit). The repo's stated bar — *a surface that
fabricates success is worse than one that is absent* — is enforced in the new
half and violated wholesale in the old half.

## What is genuinely good (build on it, don't rebuild it)

| Asset | Evidence |
| --- | --- |
| `run image` plan→confirm→execute→measure loop | cli.py:1141-1187; refuses without terminal, writes no record on failure |
| Registry provenance discipline | loaders refuse bare numbers, undated claims, non-https cites (silicon.py:171-180); 42/42 variants revision-pinned |
| Measurement corpus with contention split | 8 records, 3 systems, solo/loaded marked; `load_seconds` captured (2 rows) |
| Device probe, macOS + Linux, labelled heuristics | device_probe.py (806 lines), 20 Linux tests, Vulkan llvmpipe filtered |
| Daemon + signed fleet (read-only) | Ed25519 ORDERS, Tailscale-bound peer auth, LOG gossip; `daemon status` / `fleet list` fail honestly with real exit codes |
| Honest-refusal pattern | lora train 501, model download NotImplementedError, billing 501s — all deliberate, documented |
| CI gates | packaging + pytest + security (bandit baseline), all green on Linux |

---

## Phase 0 — Stop the lying (blocks everything; nothing honest can ship on top of fabrication)

The seven MCP tools deleted in #67/#68 were symptoms. Items 0.1-0.3 below are
now **done** on main (verified 2026-09-02) — kept here as the record of what
was wrong and why, since the doc is a handoff, not a live task board. 0.4 and
0.5 are still open; both were re-checked against current `web/*` and match the
cited lines exactly.

**0.1 DONE — fake video engines gated.** `spacepilot/api/routes/engines.py`'s
`/api/generate/multi-engine` now refuses with a 501 and an explanation instead
of queuing the old ffmpeg `testsrc` mock; the old body is preserved in git
history at `e4b7910` per the route's own docstring. Originally:
`spacepilot/engines/{ltx,wan,hunyuan}_engine.py` rendered a colour-bar pattern
and returned `status: "completed"` with fabricated inference parameters — same
failure class as the deleted MCP tools, worse because it wrote a playable file.

**0.2 DONE — `/api/generate` mock fallback refuses.** `spacepilot/api/routes/generate.py`
now sets `status: "failed"` with an explicit "no video execution route" error
when no GPU worker is running, instead of the old `_mock_gen` path that wrote
`is_mock: True` (read by nothing) and reported `"completed"`.

**0.3 DONE — legacy AWS CLI verbs retired.** `status/launch/deploy/generate/sync`
now go through `_refuse_legacy_aws()` in `spacepilot/cli.py`, which exits 2 and
says plainly that renting compute returns as the docks surface (Phase 4) and
nothing was started or billed. `status`, `ssh`, `logs`, `terminate` stay live
for a box that's already running. The fix already forward-references this doc
by name (`spacepilot/cli.py`, the `_refuse_legacy_aws` docstring) — whoever
landed it was already treating BUILD-PLAN.md as the Phase 4 pointer, which is
one more reason to merge this doc rather than leave it orphaned as a PR.

**0.6 DONE (2026-09-22) — three surfaces stopped reporting state that was not
real.** All three were verified against installed v2.8.0 the same day.
- `loaded_models` listed 75-byte marker files left by the gated mock downloader
  as loaded models, while `doctor` correctly said the weights were missing —
  and the MCP tool and `GET /api/compute/local-status` answered the same
  question differently at the same instant, because each walked the cache
  itself. One builder now serves both (`spacepilot/local_status.py`);
  `loaded_models` is deprecated and always empty, and the cache is reported as
  `cached_weight_model_ids` / `stub_marker_ids`.
- Checkpoint sync is gated. It stored nothing: `create_snapshot` computed a
  genuine sha256 and copied no bytes, `restore_snapshot` reported success and
  wrote no file, and the records lived in one process's memory, so a snapshot
  survived neither a restart nor the hop between HTTP and stdio MCP. Every
  entry point now refuses; a listing carries `store` so an empty list does not
  read as "this job has no snapshots".
- Usable memory was computed and printed independently by `doctor`, `probe` and
  the two status surfaces — 25.0 GB, 24.96 GiB and 28.8 GB for one 32 GB M1 Max
  at one instant, feeding every fit verdict. One helper
  (`device_probe.usable_memory_report`), one format (GiB), and the source
  (`metal` or `heuristic`) now travels with the number on every surface. A
  process without torch cannot ask Metal and falls back to the heuristic, so
  that difference is now visible instead of silent.

**0.4 Cockpit fabrications — the first-run page lies first.** All fixes are
small; the pages themselves are Saurabh's in the design session, so **touch
logic only, never copy/layout**:
- onboarding.html:382 — GPU pill always "Spot GPU: Active" (one line: read `gpu_online`).
- onboarding.html:398-403 — renders two invented generations on *every* load
  (treats `{"assets":[]}` as an array).
- create.js:975-1039 — progress bar is five `setTimeout` phases with fake DiT
  step counts; the polling idiom already exists in the same file (:834, :1276).
- create.js:931-936 — fabricates a job id on API failure (`'mock_' + Math.random()`).
- create.js:1080-1095 — invented cost receipts ("~$0.16 — LTX-2.5", "undo
  byte-exact" — a feature that doesn't exist).
- cockpit.js:139-144 — VRAM card invents 28.4 GiB / "NVIDIA L40S" defaults.
- cockpit.js:275-303 — deploy/sync toast success without checking `res.ok`.
- cockpit.js:54-59 + sidebar.js:466 — hardcoded SPOT_RATES rendered as live quotes.
Acceptance: with the API down or empty, every page shows empty/error states,
zero invented numbers. ~120k tokens across ~6 files.

**0.5 Un-orphan the honest cockpit.** models.html, browser-probe.js,
onboard-v2.html, docs.js are well-built and linked from nothing. One nav change.
Coordinate with the design session — propose, don't merge without Saurabh seeing
it. ~15k tokens.

## Phase 1 — CLI: from honest to excellent (the CLI is the product)

**1.1 Exit codes everywhere.** Every remaining handler that `return None`s gets
a real int. Includes `doctor` (returns None even on error paths), `studio`
(cli.py:658-662 exits 0 on "no interpreter found"), `launch`'s token refusal
(cli.py:346-349, exits 0 so no script can detect it). Acceptance: a test that
walks every subcommand's handler and asserts non-None annotated return. ~80k tokens.

**1.2 `--json` that parses, on every read verb.** Today: `silicon --json` is the
only one that parses; `probe --json` emits a trailer after the JSON object
(cli.py:1836) so `| jq` fails. Give `models`, `runtimes`, `recipes`, `fleet
list`, `daemon status`, `probe` a `--json` that is *only* JSON on stdout.
Acceptance: `spacepilot <verb> --json | python -m json.tool` for each. ~90k tokens.

**1.3 Small correctness burrs.** `fleet` with no subcommand prints "Unknown
fleet action None." exit 2 (cli.py:1384) — default to `list` like its siblings.
`sweep` help names a path that doesn't exist (`registry/sweeps/`, actual:
`spacepilot/registry/sweeps/`, cli.py:1972). `studio` silently writes
`.spacepilot_config.json` from a read command (cli.py:604-651; `.pluto_config.json`
is now only the legacy fallback name, read for back-compat) — make the write
explicit or drop it. `runtimes list` says mflux "available" while `run image`
uses it from its own env — teach runtimes.py about `mflux_bin_dir`. ~60k tokens.

**1.4 `run speech` and `run transcribe`.** Kokoro (4 measurement records) and
whisper (measured) both work but are unreachable from `spacepilot run` — it has
only `image` (cli.py:1946-1952). Same plan→confirm→execute→measure shape as
`run image`. This widens the product from one modality to three with drivers
that already exist. ~150k tokens.

**1.5 First-run path in README.** No `pip install -e .` anywhere; `run image` —
the verb that produces the product's one real artifact — is documented nowhere.
~20k tokens.

## Phase 2 — Providers via a router (the missing third leg, least code first)

**GATED ON SAURABH.** Anything on the money path — provider choice, keys, live
prices, spend — happens only with him present. No agent starts P2 or P4
unattended (his words, 2026-08-25: "we can't do money path in my absence").

**PR #111 already merged** an OpenAI-compatible `/v1` surface with fit
verdicts and coding models leading (`docs/design/INFERENCE-SURFACE.md`). Read
it before starting — 2.1-2.3 below should extend that surface, not duplicate
it; check whether the provider-registry schema (2.1) already has a home
there before adding a second one.

Decision (this session, confirmed direction from Saurabh): **do not hand-build N
provider integrations — integrate a router.** Note `litellm>=1.98.0` is already
a declared dependency (pyproject.toml:33) that no shipped code imports.

> Router choice (OpenRouter / Replicate / fal.ai / LiteLLM / …) is an open
> decision for a session with Saurabh present; the market scan was deliberately
> not run unattended. The items below are shaped so the router choice is a
> parameter, not a rewrite.

**2.1 Provider registry schema.** New `spacepilot/registry/providers/*.yaml`
mirroring the silicon discipline: every price `declared` with https cite + ISO
date, never blended with flown numbers. A provider entry names: auth env var,
modalities, model-list endpoint, pricing endpoint (or `pricing: manual` with
date). The daemon's `ProviderRate` (orders.py:296, signed, Decimal, tested) is
the fleet-facing half — reuse its shape. ~80k tokens.

**2.2 One router driver.** `spacepilot/drivers/router_driver.py`: list models,
quote price, run one job, measure wall time, write a measurement record with
`substrate: provider`. Subprocess/httpx, argv-list rules, token via Doppler.
Acceptance: `spacepilot run image --via <provider>` produces a real artifact
and a real measurement row. ~200k tokens.

**2.3 Provider rows in `models` and `run` plans.** A model the router serves
appears as a candidate route with its declared price beside local routes.
Money is loud: price shown before, actual after. ~100k tokens.

## Phase 3 — Scheduler v1 (the thesis's verb)

The formula already written down (`spacepilot/model_registry.py:115`, citing a
deleted doc — see 5.2): `score = price + (cold ? load_seconds × value_of_latency : 0)`.
Today's nearest thing is `_candidate_rank` (execution.py:104): a 4-tuple sort
with no price term, no warm/cold term, no cross-machine term.

**3.1** Extend `_candidate_rank` to consume `load_seconds` from the measurement
corpus (2 rows exist; more arrive free with every run) and a price per route
(local = $0 + electricity later; provider = declared rate). Show the ranking in
the `run` plan table with provenance per number. Acceptance: a plan on this Mac
ranks warm-mflux above a hypothetical provider row when price×latency says so,
and the table says *why*. ~180k tokens. Depends on 2.1-2.3 for the price column;
the warm/cold half can land first.

## Phase 4 — Fleet dispatch, then docks

**4.1 Remote dispatch.** The daemon's peer surface is read-only: `/v1/plan` and
`/v1/run` exist locally but are not on the peer app (daemon/api.py). A fleet can
see peers but not send work to one — "SpacePilot decides how and where" has no
*where* beyond localhost. Extend peer auth (already Ed25519 + Tailscale-bound)
to authorize dispatch; measurement record lands on the executing ship and
gossips back. ~250k tokens. Depends on 3.1 (dispatch without ranking is just ssh).

**4.2 Docks.** `grep -rn dock spacepilot/` → zero matches today. Replace the
legacy hardcoded g6e.2xlarge path with a dock registry entry (rate, region,
image, quota note) + lifecycle verbs that reuse the Phase 0.3-gated surface.
Spend ceiling: the watchdog has idle-kill (watchdog.py:30) but **no dollar
budget anywhere** — add cumulative cost accounting before any dock can start.
~300k tokens. Not before 2.x/3.x land: providers are cheaper coverage per token.

## Phase 5 — Corpus and registry health (parallel-safe, low risk)

- **5.1 Stranded measurements.** 4 of 8 records key `kokoro-82m` but the
  variant id is `kokoro-82m-onnx` — invisible to export and `models list`.
  Fix the writer (`measure --model` wrote `model_id`), migrate the 4 files.
  ~40k tokens.
- **5.2 Dangling doc references.** 20bf158 deleted docs/{INFERENCE,AWS,
  PIPELINE-STATE,DECISION-INBOX}.md (archived at ~/code/motionvector/handoffs/).
  `docs/DECISION-INBOX.md` was recreated on 2026-09-02 (#108) — only AWS.md,
  INFERENCE.md, and PIPELINE-STATE.md are still archived-only. AGENTS.md's
  "Read these before asking" section still lists DECISION-INBOX.md as archived
  (stale as of this revalidation — fix in the same pass as this item), and
  `spacepilot/model_registry.py:116` still cites DECISION-INBOX as the
  scheduler-formula source, which is accurate again now that the file exists.
  ~20k tokens.
- **5.3 Cross-validate runtimes↔models.** mlx-audio claims `runs: [musicgen,
  kokoro, bark]`; musicgen/bark aren't model ids; no loader check. Add the
  check + a test. ~30k tokens.
- **5.4 Model-file `speed:` blocks vs corpus.** kokoro.yaml says 4.6 measured;
  the corpus's newest row says 4.021. Model files should derive speed from the
  corpus or cite it — measurements.py's own docstring names this failure.
  ~60k tokens.
- **5.5 solo image measurement.** All 4 FLUX.2 Klein rows are `contention:
  loaded`. One `spacepilot measure` run on an idle machine. ~5k tokens + one
  real run.

## Phase 6 — Cockpit structure (after Saurabh's design session)

Owned decisions, not build items yet:
- **React frontend fate — resolved differently than expected.** The React
  migration (formerly PR #14) landed in main via #106 (SpaceBar v1) and #107
  (cockpit v1), as the `ui/` tree. It is **not** what the app currently serves:
  `spacepilot/app.py` mounts only `web/` (`StaticFiles` on `settings.web_dir`),
  so the vanilla pages this doc's Phase 0.4/0.5 refer to
  (onboarding.html, create.js, cockpit.js, sidebar.js) are still what a real
  request hits. Whether `ui/` replaces `web/` as the served frontend, and when,
  is still Saurabh's call — flagged for the docs-freshness sweep too, since
  README.md's architecture section describes the old `web/`-only layout.
- **Marketing copy** in home/create/oven/blueprint.html (SkyPilot arbitrage,
  Polar/x402) — Saurabh is redoing these in the design session. **No agent
  touches copy.**
- **JS quality gates** (whenever the cockpit's shape settles): no package.json,
  no linter, no E2E, browser-probe test exists but never runs
  (tests/js/browser-probe.test.mjs, zero runners), XSS `esc()` guard covers
  app.js only while cockpit.js/create.js do raw innerHTML. ~120k tokens.

## Cross-cutting

- **macOS CI gap.** Metal/mflux/MLX — the only real execution — never runs in
  CI (tests.yml:42-45, hosted macOS bills 10×). Options: self-hosted runner on
  this Mac (private repo, allowed by CI budget law) or a nightly local cron.
  Decision for Saurabh.
- **Provenance rule for every new number:** flown / declared(cited, dated) /
  unflown — the loaders already enforce it; every new surface must too.
- **Negative controls:** every new guard gets watched failing before it's
  trusted (break → red → restore → green), stated in the commit message.

## Suggested order and cost

| Slice | Items | Est. tokens |
| --- | --- | --- |
| Truth (P0) | 0.4–0.5 remaining (0.1–0.3 done) | ~135k |
| CLI polish (P1) | 1.1–1.5 | ~400k |
| Providers (P2) | 2.1–2.3 | ~380k |
| Scheduler (P3) | 3.1 | ~180k |
| Corpus (P5, anytime) | 5.1–5.5 | ~160k |
| Dispatch+docks (P4) | 4.1–4.2 | ~550k |

P0 and P5 are parallel-safe today. P1 next. P2→P3 in order. P4 last. P6 waits
for the design session.

---

## Appendix A — Registry inventory (measured 2026-08-25)

19 models / 42 variants (all revision-pinned) · 9 runtimes · 12 silicon parts ·
3 systems · 8 measurements · 2 sweeps.
Modalities: image 9 models, video 5 (none run locally), transcription 2,
speech 1, text 1, vision 1. Measured speed exists for 5 of 42 variants
(kokoro ×1, whisper ×4); one measured working_set (flux2-klein-4b-4bit).

## Appendix B — Build Board corrections (board dated 2026-08-23)

- PR #40 (overnight sweep): **merged** 2026-08-23, board says open.
- "Make the export see the measurement store": **fixed**; real gap is the
  stranded `kokoro-82m` keys (item 5.1).
- Local checkout rename pluto→spacepilot: **done**, and the package itself was
  flattened from `spacepilot/pluto/` to `spacepilot/` on 2026-09-02 (#101).
  `~/code/CLAUDE.md` still points at the old `pluto` checkout path pending a
  worktree sweep noted in that file; external references in .mvec-local also
  stale.
- React frontend: 75 files (not 78), 104 commits behind (not 70), 6 PRs.
- `~/Downloads/ltx-out` (the board's cited source for real LTX renders):
  **does not exist on this machine**; whether those runs survive anywhere is
  unknown.
- LoRA panel / fine-tuning panel: removed by deletion; backend 501s correctly.
