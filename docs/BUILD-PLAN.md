# SpacePilot — Build Plan

**Status:** proposed · **Written:** 2026-08-25 · **Verified against:** main `e4b7910`
(after PRs #66/#67/#68) · **Audit:** 12 read-only agents, every claim below carries
file:line evidence · **Supersedes:** the SpacePilot Build Board artifact
(2026-08-23, now stale on ~10 items — see Appendix B).

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
`spacepilot/pluto/registry.py:115`) or actively fabricating success (the legacy
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

The seven MCP tools deleted in #67/#68 were symptoms. The disease is still
mounted on the app and served to first-run users.

**0.1 Delete or gate the fake video engines.** `spacepilot/engines/{ltx,wan,hunyuan}_engine.py`
render an ffmpeg `testsrc` colour-bar pattern and return `status: "completed"`
with fabricated inference parameters (ltx_engine.py:88-118 calls
`_render_mock_video()` unconditionally; the `mock: bool` arg is never branched
on). `/api/generate/multi-engine` (mounted at pluto/app.py:84) serves this as a
real job. Same failure class as the deleted MCP tools, worse because it writes a
playable file. **Do:** unmount the route → 501, gate the engines behind
NotImplementedError, keep code commented for archaeology. Acceptance: route
returns 501; `test_compute_endpoints_all_require_the_token` still passes;
grep shows no reachable `_render_mock_video`. ~60k tokens.

**0.2 `/api/generate` mock fallback marks but doesn't refuse.** generate.py:280-329
`_mock_gen` sets `is_mock: True` (line 284) — which nothing reads (grep: one
write, zero reads) — then `status: "completed"`. UI shows a completed clip.
**Do:** no GPU → job status `"failed"` with a reason, never a testsrc render.
~30k tokens.

**0.3 Retire the legacy AWS CLI half or make it honest.** Verbs
`status/launch/deploy/ssh/logs/generate/sync/terminate` all return `None` (exit
0 always). Two fabricate: `status` renders any AWS error as "No active GPU
instance found" exit 0 (cli.py:232-257 catches everything → None) — a credential
failure is indistinguishable from an empty account on the verb the docs call the
free way to check a billing box; `sync` prints "Sync complete!" regardless of
rsync's exit. `status` also prints a hardcoded "78 GB model into VRAM (~170s)"
(cli.py:322) on a 48 GB-VRAM instance, and a hardcoded $0.75 rate (cli.py:55).
**Decision needed (Saurabh):** these verbs become the *docks* surface in Phase 4,
so the choice is (a) fix exit codes + error surfacing now and rebuild later, or
(b) gate them 501-style now and rebuild once. Recommend (b): smaller, and the
verbs are unusable today anyway (the AWS profile they need doesn't resolve).
~50k tokens for (b), ~150k for (a).

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
`.pluto_config.json` from a read command (cli.py:604-651) — make the write
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

The formula already written down (registry.py:115, citing a deleted doc — see
5.2): `score = price + (cold ? load_seconds × value_of_latency : 0)`.
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
  PIPELINE-STATE,DECISION-INBOX}.md (archived at ~/code/motionvector/handoffs/)
  but AGENTS.md:66-73 still tells every agent to read them, and registry.py:116
  cites DECISION-INBOX as the scheduler-formula source. Point both at what
  exists. ~25k tokens.
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
- **React frontend fate.** PR #14: 75 files, 104 commits behind main, 6 related
  open PRs (#14 #16 #23 #24 #27 #28). Rebase-or-close is a product call.
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
| Truth (P0) | 0.1–0.5 | ~275k |
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
- Local checkout rename pluto→spacepilot: **done** (~/code/CLAUDE.md still
  says otherwise; external references in .mvec-local also stale).
- React frontend: 75 files (not 78), 104 commits behind (not 70), 6 PRs.
- `~/Downloads/ltx-out` (the board's cited source for real LTX renders):
  **does not exist on this machine**; whether those runs survive anywhere is
  unknown.
- LoRA panel / fine-tuning panel: removed by deletion; backend 501s correctly.
