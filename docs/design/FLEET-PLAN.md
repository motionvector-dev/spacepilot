# SpacePilot — Fleet Plan: From Single-Machine Core to Fleet

**Status**: plan (2026-08-27). Grounded in code as of main `35be2cc` and PR #78
(`codex/mlx-llm-runtime`). The design commitments come from the design paper
(§3) and `docs/design/CONCEPT.md`; this doc is the execution bridge — what
exists, what is missing, and the order to build it.

**Revalidated 2026-09-02** against main `01027f4`, as part of the merge train
that landed this doc. `spacepilot/pluto/*` paths below are fixed to their
current location (`spacepilot/*` — the package was flattened in #101; the
line numbers otherwise still match). More substantively, `spacepilot/daemon/`
moved further than this plan assumed:

- **W6 (LOG gossip) is now substantially built.** `spacepilot/daemon/log.py`
  ships signed records, signed pages, and `LogStore.records_since(epoch,
  sequence)` — pull-since-a-cursor plus union-merge-on-ingest, matching this
  workstream's shape. Re-verify the "no CRDT, converges order-free" property
  with a test before calling it done, but the code is there.
- **W5 (liveness/sleep) is further along than "gap".** `daemon/fleet.py`
  already carries the full `ready/busy/asleep/gone` state machine with aging
  (`FleetMember`, `FleetRowFacts`). What's still missing, confirmed by grep,
  is the scheduler side: no `plan()` path renders "queued — asleep, checked
  Ns ago" yet. Keep "Partly built."
- **W0, W1, W3 are still open**, re-confirmed against current main: no
  `timeout=` reaches `driver.infer()` in `spacepilot/services/text_execution.py:133`;
  no `on_paper.py` module exists anywhere in the tree; `spacepilot/mcp_server.py`
  carries 17 tools (not 16 — recounted 2026-09-02), still none named `plan`
  or `execute`.
- **W4 (substrate parity)**: `tests/test_daemon_phase4.py` exercises both
  `DirectLocal` and `DaemonClient` against `spacepilot/substrate.py`, but no
  single parametrized fixture-identity test was found by grep. Unconfirmed
  either way without reading that file closely — don't assume built.

**Scope**: everything between the running single-machine core and the
multi-machine fleet the paper describes. Not in scope: new models, new
runtimes, multi-tenant fleets.

---

## 1. Where the code actually stands

Verified by reading main and the PR #78 worktree, not from memory.

| Paper commitment | Code today | Verdict |
|---|---|---|
| Provenance typing (flown / on paper / unflown) | `spacepilot/services/provenance.py:20-47` — `FactProvenance` with the three states and the rendering rule | **Built** |
| Caveat taxonomy | `spacepilot/model_registry.py:80-104` — `CAVEAT_STATUSES` (preserved/degraded/untrained/absent), `CAVEAT_PROVENANCES` (measured/inferred/declared); `Caveat` dataclass at :164 | **Built** |
| Measurement corpus (LOG) | `spacepilot/measurements.py` — `Measurement` dataclass with revision/knobs/contention/status, `record()`, YAML on disk per system/model | **Built** |
| Resolver | `paths.py` `resolve()` — content-addressed cache, offline | **Built** |
| Substrate (DaemonClient ≡ DirectLocal) | `substrate.py` — wire-shaped dicts, no-retry-on-lost-response | **Built** |
| Daemon, UDS + tailnet peers, Ed25519 | `daemon/server.py` (479 lines), `daemon/peer_auth.py` (338), `daemon/fleet.py` (506) | **Built** |
| Liveness (ready/busy/asleep/gone, aged) | `daemon/fleet.py` — `FleetMember`, ages; sleep states in the paper's shape | **Partly built** |
| Agent surface over MCP | `spacepilot/mcp_server.py` — 17 tools, all probe/download/checkpoint; **no plan, no execute** | **Gap** |
| Consent gate for agents | CLI has `--yes`/TTY refusal; MCP has nothing | **Gap** |
| Cold-start evidence (fresh fleet) | No importer for public corpora | **Gap** |

Two defects found while verifying:

1. **No wall-clock bound on `infer()`** — `spacepilot/services/text_execution.py:133`
   calls `driver.infer(...)` with no `timeout`; the driver default is `None`.
   Token count and KV are bounded; time is not. A stalled 15 GB load into swap
   hangs the CLI forever. The driver already raises on `TimeoutExpired` — the
   bound is simply never armed.
2. **Non-TTY confirmation asymmetry** — `_confirm_run` refuses non-TTY without
   `--yes` (correct), but the MCP surface has no equivalent gate at all.

## 2. The system, one picture

```
                    ┌─────────────────── above the waist ───────────────────┐
                    │  weights hubs · formats · quantizations · model cards │
                    └───────────────────────────┬──────────────────────────┘
                                                │  registry: repo+revision+files
                                                ▼
        ┌──────────────────────────── THE WAIST ────────────────────────────┐
        │                                                                  │
        │   probe ──▶ rank ──▶ gate ──▶ execute ──▶ write back              │
        │   (what     (fits/   (Y/n,     (child      (Measurement           │
        │    this      tight/   proven-   process,   with revision,          │
        │    machine   won't    ance     offline,   contention, tps)         │
        │    has)      fit)     shown)   bounded)                           │
        │        ▲                                              │           │
        │        └──────────── every run a measurement ─────────┘           │
        └──────────────────────────┬───────────────────────────────────────┘
                                   │
              ┌────────────────────┼──────────────────────┐
              ▼                    ▼                      ▼
        this machine          owned peers            rent / APIs
        (DirectLocal)         (daemon + tailnet)     (a dock, a provider)
              │                    │
              └──── Substrate ─────┘     one protocol, two transports
                                         parity test is the contract

   fleet state, three classes, three rules:

   LOG       append-only YAML · every machine · union-merge · never mutates
   ORDERS    one signed fleet.yaml · one author · versioned overwrite
   PICTURE   liveness/load/warmth · in memory only · every field aged
             (a test walks the data dir to prove no picture reaches disk)
```

