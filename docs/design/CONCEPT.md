# Concept — SpacePilot

**Revision 2 · 2026-08-24 · supersedes revision 1 (2026-08-23, commit `df5d7de`)**

Revision 1 optimized for internal coherence and grew a ten-word lexicon across
two vocabularies. This revision optimizes for external inevitability and cuts
the vocabulary to five words. What survives is compressed here; what died is
recorded in §12 with reasons, so nobody re-derives it.

---

## 1. The thesis

Every AI company tells the story where the models are the stars. That story is
wrong about this decade.

If acceleration holds — and we build for the case where it does — intelligence
becomes abundant. Weights are already freight: large files hauled across
networks, compressed for the trip, priced by the gigabyte moved. The scarce
thing, the contested thing, is where they run and what the run costs.

**Intelligence is cargo. Compute is territory. SpacePilot is the pilot.**

The drama of the next few years is not "which model". It is routes, fuel and
dock space — a scheduler's story. The scheduler is the product:

```
score = price + (cold ? load_seconds × value_of_latency : 0)
```

That equation is fuel economy. SpacePilot exists so that when the inversion
becomes consensus, the product looks like it was built for that world rather
than pivoted into it.

---

## 2. The goal

A stranger lands on spacepilot.dev, absorbs the worldview in ten seconds
without a glossary, and runs the install command.

Every word and pixel serves that or gets cut. The test is external
inevitability, never internal coherence or completeness of metaphor. A brand
that needs a lexicon table has already lost — which is why the table below is
the whole budget.

---

## 3. Five words

The entire metaphor budget. Everything else, on every surface, is plain
measured English.

| word | means |
| --- | --- |
| **ship** | a machine you own. The laptop, the 5090 box, the Air. |
| **dock** | compute you rent. A spot instance, a provider endpoint. The meter runs. |
| **cargo** | models. Weights are freight; you carry what fits. |
| **fuel** | what a run costs. The scheduler minimizes fuel: price plus cold-start. |
| **flown** | measured. We ran it on this ship and logged the number. |

Derived forms are free and do not count against the budget: **unflown** (nobody
ran it here), **flight check** (the CLI readiness pass), **pilot / autopilot**
(SpacePilot itself; autopilot is the pilot with the conn, granted by you).
"On paper" is plain English, not lexicon: someone else's published number,
cited and dated.

Everything else stays literal. Disk space is disk space. Downloading is
downloading. Loading into VRAM is loading. The metaphor is a voice, not a
costume — and a voice never stops to explain itself. The moment a screen needs
a legend, the screen has failed.

---

## 4. One register

Working space, not exploration. The fiction this borrows from is freighter
fiction — the Nostromo was a commercial towing vehicle; Serenity hauled cargo;
the Canterbury hauled ice. Owner-operators, fuel margins, manifests, dock fees.
Blue-collar space. Never federation grandeur.

One register everywhere. Landing and Cockpit differ in motion frequency and
density, never in vocabulary. Revision 1's "two registers" split let every
vocabulary survive by giving each one a floor; that is where the convolution
came from, and it is dead.

The cast is three:

- **You.** Captain, owner-operator. You own the ships, you authorize the spend.
- **The pilot.** SpacePilot. Copilot by default; autopilot when you grant the
  conn. A description of the MCP surface, not a flourish.
- **Cargo.** The models. They are not characters. They are not collected. They
  are carried, and the good ones earn their place in the log.

Galaxies, planets, stars, providers-as-territories: **scenery.** Allowed in
prose and art direction on the story layer. Never a noun in the UI, never a
label in nav, never a name for a screen.

---

## 5. Provenance is the design language

Most numbers in this product were not measured by us on your hardware. That is
not a caveat to design around; it is the spine.

Two axes, and most tools collapse the wrong one:

```
                  measured HERE       measured ELSEWHERE
  we ran it     │  flown           │   —
  they claim it │  —               │   on paper
  nobody ran it │  unflown         │   unflown
```

LTX at 12 s/clip on an H100 is a true number that says nothing about a 24.96 GB
M1 Max. So `on paper` and `unflown` stack rather than compete:

```
ltx-2.5 · video · won't fit
12 s/clip on paper (H100 · model card, 2026-08-12) · unflown
```

