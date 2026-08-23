---
status: decided — the concept pass the brief asked for
written: 2026-08-23
verified: 2026-08-23 (product facts inherited from COCKPIT-BRIEF.md, checked same day)
scope: SpacePilot brand and product concept — all surfaces
supersedes: nothing. Answers the six questions in docs/design/COCKPIT-BRIEF.md §7
revisit when: local video generation works, an image runtime ships, the G-family
  spot quota moves off 8 vCPU, or a second ship joins the fleet — any of those
  changes what a screen can honestly say
---

# Concept — SpacePilot

The brief asked for a position on six questions, in the product's own voice,
that a person can build from. This is that. It is decided, not proposed.

`COCKPIT-BRIEF.md` remains the input — read it for what is true about the
product today. This file is what we do about it.

---

## 1. The position

**An instrument that does not flatter you.**

Three tools got this laptop wrong while the product was being built. One called
a 32 GB M1 Max MacBook Pro an 8 GB 4-core x86 Air. Ours asks Metal for the real
ceiling, reports 24.96 GB rather than 32, and records every field it could not
read and why.

That is the brand. Not the voyage. The metaphor is voice on top of it — never
the differentiator, because aviation and space are the most crowded namespace in
developer tools and we would lose that fight on day one.

**The misidentification story is motivation, never copy.** It explains why the
probe exists and it belongs in this document. It does not belong on a landing
page, in Cockpit, or in the CLI. A product whose loudest claim is that other
tools are wrong reads as a grievance, not as a thing worth installing. Say what
we do; let the reader draw the comparison. Zero mentions on any surface.

---

## 2. The lexicon

These words are load-bearing. They describe hardware and measurement, so they
are identical in every surface and for every persona. Nothing here is decorative
and nothing here is optional.

| word | means | replaces |
| --- | --- | --- |
| **the ship** | the machine the user owns and is on | "local", which is accurate and lifeless |
| **aboard** | runs on the ship. No credentials, no meter | "local execution" |
| **off-ship** | runs on the rented box. Meter running | "cloud" |
| **crew** | the models installed on this ship | "your models", "library" |
| **berth** | one crew slot. Finite, bounded by disk | "install slot" |
| **flown here** | we ran it on this ship and measured it | `measured` |
| **on paper** | somebody else's published number, cited and dated | `declared`, `huggingface-api` |
| **unflown here** | nobody has run this on this ship | `estimated`, and every blank cell |
| **flight check** | the readiness pass over ship, crew and runtimes | already ours — the build board |
| **copilot** | agents fly this via MCP. A description, not a flourish | — |

### Compatibility verdicts are a separate axis from provenance

Provenance says how we know a number. The verdict says whether the model runs at
all. They stack; they never merge.

| verdict | treatment |
| --- | --- |
| `fits` | plain ink. Nothing to flag |
| `fits, tight` | **platinum** — a raised chip, cool achromatic, one luminance step above the zinc around it |
| `won't fit` | rose. A wall, and the only verdict that spends a hue |
| `not supported` | faintest ink. An absence, not a failure |

Platinum is a metal, not a hue: `#cfd4dc` on a `--raised` surface with a
`rgba(207,212,220,.30)` hairline in dark, `#5c6672` in light. It reads premium
without spending the colour budget, which stays reserved for true, wrong and
agent, and it satisfies "elevation is luminance, never a shadow" because that is
literally how it is built. No gradient — metal here is a luminance step and a
cool cast, nothing more.

**Dead on arrival:** galaxy, planets, stars, capture, constellation, nebula,
stardust, warp, hyperdrive, launch sequence, mission control, orbit, ground
control. Each is either decorative with no referent, or already owned by a
larger company.

---

## 3. Provenance is the design language

Eight of nine model variants have no measured speed on any machine. That is not
a caveat to design around. It is the spine.

Two axes, and most tools collapse the wrong one:

```
                  measured HERE       measured ELSEWHERE
  we ran it     │  flown here      │   —
  they claim it │  —               │   on paper
  nobody ran it │  unflown here    │   unflown here
```

LTX at 12 s/clip on an H100 is a true number that says nothing about a 24.96 GB
M1 Max. So `on paper` and `unflown here` stack rather than compete:

```
LTX-2.5 · video · won't fit aboard
12 s/clip on paper (H100 · model card, 2026-08-12) · unflown here
```

### Why `unflown` and not `estimated`

