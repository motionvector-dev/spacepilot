# Concept — SpacePilot

**Revision 3 · 2026-08-24 · supersedes revision 2 (2026-08-24, commit `313a21f`)**

Revision 1 optimized for internal coherence. Revision 2 cut the vocabulary to
five words but still told the story in the past tense — freight, harbors,
grids. Revision 3 was born in a divergence session (ten frames, a kill round)
and stands on what survived: three frames, several verified facts, and a name
that turned out to be more literal than we were treating it. What died is in
§13.

---

## 1. The name is the thesis

**There has never been a space pilot.** Not one. Astronauts do not pilot in
any meaningful sense — Buran landed unmanned in 1988, Dragon docks itself,
every burn is computed into a window. Orbital mechanics are the canonical
space human intuition cannot fly: speed up to fall behind, burn backwards to
catch up. When the profession finally exists, it will be a human supervising
trajectories no hand could fly.

**The first space pilots will be software.** That is not a metaphor for this
product; it is a description of it. The compute universe — prices moving in
two lanes, spot boxes evaporating, warm states shifting across a fleet,
quotas and export borders redrawn by the quarter — is a high-dimensional
space with dynamics as counterintuitive as orbital mechanics. You do not
hand-fly a transfer window. You will not hand-schedule a fleet.

And "space" carries its second reading for free: to anyone who has touched
ML, a *space* is a state space, a latent space — territory you navigate with
math because intuition fails there. SpacePilot is the pilot of a space. Both
readings are true. Neither needs explaining to the audience that installs
Python packages.

This is the brand's tense: **future, claimed early.** The name is a job
title from a profession that does not exist yet. Historical frames — freight,
pilotage, merit-order — are ballast for credibility, used sparingly in docs.
The masthead makes the bet.

---

## 2. Three frames

Everything on every surface traces back to one of these.

### 2a. Already aboard — what the pilot is

The pilot installs on every machine and runs headlessly everywhere at once.
Cargo sits in one place. A ship is one place. The human is in one place.
**The pilot is the only entity in the universe that is in more than one place
at once** — and a pilot that had to be somewhere would just be another
program.

Consequences:

- **You don't open SpacePilot. It's already aboard.** Installing it on a new
  machine is the pilot boarding that ship — a better arrival moment than any
  download.
- **Three doors, one pilot.** Human → Cockpit. Agent → MCP. Nobody →
  autopilot, still flying. Same pilot, same facts. This is the architectural
  version of "personas are views": the doors differ, the pilot cannot.
- **One ceremony: granting the conn.** Copilot → autopilot is a human handing
  over control of things that bill money. It is the single place ritual is
  honest, and it gets the craft we once wasted on downloads.
- **Asleep, not lost.** Verified against both hemispheres' tooling: no
  scheduler — not exo, not Petals, not BOINC's descendants, nothing Chinese
  or American — treats a sleeping laptop as a distinguished state. exo stalls
  the whole ring and tells users to run `caffeinate`. Everyone else treats
  sleep as death. The pilot stays aboard a sleeping ship: queue the cargo,
  wake the ship, resume. This is provenance-grade honesty applied to
  liveness, it is an empty niche, and it is ours to name.

### 2b. The picture — what the pilot holds

One state. Every terminal — the laptop, a web shell into a droplet, a RunPod
pod, the Cockpit in a browser — is a **window onto the picture, never the
picture itself**. It does not matter which console you sit at; the picture is
the picture.

Consequences:

- **Design the scope, not the dashboard.** A dashboard is a room of gauges
  about one machine. The scope is one state-dense, glanceable rendering of
  the whole fleet, identical wherever it appears. This is the standing answer
  to "why has the UI gotten complicated": we were building headquarters when
  the product is a window.
- **Git, not Docker.** Docker manages state per-daemon; `docker context`
  points at one remote at a time; there is no merged truth. Git has merged
  truth — one repository, every checkout a view. That is the lineage.
- **Three kinds of state, three mechanisms** (verified shape, SkyPilot-grade
  precedent): the **logbook merges** (append-only facts — measurements,
  manifests — union is truth), the **orders have one author** (desired
  config, single-writer), the **picture is observed** (warm state and
  liveness are perishable — never stored, always fresh, always timestamped).
  Forcing all three through one mechanism is where distributed systems go to
  die; our shape — one owner, small fleet, already on a tailnet — is the easy
  case if we respect the split.
- **The moat is the picture, not the manifest.** Anyone can reproduce a
  measurement by running the model once. Nobody else can hold the live
  picture of *your* fleet — which ship is warm, which is asleep, what the
  next job should do about it. Situational awareness is the asset; the
  logbook is its memory.

### 2c. The bet — where this is going

The RSI-era inversion: intelligence becomes abundant; the scarce, contested
thing is where it runs and what the run costs. Weights are already freight.
The verified 2026 universe, in four words: **free cargo, bordered territory.**
Qwen and DeepSeek weights fly on Mac Minis in both hemispheres while H100s
cross borders in suitcases and export rules flip by the quarter.

