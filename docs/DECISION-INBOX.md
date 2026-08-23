# SpacePilot decision inbox

---
status: accepted
authority: normative-process
decided_at: 2026-08-23
last_verified_at: 2026-08-23
owners: [cto, founder]
---

One unresolved decision gets one entry. Agents add evidence to the entry instead
of independently asking the same question again.

These lived on Studio's board until 2026-08-23, which meant a session reading
that board found one product's decisions in another product's canon. `~/code/AGENTS.md`
now routes product decisions to the product's own `docs/`. Competitive and market
research is the deliberate exception and stays pooled in
`motionvector/studio/docs/market/`, because splitting it per product makes it
undiscoverable.

## Open

### `caveats:` on a variant — is a capability ledger the registry's job?

- **Shipped 2026-08-23, deliberately reversible** (PR: transcription entries).
  A variant may now carry `caveats:`, a list of `{capability, status, detail}`
  with status in `preserved | degraded | untrained | absent` and `detail`
  required. It is modelled on `license.restrictions`: the same argument that
  put "SOTA but you may not ship it" in a machine-readable field applies to
  "fast, and the word timestamps were never trained".
- **The case that forced it**: distil-whisper distilled only segment-level
  output. Its word timestamps are inherited from the parent's attention heads
  with no dedicated training — right for subtitles, wrong for cutting filler
  words. Nothing in size, licence, speed or precision can say that, and to a
  reader skimming the table it is simply the smaller, faster large-v3.
  Quantised whisper.cpp builds are the opposite case and say so: whisper.cpp
  computes timestamps in its own decoder logic, so q5_1 aligns as well as f16.
- **What is open**: whether a per-variant capability ledger belongs in this
  registry at all, or whether it is the first plank of a capability matrix that
  should be its own thing. Four statuses and one sentence is the smallest
  version that is still honest; it could as easily have been a prose `notes:`
  line, which is cheaper and unqueryable.
- **Cost of reversing**: two YAML blocks, one parser function, one render block
  in `web/models.html`, one test file. No caller depends on it yet.
- **Close when**: Saurabh says keep it, drop it to prose, or grow it.

### SpacePilot public claim — timing, not direction

- **Direction is decided** (Saurabh, 2026-08-23): SpacePilot is a federated
  inference network for **any device and any modality it is capable of**, not a
  local-first tool and not a Mac-only text network. Darkbloom is therefore a
  competitor in a lane we intend to enter, not an adjacent product. Evidence:
  [darkbloom-federated-apple-silicon-2026-08-23.md](market/darkbloom-federated-apple-silicon-2026-08-23.md).
- **What is still open**: when this is said publicly. Today the repo has a
  macOS-only device probe, one `source: measured` fact in the model registry
  (Kokoro speech), no image model entry at all, and no networking, routing or
  settlement layer. Saying it before any of that exists makes it a claim rather
  than a description.
- **CTO recommendation**: state the direction internally now and hold the public
  claim until at least one device serves at least one non-text model to at least
  one other device. That is the smallest fact that makes the sentence true.
- **CPO decision needed**: whether the public site describes the destination or
  the current state, and how loudly it marks the difference.
- **Close when**: the public claim and a dated capability record agree.

### Settlement for the inference exchange

- **Reframed 2026-08-23**: this was filed as a research question about verifying
  diffusion work. Given the exchange decision below, it is not a side quest — it
  is the **settlement layer**, and no exchange has ever functioned without one.
- **The problem**: an energy market works because a kilowatt-hour is meterable and
  undisputed. Diffusion steps are not. A provider paid for 30 steps can run 8 and
  return a plausible frame; a provider paid a surge rate for warm capacity can be
  cold and claim otherwise. Both cheats pay best exactly when volume and prices
  are highest. Zero of fifteen surveyed networks can detect either.
- **CTO recommendation**: do not pursue cryptographic completeness. zkML is
  hours-to-infeasible at diffusion scale and should be budgeted as a 2028+
  capability. Build settlement as market design instead — spot-check rate times
  slashing penalty exceeding the cheat payoff — with perceptual quality scoring as
  a free first-pass filter, and, where we control the runtime, intermediate latent
  hashes signed at fixed step boundaries so attestation becomes auditable rather
  than merely present.
- **Founder decision needed**: whether settlement is designed before any third
  party is paid, or whether the first paid substrates are restricted to ones that
  carry the risk themselves (fal, Replicate, Salad) while settlement is developed.
- **Close when**: there is a written settlement design with a stated cost per
  verified job, or a written decision to defer third-party payment until there is.

### Revenue model for the exchange

- **Conflict**: the thesis states two revenue models that price differently and
  attract different supply. "Raw cost plus a small percent for orchestration" is a
  flat fee. "Dynamic pricing, priority routing, spot capacity, cross-cloud
  arbitrage" is a market maker. A flat percentage captures almost nothing during
  the surge moments where the most value is created, and — critically — it pays
  nobody to hold a model resident through a demand trough.
- **Evidence that the market model is real**: DeepSeek introduced peak/off-peak
  API pricing effective 16:00 UTC on 16 August 2026, in their own words to enable
  "more flexible workload scheduling" and allocate resources "more reasonably."
  Off-peak is half of peak. V4-Flash output moved from a flat $0.28/M to
  $1.32 peak / $0.66 off-peak. A frontier lab has priced congestion directly.