`estimated` reads as a hedge on our own competence. `unverified` is accusatory
toward the source. `unknown` is false — we know the claim. `untested` implies
negligence. `no data` is a blank with a label on it.

`unflown` is a state of the aircraft, not a judgement of the data. An unflown
airframe is finished, certified, sitting on the apron, and nobody has taken it
up yet. That is exactly the condition. It also fits crew without a seam: a crew
member can be signed on and unflown, and that is a normal thing to be on day one.

### It is per-ship, and the transition is the product

`unflown` is never a global property of a model. It is a property of this model
on this ship, and it is the before half of a one-way door:

```
unflown here  ──── first run on this ship ────▸  flown here · 4.6× realtime · 2026-08-23
```

Once. Per model. Per ship. Irreversible. Every screen carries the running count,
and it is the only progress meter the product needs:

```
CREW   1 flown · 4 unflown
```

Every other tool gets more confident with use because it hides more. This one
gets more true.

### Two edges that must be designed, not discovered

1. **When the ship changes.** New machine, or an OS update that moves the Metal
   ceiling. A `flown here` measurement holds — your own old measurement is
   better evidence than a stranger's H100 — but it must name which ship and
   which hardware fingerprint produced it. It never silently demotes to
   `on paper`.
2. **When a model cannot fly.** A model that will not fit stays unflown forever.
   Rendering it identically to "unflown, fits, tight" is misleading: one is an
   invitation, the other is a wall. The wall case gets an em dash, not a state.

```
wan-2.2    fits, tight    unflown here      ← invitation
ltx-2.5    won't fit      —                 ← not unflown. Just no.
```

Do not invite someone onto an aircraft they cannot lift.

---

## 4. Crew, not collection

The concept on the table was a galaxy of models you capture like Pokémon. That
is rejected, for one reason: it promises abundance and delivers triage. Most
models will not fit. Several are licence-encumbered. One takes 82 minutes per
two seconds of video on hardware twice as good as the user's. A concept that
promises abundance and delivers triage feels like a lie on first contact.

You do not collect models. You **crew** them.

A galaxy of 400 catchable creatures is a lie about your ship. A crew of four —
each chosen because it fits, each with a job and a logged record — is true,
respectable, and gets better as it gets smaller. "This one does not come aboard,
it is too heavy" is a normal sentence about a ship and a humiliating one about a
Pokédex.

Berths are finite and visible. `1 aboard · 4 berths open` is computed from disk,
never a constant.

---

## 5. Where the magic lives

The system already rations motion by frequency: the brand mark animates on cold
start because you meet it rarely. Extended outward, that yields exactly three
moments. Each is crossed once. Each earns real craft. Everything else is severe
forever.

**1 · First probe — the ship reads itself.** Once, ever. First contact, and
where the product is won. The readout lands field by field, including the fields
it could not read and why. `24.96 GB usable — not 32.` A machine telling you the
truth about itself for the first time needs no decoration.

**2 · Coming aboard.** Once per model. Download completes, checksum clears, it
takes a berth. `kokoro-82m is aboard.` This is the honest version of the capture
moment, and the one place a genuine flourish belongs.

**3 · First flight.** Once per model, per ship. The figure flips from `unflown`
to a measured number with the ship's name on it. This is the instant the product
stops quoting other people and starts knowing something. A needle settling, not
confetti.

Everything daily — Cockpit telemetry, model lists, runtime installs — gets
nothing. Numbers that tick are never animated. That rule is what makes the three
moments land.

---

## 6. Ship identity

**The user never names their machine.** Naming is a fake-personalisation tax
charged in the first sixty seconds, and the slope to cute is short and steep.
`USS Renderprise` will happen on day one and will never leave the screenshots.

The ship uses the name it already has, from the OS, alongside the instrument:

```
Saurabh's MacBook Pro
M1 Max · 8P + 2E · 32-core GPU · Metal 4
24.96 GB usable  ·  285 GB free  ·  3 fields unread
```

Line one is free and already true. Line two is the instrument. Neither is
invented.

**This is a primary key, not decoration.** The first real user runs Macs, a
5090, RunPod and Modal as one fleet. The moment there are two ships,
`flown here` must resolve to *which* here:

```
kokoro-82m   flown here   4.6× realtime   Saurabh's MacBook Pro   2026-08-23
wan-2.2      flown here   31 s/clip       the 5090 box            2026-08-21
wan-2.2      unflown here                 Saurabh's MacBook Pro
```