The inversion is the *second* beat on every surface, never the first. Lead
with what the pilot does; let the worldview land underneath it. (Revision 2
led with the worldview and read like a compute exchange. §13.)

---

## 3. The goal

A stranger lands on spacepilot.dev, learns two things in ten seconds — what
the tool does, and that the name is a bet — and runs the install command.

The plain sentence, which every surface must be able to say and revision 2
forgot to write down: **SpacePilot sends every job to whichever of your
machines is already holding the model warm — and rents only when you'd want
it to.**

---

## 4. Four words, one reserved

The metaphor budget. Everything else, on every surface, is plain measured
English.

| word | means |
| --- | --- |
| **ship** | a machine you own. The laptop, the 5090 box, the Air. |
| **dock** | compute you rent. A spot instance. The meter runs. |
| **cargo** | models. Weights are freight; you carry what fits. |
| **flown** | measured. We ran it on this ship and logged the number. |
| *fuel* | **reserved.** What a run costs. Enters the lexicon the day a scheduler surface exists to say it, and not before. A word no surface uses is a lie about the product. |

Derived forms are free: **unflown**, **flight check**, **pilot / autopilot**,
**aboard** (only of the pilot: *the pilot is aboard* — never of models),
**stowed** (cargo arrival). "On paper" is plain English: someone else's
published number, cited and dated.

Everything else stays literal. Disk is disk, downloading is downloading,
loading is loading. The moment a screen needs a legend, the screen has
failed.

**Open flaw, carried honestly:** `dock` does double duty. A spot instance you
stock with cargo and a provider API that comes pre-stocked behave nothing
alike — the second has no fits/unflown axis at all. Rule until resolved:
*docks you stock* are docks; provider endpoints are named plainly
("providers") until a better word earns its place. Do not force it.

---

## 5. One register

Working space, not exploration — owner-operators, manifests, meters, blue-
collar space, never federation grandeur. One register everywhere: landing and
Cockpit differ in motion frequency and density, never in vocabulary.

The cast is three: **you** (captain, owner-operator — you own the ships, you
authorize the spend), **the pilot** (everywhere at once; copilot by default,
autopilot by granted conn), **cargo** (not characters, not collected;
carried). Galaxies, planets, stars: scenery — story-layer art and prose only,
never a noun in the UI.

---

## 6. Provenance is the design language

Unchanged in substance from revision 2; the pilotage principle now names its
foundation: **local knowledge is a different kind of knowledge, and it cannot
be shipped in from outside.** Every serious harbor on earth makes pilotage
mandatory because knowing *these waters* beats general seamanship. An H100
benchmark is general seamanship. `4.6× realtime on this M1 Max, measured
Tuesday` is knowing where the sandbar is. Harbors do not accept résumés.

The mechanics stand:

```
                  measured HERE       measured ELSEWHERE
  we ran it     │  flown           │   —
  they claim it │  —               │   on paper
  nobody ran it │  unflown         │   unflown
```

- `on paper` and `unflown` stack rather than compete.
- `unflown` is a state of the airframe, not a judgement of the data.
- Per-ship, one-way door: `unflown ──first run──▸ flown · 4.6× · date`.
  Once, per model, per ship, irreversible. `CARGO 1 flown · 7 unflown` is the
  only progress meter the product needs, always computed, never written in.
- Two streams, never merged: `solo` and `loaded` differ by ~40%; the stream
  name rides on the number.
- A `flown` number survives a ship change but names its hardware fingerprint;
  it never silently demotes to `on paper`.
- Cargo that cannot fly stays a wall, not an invitation: an em dash, not a
  state.

Verdicts remain a separate axis (`fits` plain · `fits, tight` platinum ·
`won't fit` rose · `not supported` faintest), stacking with provenance, never
merging. Platinum is a metal, not a hue.

---

## 7. Liveness is provenance's twin

Revision 3's structural addition. The same honesty that governs numbers
governs presence:

| state | means | treatment |
| --- | --- | --- |
| `warm` | model in memory, answers now | the prize. Plain ink, stated with its ship |
| `cold` | on disk, loads on demand | plain, with the measured load time when flown |
| `asleep` | ship is sleeping. **Not lost.** | its own state, never rendered like failure |
| `gone` | spot reclaimed, node vanished | said plainly, with the timestamp |

`asleep` is the differentiator: queue the cargo, wake the ship, resume — and
say so. Every peer tool renders a sleeping MacBook the way it renders a dead
one. The pilot knows the difference because the pilot is still aboard.

The picture's staleness is itself data: every liveness fact carries its age.
A fresh "asleep" is honest; a stale "warm" is a lie wearing green.

---

## 8. Ships and docks

Unchanged from revision 2. Ships keep the OS name (`Saurabh's MacBook Pro`),
never invite naming; beneath sits the hardware fingerprint that keys every
measurement. Docks never get a friendly name — instance ID, region, rate,
running clock (`g6e.2xlarge · us-east-1 · i-0a3f7c21 · $0.75/hr · 00:41:12`).
The asymmetry is the honest signal. Every list is plural and keyed by ship
even at n=1; design the list that happens to have one row.