- **CTO recommendation**: the mechanism that actually makes residency happen is a
  **capacity payment** — money for standing by, paid whether or not a job lands —
  not a percentage of throughput. Model it explicitly before pricing anything.
- **Founder decision needed**: flat orchestration fee, spread, capacity payments,
  or a combination — and whether the open-core engine is priced at all.
- **Close when**: a pricing model is written down and one substrate is paid under it.

### Brand and trademark clearance for SpacePilot

- **Changed since prior state**: name availability was checked on 2026-08-23. The
  package names are free; two adjacent trademarks exist and were not previously
  recorded.
- **Facts**: `spacepilot` is available on PyPI, npm, crates.io and Hugging Face.
  `pluto` is **taken on PyPI**, so the package cannot publish under its current
  name. `github.com/spacepilot` is a dormant personal account (0 repos, last
  active 2019) and `spacepilot` on Docker Hub is taken. `spacepilot.dev` is ours
  and live. `spacepilot.com`, `.ai` and `.io` are registered by others — `.ai` and
  `.io` serve an aerospace guidance/navigation/control site.
- **The consideration**: **3Dconnexion has sold a SpacePilot 3D mouse since the
  2000s**, including the SpacePilot PRO. That is a long-standing mark in computing
  peripherals used by CAD and DCC software — adjacent to creative tooling, though
  a different class of goods from a distributed inference runtime.
- **CTO recommendation**: park the free names now, before the name appears in any
  public artifact; squatting follows announcements. Treat the 3Dconnexion mark as
  a question for counsel rather than for an agent — thirty minutes of advice is
  cheap against a rebrand after adoption.
- **Founder decision needed**: proceed on SpacePilot, or clear it first.
- **Close when**: names are parked and the trademark question has an answer.

## Decided 2026-08-23

- **SpacePilot is a federated inference network for any device and any modality**
  (founder decision, Saurabh). Not local-first, not Mac-only, not text-only. Any
  device joins a provider community and serves whatever inference it is capable
  of. This supersedes the earlier framing of SpacePilot as a tool for running
  models on your own machine; the local path becomes one case of the general one.
  Consequence: the device probe and the model/runtime registries are the routing
  substrate for the network, not just an onboarding nicety — a registry that says
  "device X runs model Y at speed Z" is the routing table. Their macOS-only scope
  is now a gap rather than a scope choice. Open timing question above.

- **We do not copy Darkbloom's implementation** (founder decision, Saurabh). The
  techniques in question are published — MLPerf's system/result separation,
  continuous batching, paged KV, Apple's own attestation APIs — and none of it is
  closed tribal knowledge. We build our own with the fleet. This closes the reuse
  boundary question: reading their source to understand the problem space stays
  fine and useful; no pattern reaches our code by transcription, so their licence
  clause and provisional patent draft stop being live constraints on our roadmap.

- **SpacePilot is an exchange, not a router** (founder decision, Saurabh). The
  scarce good is not compute — compute is abundant across local machines, friends'
  machines, community fleets and clouds. The scarce good is **warm residency**: a
  node already holding the right weights. A 20GB+ diffusion model costs 20-50
  seconds to load cold, so the cheapest substrate is frequently not the cheapest
  answer. Cost-only routing, which is what every orchestrator including SkyPilot
  does, therefore routes wrong.

  The consequence is that the scheduler scores
  `price + (cold ? load_seconds x value_of_latency : 0)` rather than price, and
  `load_seconds` per model per substrate is a **measured** quantity — which is why
  the measurement store is the routing table rather than a marketing asset.

  The economic consequence is larger: warmth cannot be manufactured, only paid
  for. Interactive demand pays a surge rate for zero cold start; batch work fills
  troughs and, in doing so, funds residency. This makes idle capacity liquid,
  which is a different business from reselling it. DeepSeek's peak/off-peak launch
  on 16 August 2026 is the same mechanism shipped by a frontier lab. Open
  questions on revenue model and settlement are filed above.

- **The engine is renamed from Pluto to SpacePilot, and the package is renamed
  with it** (founder decision, Saurabh). Pluto was an internal name for a worker
  API that ran LTX-2.5 on an AWS spot GPU; the scope it now carries is unrelated.
  `pluto` is additionally taken on PyPI and can never publish. The distribution
  name becomes `spacepilot`. The repository name is a separate question and is not
  decided here.

- **The onboarding fork is a multi-select, not an either/or** (CTO decision,
  ratified in discussion). "Local or cloud" contradicts the product: the first
  real user already runs local Macs, a local 5090, RunPod and Modal as one fleet.
  Setup assembles a fleet from local, cloud and borrowed substrates; after setup,
  which substrate ran a job is an implementation detail. Cloud additionally
  carries three gates local does not: credentials held outside argv and dotfiles,
  a quota reality check (the G-family Spot quota is 8 vCPU, exactly one
  g6e.2xlarge, so an account can look like a cloud and be one box), and a hard
  budget ceiling with idle shutdown on by default.