**Why `unflown`, not `estimated`:** `estimated` hedges our competence,
`unverified` accuses the source, `unknown` is false (we know the claim),
`no data` is a blank with a label on it. `unflown` is a state of the airframe,
not a judgement of the data — finished, certified, on the apron, never taken up.

**Per-ship, and the transition is the product.** `unflown` is never global. It
is this cargo on this ship, and it is the before half of a one-way door:

```
unflown  ──── first run on this ship ────▸  flown · 4.6× realtime · 2026-08-23
```

Once, per model, per ship, irreversible. The running count is the only progress
meter the product needs:

```
CARGO   1 flown · 4 unflown
```

**Two measurement streams, never merged.** `solo` (nothing else running) and
`loaded` (under real workload) differ by roughly 40%. Both are `flown`; the
stream is named on the number. Merging them would be the exact dishonesty this
product exists to refuse.

**Two edges designed, not discovered:**

1. **The ship changes.** New machine or an OS update moves the Metal ceiling. A
   `flown` number holds — your own old measurement beats a stranger's H100 —
   but it names which ship and which hardware fingerprint produced it. It never
   silently demotes to `on paper`.
2. **Cargo that cannot fly.** A model that will not fit stays unflown forever.
   That is a wall, not an invitation, and it renders as an em dash — not a
   state:

```
wan-2.2    fits, tight    unflown       ← invitation
ltx-2.5    won't fit      —             ← not unflown. Just no.
```

---

## 6. Verdicts are a separate axis

Provenance says how we know a number. The verdict says whether the cargo can
fly at all. They stack; they never merge.

| verdict | treatment |
| --- | --- |
| `fits` | plain ink. Nothing to flag |
| `fits, tight` | **platinum** — raised chip, cool achromatic, one luminance step up |
| `won't fit` | rose. A wall, and the only verdict that spends a hue |
| `not supported` | faintest ink. An absence, not a failure |

Platinum is a metal, not a hue: `#cfd4dc` on `--raised` with a
`rgba(207,212,220,.30)` hairline in dark, `#5c6672` in light. Premium without
spending the colour budget, which stays reserved for true, wrong and agent.

---

## 7. Cargo, not collection — and the manifest is the moat

You do not collect models. You carry what fits.

A catalogue of 400 promises abundance and delivers triage: most will not fit,
several are licence-encumbered, one takes 82 minutes per two seconds of video
on hardware twice as good as yours. Four pieces of cargo — each carried because
it fits, each with a job and a logged record — is true, respectable, and gets
better as it gets smaller. "This one is too heavy for this ship" is a normal
sentence about freight and a humiliating one about a collection.

**The moat, said in-world:** weights are commodity — anyone can download the
same cargo. What nobody else holds is your manifest: the log of how each one
actually flies on your ships, measured, dated, keyed by hardware fingerprint.
Everyone buys the same freight. Only you know your routes. The measurement log
is the proprietary asset, and every design decision that makes it richer makes
the product harder to leave.

---

## 8. Ships and docks

**Ships keep the name the OS already gave them.** Naming is a
fake-personalisation tax charged in the first sixty seconds; `USS Renderprise`
happens on day one and never leaves the screenshots.

```
Saurabh's MacBook Pro
M1 Max · 8P + 2E · 32-core GPU · Metal 4
24.96 GB usable  ·  170 GB free  ·  3 fields unread
```

Line one is free and already true. Line two is the instrument. Neither is
invented. Beneath the display name sits a hardware fingerprint — chip, cores,
driver ceiling, OS build — invisible in the UI but keying every measurement,
which is what answers the ship-changed edge in §5.

**Docks never get a friendly name.**

```
g6e.2xlarge · us-east-1 · i-0a3f7c21 · $0.75/hr · 00:41:12
```

Friendly names on metered resources are how people forget the meter. Ships get
human names because they are owned and free; docks get an instance ID and a
running clock because they are billing right now. The asymmetry is itself the
honest signal, and it costs nothing.

**The substrate is a fleet, from day one.** The first real user runs Macs, a
5090 box, and rented docks as one fleet on a tailnet. Every list is plural and
keyed by ship even when it has one row. A layout that structurally cannot show
two ships is the trap; design the list that happens to have one row.

---

## 9. Three thresholds