---

## 9. Three thresholds, one ceremony

Motion is rationed by frequency. Three thresholds earn craft, each crossed
once: **first boarding** (the probe — the ship reads itself, fields it could
not read included), **cargo arrival** (`kokoro-82m is stowed.`), **first
flight** (`unflown` flips to a measured number with the ship's name on it).

Above them sits the one ceremony: **granting the conn.** Autopilot touches
money; the moment of authorization is designed like the signing of something,
because it is. Everything daily gets nothing; numbers never tick.

---

## 10. The economics, verified

Facts the design leans on, checked live 2026-08:

- **The price lanes split.** Committed compute rose hard through 2026
  (1-yr H100 contracts $1.70 → $2.35/hr Oct–Mar, SemiAnalysis; AWS Capacity
  Blocks +38% in six months). Opportunistic compute stayed flat
  ($2.79–2.83/hr composite since Jul 2025). **Commitment is getting
  expensive; opportunism stays cheap. A scheduler is an opportunism
  machine.** The spread between lanes — and between your $0 warm ship and
  any lane at all — is what the pilot eats. Abundance does not close it.
- **The niche is empty in both hemispheres.** Borg, MAST, Singularity,
  SkyPilot, Dynamo, llm-d, Gödel, AIBrix, Volcano — every scheduler surveyed
  assumes nodes reliably present. None treats a closed lid as scheduling
  state. Small market is the stated reason, not prior solution.
- **The pilot layer trends open on both sides of the Pacific** — NVIDIA
  open-sources schedulers to sell silicon; China opens infra (DeepSeek's
  filesystem week, Huawei's CANN) to catch up on CUDA. Different motives,
  same direction. The proprietary layer is always the *fleet*, never the
  pilot. An open SpacePilot runs with the grain of the industry.
- **The quota stays loud.** Ceiling rendered from the quota, never
  hard-coded: `Ceiling is 1 dock, by quota.` Renting is a decision, not a
  default.

---

## 11. The wedge, and the doors

Unchanged in substance: `pip install spacepilot`, no account, no API key, no
config; `spacepilot check` is the first screen and teaches the four words in
one pass; `doctor` aliases it. Personas change how many facts you see, never
which facts are true; persona is inferred from the door, never asked;
surfaces are named by function. The agent surface is the schema; humans are
views over it.

---

## 12. The ten-second sequence

The landing page's order of operations, fixed:

1. **The plain sentence** (§3) — what it does, in measured English.
2. **The picture** — the live proof: the fleet, the warm ship chosen, the
   sleeping ship honest, the meter at $0.00.
3. **The bet** — the name explained in two lines: *There has never been a
   space pilot. The first one is software.*
4. The install pill.

Worldview never leads. Revision 2's hero led with "Intelligence is cargo.
Compute is territory" and read like a compute exchange; the inversion now
arrives third, where it lands as depth instead of confusion.

---

## 13. What died, and when

**Rev 1 (2026-08-23):** models as planets, capture, galaxy-as-collection,
persona modes, machine naming, animated counters. Still dead.

**Rev 2 (2026-08-24, morning):** crew/berth/aboard-for-models/off-ship, the
two-register split, "flown here". Still dead.

**Rev 3 (2026-08-24, the kill round):**

- **The worldview headline.** "Intelligence is cargo. Compute is territory"
  demoted from first beat to third. It claimed a war the product doesn't
  fight and failed the ten-second test in the direction of grandeur.
- **The container/intermodal frame** — borrowed glory; we adapt to formats,
  we don't set them. One line survives in escrow for the day conversion
  ships: "any cargo, any ship, untouched by hand."
- **The home-grid frame as identity** — electrons are fungible, inference
  isn't; it hid the compatibility half of the product. Survives only as a
  teaching device for the score function.
- **Proprioception as a frame** — nobody installs a nervous system. Its
  jewel survives at the center of §7: *asleep, not lost.*
- **`fuel` as an active word** — demoted to reserved (§4). Vocabulary must
  trail the product, never lead it.
- **The manifest-as-moat claim** — the moat is the live picture; the
  manifest is its memory.
- **Past-tense ballast as spine** — Nostromo, McLean, merit order move from
  masthead to footnotes. The name faces forward; the doc now does too.

---

## 14. Still open

- **The dock/provider split** (§4). Carried as a named flaw; resolve when the
  provider surface is designed, not before.
- **The freight-chart hero** predates the kill round — it leads with the
  worldview and shows no sleeping ship. Rebuild against §12's sequence when
  UI work resumes.
- **Wake mechanics.** "Queue and wake" needs a technical answer per ship
  class (wake-on-LAN for the Lenovo, launch-on-demand for docks, waiting
  honestly for a lid). The concept commits to the honesty, not to magic.
- **Sparse density; fleet UI at n>1 in daily use.** Unchanged.
- **The story-layer scenery budget.** Unchanged; resolve by building.