Beneath the display name sits a hardware fingerprint — chip, core counts, driver
ceiling, OS build — invisible in the UI, but what actually keys the log and
answers the ship-changed edge case in §3. Design that key now or retrofit it
through every measurement record later.

### Rentals get the opposite treatment

The rented GPU never gets a friendly name.

```
g6e.2xlarge · us-east-1 · i-0a3f7c21 · $0.74/hr · 00:41:12
```

Friendly names on metered resources are how people forget the meter is running.
The ship gets a human name because it is owned and free. The rental gets an
instance ID and a running clock because it is billing right now. The asymmetry
in how the two are named is itself the honest signal, and it costs nothing.

---

## 7. Two registers: landing demonstrates, Cockpit operates

Same severity, same palette, same refusal to flatter. Different job.

| | Landing | Cockpit |
| --- | --- | --- |
| verb | **demonstrate** | **operate** |
| subject | a machine that is not ours | the machine you are on |
| vocabulary | explains itself once | assumes you know |
| motion | allowed | rationed to near zero |
| time on surface | 40 seconds, once | all day, forever |

Landing is a rare surface, so under the existing frequency rule it earns motion
and Cockpit still gets none. That is the rule working, not an exception carved
for marketing.

### The landing page is the browser probe

Two probes, one registry — already the architecture, and already the page. The
reader arrives and, before any copy or signup, the browser probe tells them a
true thing about their own machine, then states exactly what it could not know:

```
You are on an Apple M1 Max. 32-core GPU.

We can read that much from a browser.
We cannot ask your driver how much of your 32 GB
it will actually hand a model.

Three tools we tried got this laptop wrong.
One called it an 8 GB, 4-core x86 Air.

  install → we ask the driver  ▸
```

The pitch is a demonstration rather than a claim, and the CTA is generated by
the probe's own honest limit. The browser names the chip; it cannot reach the
driver. That gap is the button. No hero video, no gradient, no galaxy.

### Cockpit's cold open

Cockpit today is built around a box that usually does not exist, so it has
nothing to say in the normal state. Restructured around the ship, it can never
be empty:

```
┌─ ABOARD ────────────────────────────────────────────────────┐
│  Saurabh's MacBook Pro                                      │
│  M1 Max · 8P + 2E · 32-core GPU · Metal 4                   │
│  24.96 GB usable          not 32 — asked the driver         │
│  285 GB free                                                │
│  3 fields unread          why ▸                             │
├─ CREW ──────────────────────────────────────────────────────┤
│  kokoro-82m      speech    flown here · 4.6× realtime       │
│  4 berths open                                              │
├─ ON PAPER ──────────────────────────────────────────────────┤
│  wan-2.2         video     fits, tight   · unflown here     │
│  ltx-2.5         video     won't fit     · —                │
├─ OFF-SHIP ──────────────────────────────────────────────────┤
│  none running · $0.00/hr · ceiling is 1 box, by quota       │
└─────────────────────────────────────────────────────────────┘
```

`3 fields unread — why` is the single most differentiating element in the
product. First contact proves the tool is not lying before it asks for anything.

---

## 8. The developer is the wedge

Install to first output with no account, no API key and no config file. The
terminal is therefore the first screen, and it teaches the entire vocabulary in
one pass — which is why no surface needs a glossary:

```
$ spacepilot check

  Saurabh's MacBook Pro
  M1 Max · 8P + 2E · 32-core GPU · Metal 4
  24.96 GB usable       asked the driver, not the spec sheet
  285 GB free
  3 fields unread       spacepilot check --why

  CREW   1 aboard · 4 berths open
    kokoro-82m    speech   flown here    4.6× realtime · 2026-08-23

  ON PAPER
    wan-2.2       video    fits, tight   unflown here
    ltx-2.5       video    won't fit     —

  OFF-SHIP   none running · $0.00/hr
    Ceiling is 1 box. G-family spot quota is 8 vCPU;
    a g6e.2xlarge is 8 vCPU. $0.74/hr, bills until terminated.
```

`spacepilot check` is primary. `doctor` is an alias, because people type it
without reading docs. The output is titled *Flight check* — the same words as
the internal build board.

---

## 9. The quota, said loud

> **Ceiling is 1 box.** The G-family spot quota is 8 vCPU. A g6e.2xlarge is
> 8 vCPU. So off-ship is a decision, not a default.

For the wedge persona this is an asset, not an admission. Every developer has
been burned by a tool that quietly fanned out and billed them. "There is exactly
one, it costs $0.74/hr, and it bills until you kill it" is a tool that respects
them. The constraint reads as discipline — an instrument that does not flatter
you does not flatter itself either.