Motion is rationed by frequency, so exactly three moments earn craft. Each is
crossed once. Everything else is severe forever.

1. **First probe — the ship reads itself.** Once, ever. The readout lands field
   by field, including what it could not read and why. `24.96 GB usable — not
   32.` A machine telling you the truth about itself needs no decoration.
2. **Cargo arrival.** Once per model. Download completes, checksum clears.
   `kokoro-82m is stowed.` The one place a genuine flourish belongs.
3. **First flight.** Once per model, per ship. `unflown` flips to a measured
   number with the ship's name on it — the instant the product stops quoting
   other people and starts knowing something. A needle settling, not confetti.

Numbers that tick are never animated. That rule is what makes the three
moments land.

---

## 10. The quota, said loud

> **Ceiling is 1 dock, by quota.** The G-family spot quota is 8 vCPU. A
> g6e.2xlarge is 8 vCPU. Renting is a decision, not a default.

For the developer wedge this is an asset. Every developer has been burned by a
tool that quietly fanned out and billed them. "There is exactly one, it costs
$0.75/hr, and it bills until you kill it" is a tool that respects them.

**Render the count from the quota. Never hard-code "one."** When the quota
moves, the number moves and the sentence survives.

---

## 11. The wedge, and personas as views

Install to first output with no account, no API key, no config file:

```
$ pip install spacepilot
$ spacepilot check

  Saurabh's MacBook Pro
  M1 Max · 8P + 2E · 32-core GPU · Metal 4
  24.96 GB usable       asked the driver, not the spec sheet
  170 GB free
  3 fields unread       spacepilot check --why

  CARGO   1 flown · 2 unflown
    kokoro-82m    speech   flown         4.6× realtime · 2026-08-23
    wan-2.2       video    fits, tight   unflown
    ltx-2.5       video    won't fit     —

  DOCKS   none rented · $0.00/hr · ceiling 1, by quota
```

The terminal is the first screen and teaches all five words in one pass, which
is why no surface needs a glossary. `spacepilot check` is primary; `doctor` is
an alias because people type it without reading docs.

**Personas change how many facts you see, never which facts are true.** A
creator does not get "fast!" where a developer gets `4.6× realtime`; both get
the number, the creator gets fewer rows around it. Three mechanisms keep later
personas free: the agent surface is the schema and humans are views over it;
persona is inferred from the door (terminal, MCP handshake, spacepilot.dev),
never asked; surfaces are named by function (Cockpit, Create, Flight Check),
never by audience.

---

## 12. What died, and when

**Revision 1 killed (2026-08-23), still dead:** models as planets to capture,
the galaxy as collection, capture animations, nebula gradients, persona
switches, "name your machine", friendly names for rentals, animated counters,
hero video, any accent hue beyond true/wrong/agent.

**Revision 2 kills (2026-08-24):**

- **crew, berth, aboard, off-ship, coming aboard** — four metaphor systems in a
  trenchcoat. Each was locally good; together they needed the lexicon table
  this document is no longer allowed to need. Cargo covers all of them.
- **The two-register vocabulary split.** It was a hedge that let every
  vocabulary survive. One voice everywhere; only motion and density vary.
- **"unflown here" / "flown here".** The "here" was doing per-ship work that
  the data model already does. The word is `flown`; the ship column says where.
- **The misidentification story as copy** stays dead (rev 1 rule, reaffirmed):
  it explains why the probe exists, it belongs in this document, and it appears
  on zero surfaces. Say what we do; let the reader draw the comparison.

**Reopened, deliberately:** galaxies and planets — killed in rev 1 when models
were celestial bodies to capture — return as *scenery only* under §4. The rev 1
kill was about collection mechanics; this is territory. Scenery may appear in
story-layer art and prose. It still never names a UI element.

---

## 13. Still open

- **The freight-chart hero.** Direction chosen (cargo moving between docks on a
  dark chart, legs marked `flown` / `on paper`), unbuilt. Replaces the ring.
- **Sparse density.** The axis is designed; only the dense value is specified.
- **Fleet UI.** Lists are plural and keys exist; the multi-ship view waits for
  a second ship in daily use.
- **Story-layer scenery.** How far the territory imagery goes on landing before
  it fights the ten-second test. Resolve by building, not debating.