## 3. Workstreams

Ordered. Each one is small, testable, and lands on its own branch.

### W0 — Arm the timeout (defect fix, do first)

- `text_execution.py:133`: pass `timeout=600` into `driver.infer()`.
- Test: assert the service forwards a timeout (fake driver records kwargs).
- Watch the test fail against the current code before fixing it.

### W1 — Pipette import as on-paper evidence (kills the cold-start gap)

A fresh fleet has zero flown records; the ranked table is all dashes. Import
public benchmark corpora as dated, cited *on paper* rows.

- New module `spacepilot/services/on_paper.py`: load a Pipette export, map each row
  to a registry variant (model × quant × runtime), emit `FactProvenance`
  records with source URL and date.
- Never blend: imported rows render `on paper (pipette, 2026-08-21)`, never as
  flown numbers, even after a local run confirms them — confirmation writes a
  *separate* flown record.
- Ingestion path today: Pipette's dataset is published results + coverage pages
  (pipette.liquid.ai), clients Apache-2.0 on GitHub (Liquid4All). Start with a
  checked-in snapshot file, not live scraping; the date is part of the evidence.
- Test: an imported row cannot raise a candidate's rank above a flown row.

### W2 — Render provenance and caveats in the run table

- The `run` table shows the typed provenance of every speed cell: flown with
  sample count, on paper with date, or the word *unflown*. Never a bare number.
- Any degraded caveat on the selected variant prints above the confirm prompt.
- Test: a degraded caveat in the registry surfaces in `text_run_confirmation_lines`.

### W3 — MCP plan/execute with the consent gate (the agent surface)

The paper's §3.7 promise: same properties, agent-facing. Two tools:

```
plan(workload)  → { plan_hash, facts: ranked table, provenance, caveats, bounds }
execute(plan_hash, consent=true) → receipt (wall, load, tps, peak mem, revision)
        refuses when: consent ≠ true · plan_hash stale · no safe route
```

- `plan_hash` = SHA-256 of the canonical plan JSON. Binds the consent to the
  exact plan, not to "some plan".
- This is the non-TTY rule restated for agents: nobody executes without an
  explicit yes against a specific plan.
- Tests: refuse without consent; refuse on stale hash; both watched failing.

### W4 — Substrate parity test as a standing gate

- A parametrized test runs identical fixtures through `DirectLocal` and
  `DaemonClient` and asserts identical wire dicts. It already has a home in
  `substrate.py`'s design; make it a test that CI runs.
- The property it protects: `spacepilot check` works with no daemon, no
  config, no network — and lies to nobody when a daemon exists.

### W5 — Liveness and sleep in the scheduler

- Fleet-aware `plan()` ranks asleep machines honestly: "queued — asleep,
  checked 40s ago", never silent reroute, never a fake ready.
- Wake is attempted where the mechanism exists; the interface says which.
- Tests: an asleep member renders queued-not-rerouted; a gone member raises
  to the owner.

### W6 — Gossip for the LOG

- Peers pull measurement records since a timestamp; union-merge converges any
  subset. No CRDT, no consensus — the class forbids it.
- Test: two directories of measurement YAML union into one corpus, order-free.

### W7 — Fleet end-to-end

- Two real machines, one workload, one ranked table across both. The paper's
  §6 evaluation: sleep/wake cycles under real workloads, measured.
- This is where the design stops being *on paper* and starts being flown —
  including for the paper itself.

## 4. Sequencing

```
W0 ─▶ W1 ─▶ W2 ─▶ W3 ─▶ W4 ─▶ W5 ─▶ W6 ─▶ W7
 │      │      │     │
 │      │      │     └─ agent surface needs provenance + caveats rendered
 │      │      └─ rendering needs evidence to render (flown + on paper)
 │      └─ evidence import needs bounded runs to be safe to compare against
 └─ every later workstream records measurements through this path
```

W0–W2 are single-machine and land independently of the fleet. W3 is the
hinge: it makes the product agent-native. W4–W7 are the fleet, in dependency
order.

## 5. Test strategy

- Every new check is watched failing before it is trusted (repo rule).
- Parity, consent-refusal, no-picture-on-disk, and no-blending are property
  tests — they run on every PR, not once.
- The full suite stays green: ~731 passed on PR #78's branch is the floor.

## 6. Risks

1. **Pipette moves** — dataset shape may change under an active platform.
   Mitigation: checked-in snapshots with dates; import is a cache, not a dependency.
2. **Consent-gate ergonomics** — too strict and agents route around the tool;
   too loose and the trust story dies. The plan-hash binding is the middle.
3. **Adjacent competition** — Liquid's LocalCowork and the MacPaw partnership
   are climbing toward placement from the model side. The differentiator here
   is private fleet state × public evidence at decision time; speed matters.
4. **Paper inconsistencies** — eleven systems surveyed in the paper, nineteen
   in the report; citations are placeholders. Fix before the paper circulates.

## 7. What this plan deliberately does not do

No new runtimes, no model splitting, no multi-owner trust, no serving-layer
work (Dynamo/llm-d own that). The waist stays narrow.