**Render the count from the quota. Never hard-code "one."**

```
Ceiling is {n} box{es}, by quota.
```

When the quota moves the number moves and the sentence survives. Same discipline
for `{n} berths open`, computed from disk.

---

## 10. Personas are views, never modes

The trap is a persona switch. Ship "Developer Mode / Creator Mode" and you have
two half-products, and the second one lies — because the moment a persona can
change what is on screen, someone softens a number for the creator.

> **Personas change how many facts you see. They never change which facts are
> true.**

A creator does not get "fast!" where a developer gets `4.6× realtime`. Both get
`4.6× realtime`; the creator gets fewer rows around it. `unflown` appears in
every persona forever, because it is a fact about hardware rather than a
developer's tolerance for detail.

Three mechanisms make later personas free:

1. **The agent surface is the schema; humans are views over it.** Agents have no
   visual density, only facts. If CLI, Cockpit and Landing all render what the
   MCP tools return, personas cannot diverge without diverging from the schema.
   That is an architectural guarantee, not a design convention.
2. **Persona is inferred from the door, never asked.** Terminal, MCP handshake,
   or spacepilot.dev. A fourth persona is a fourth door — not a switch, and no
   existing user gets re-onboarded.
3. **Surfaces are named by function, never by audience.** Cockpit, Create,
   Flight Check. Ship "Developer Dashboard" and adding a persona means either
   renaming it or building a parallel one.

### Expose the axis, ship one value

| axis | values | ship now |
| --- | --- | --- |
| density | dense · sparse | **dense** |
| surface | cli · cockpit · landing · mcp | **cli + cockpit** |
| ships | 1 · n | **n**, currently n=1 |
| off-ship boxes | 0 · 1 · n | **n**, ceiling 1 |

The last two rows are the ones that hurt if skipped.

> **Design the list that happens to have one row.**

A frontend that shows a fleet when there is one machine is a lie with a nice
gradient. The inverse trap is a layout that structurally cannot show two — a
hero card for "your machine", a singleton off-ship panel. The first real user
already runs Macs, a 5090, RunPod and Modal as one fleet. Ship a ship-list with
one row and an off-ship list with zero: both honest today, both correct at n=4
without a redesign. `flown here` is keyed by ship from day one, even with one
ship to key it to.

---

## 11. What this kills

- The galaxy, the starfield, planets and stars as models, the capture animation
  as collection, any nebula gradient. Decorative by construction, and in direct
  conflict with "colour must mean something".
- Any accent hue beyond the existing three: true (green), wrong (red), agent
  (desaturated violet). There is no brand blue and no gradient.
- Persona switches, mode toggles, "name your machine", friendly names for
  metered rentals, animated counters, hero video.
- Any blank cell where a provenance mark belongs.

The design language in `COCKPIT-BRIEF.md` §4 is unchanged by this document and
is not up for renegotiation here: no accent hue, elevation by luminance, two
type sizes in chrome, motion rationed by frequency, exits faster than entrances
and travelling nowhere, reduced motion zeroing distance and keeping time.

---

## 12. Answers to the brief's six questions

1. **Where does the magic live?** Three thresholds, each crossed once: first
   probe, coming aboard, first flight. §5.
2. **Is the metaphor load-bearing or a skin?** Load-bearing for copilot, flight
   check, aboard/off-ship, crew/berth/flown. A skin — and killed — for
   everything voyage-shaped. §2.
3. **What do we call the user's own machine?** The ship, and it carries the name
   the OS already gave it. §6.
4. **What is the moment a model finishes downloading called?** Coming aboard.
   §5.
5. **How do we say "nobody measured this"?** `unflown here`. §3.
6. **What does Cockpit say when there is nothing to show?** It is never empty —
   the ship is always there, and `3 fields unread — why` is the opening move. §7.

---

## 13. Still open

- **Density on the sparse end.** The axis is designed; only the dense value is
  specified. A creator surface needs the sparse rendering defined before it
  ships, and it must not soften a single number.
- **Fleet UI.** Deliberately unscoped. The lists are plural and the keys exist;
  what a multi-ship view actually looks like waits for a second ship.
- **The glossary moment on landing.** The terminal teaches the vocabulary for
  the wedge persona. Whether landing needs its own one-time definition pass, or
  can rely on context the way the CLI does, is untested.
