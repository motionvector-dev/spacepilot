---
status: draft — input to a concept pass, not a decision
written: 2026-08-23
verified: 2026-08-23 (product facts checked against the repo on this date)
scope: SpacePilot Cockpit; the observations in §2 apply to the whole product
supersedes: nothing
revisit when: local video generation works, an image runtime ships, or the
  Cockpit restructure in §3 lands — any of those changes what §2 says is true
---

> **Context, not authority.** This is a brief written to aim a concept pass, and
> it records what was true on the date above. §2 in particular goes stale the
> moment a new runtime works. Check it against the repo before building on it.

# Brief — SpacePilot Cockpit

For a concept and voice pass before we open a design canvas. Cockpit first,
taken all the way to shipped, then the others.

---

## 1. What the product is

SpacePilot runs generative models on hardware the user already owns, and treats
their laptop and their cloud account as one substrate. Video first, because it
is the hardest case on every axis — largest weights, worst runtime
fragmentation, thinnest tooling — but the same layer serves image, speech, text
and vision.

The thesis in one line: **any model above, any silicon below, one narrow waist
in the middle.** Everything wide is somebody else's open source. The waist —
probe the machine, pick the model, pick the runtime, place the work — is the
only part that has to be written, and nobody has written it.

The engine repo is `pluto`. The product is SpacePilot. Agents are first-class
users: there is an MCP server, and the web surfaces register WebMCP tools, so a
Claude or a Cursor can drive the product without a human touching a screen.

## 2. What is actually true today

This is the part a fresh session cannot know, and getting it wrong produces a
concept for a product we do not have.

**Works, measured, on the user's own machine:**
- Speech. Kokoro 82M through ONNX, **4.6× realtime**, measured on an M1 Max.
  A sentence in 2.7 seconds, no network.
- Hardware probing. Chip, performance/efficiency core split, GPU core count,
  Metal family, free memory, free disk.
- A model registry: 9 variants across 7 models, every repo resolved against
  Hugging Face, every byte count real.
- A runtime registry: 7 packages, install previewed before it runs.
- Compatibility: every model judged against the machine — fits, tight, won't
  fit, not supported.

**Does not work locally yet:**
- Video. `pluto generate` goes to a cloud box.
- Image. No path at all; mflux would give it.
- Music and SFX. Half-wired.

**The economics:** the cloud box is a g6e.2xlarge spot instance at roughly
$0.75/hour that bills until terminated. The account quota allows **exactly one**.
So the cloud is a single, expensive, deliberate escalation — not a fleet.

**The house rule on numbers.** Every figure in the product declares where it
came from: `measured` (we ran it), `huggingface-api` (summed from the registry
on a date), `declared` (someone else published it, cited), `estimated` (derived,
and the note says from what). Eight of nine models have **no measured speed on
any machine**, and the product says so rather than implying otherwise. This is
not a caveat to design around. It is the most distinctive thing about the
product and it should be visible, not apologised for.

**Reference numbers on the user's own machine**, useful for mockups:
Apple M1 Max · 10 cores (8P + 2E) · 32-core GPU · Metal 4 · 32 GB unified,
of which **24.96 GB** is what the graphics driver will actually hand a model —
not 32. 285 GB free. macOS 26.6.2.

## 3. What Cockpit is now, and why it is wrong

Cockpit today is entirely about the cloud box: GPU telemetry, spot fleet
settings, an SSH terminal, launch and terminate. With no box running — the
normal state, the cheap state, the state every session starts in — it has
almost nothing to say.

That is a structural error, not a styling one. **The product's whole claim is
local-first, and its control surface is about a machine that usually does not
exist.**

Cockpit should open on the machine in front of the user: what silicon, what it
can run, what is installed, what is missing. The cloud box becomes what you
escalate *to* when the local answer is "won't fit" or "82 minutes per clip" —
present, honest about its meter running, and clearly the exception.

## 4. The design language, and what cannot move

Already decided, already shipped, and it is the half of the product that is
good. Treat it as ground, not as suggestion.

- **No accent hue.** The one primary action per view is inverted foreground —
  light on dark, dark on light. Colour is spent only on what is **true**
  (green), what is **wrong** (red), and what **the agent** is saying (a
  desaturated violet). There is no brand blue. There is no gradient.
- **Elevation is luminance, never a shadow.** Surfaces get lighter, they do not
  float.
- **Chrome gets exactly two type sizes.** Rank comes from the text colour ramp
  and from position, not from inventing more steps.
- **Motion is rationed by frequency.** Something seen a hundred times a day gets
  none. Exits are faster than entrances and do not travel — nothing slides away,
  it fades where it stands. Stagger is 40ms and caps at the fifth sibling.
  Reduced motion zeroes distance and keeps time, because a crossfade is the
  accessible affordance rather than the thing to remove.
- **Numbers that tick are never animated.** The stated reason: animating a
  number is the fastest way to make a tool feel like a toy.
- **The brand mark animates once, on cold start, and never again** — a playhead
  sweeps and the mark renders behind it. It is allowed motion *only* because it
  is a surface you meet rarely.

## 5. The central question

The concept on the table is: a copilot, flying a ship, through a galaxy of AI
models as planets and stars, which you capture and bring aboard.

That is genuinely appealing and it collides head-on with everything in §4. A
galaxy you fly through is maximally decorative; the system says colour must mean
something and motion must be earned. Both cannot win everywhere.

**So the brief's real question is: where is the magic allowed to live, if the
chrome stays severe?**

There is already an answer inside the system, and it is a good one. The brand
mark gets motion *because it is rare*. Apply that logic outward:

- Installing your first model is a threshold you cross **once**. That is a
  rare surface. It can carry a real moment — the capture.
- Cockpit is where someone lives while working. That is a hundred-times-a-day
  surface. It stays quiet, forever.

Magic rationed to thresholds; severity everywhere daily. That is a sharper
constraint than "make it feel like a spaceship", and it means the metaphor has
to earn each appearance rather than coat the product.

## 6. Where the metaphor already holds, and where it is dangerous

**Holds, because it is literal rather than decorative:**
- *Copilot* — agents genuinely fly this thing via MCP. The user is not alone at
  the controls. This is a description, not a flourish.
- *Flight check* — already the name of the internal build board, and it is the
  right word for "is this machine ready".
- *Ground control / local* versus *orbit / cloud* — maps exactly onto the
  local-first-then-escalate structure, which is the restructure §3 asks for.

**Dangerous:**
- Aviation and space metaphors are the most crowded territory in developer
  tools. Cockpit is a Red Hat product. Copilot is GitHub's. Ground Control,
  Mission Control, Launchpad, Orbit and Nebula are all taken. The metaphor
  cannot be the differentiator; it can only be the *voice* on top of one.
- The differentiator we actually have is stranger and better: **this thing tells
  you the truth about your own machine when nothing else does.** Three separate
  tools misidentified the user's laptop while this was being built — one called
  a 32 GB M1 Max MacBook Pro an 8 GB 4-core x86 MacBook Air. Ours reads the
  chip, asks Metal for the real ceiling, and marks every number it did not
  measure. That is the brand: *an instrument that does not flatter you.*
- A galaxy of models you "capture" implies collection and abundance. The actual
  experience is closer to triage: most models will not fit, several are
  licence-encumbered, and one of them takes 82 minutes per two seconds of video
  on hardware twice as good as yours. A concept that promises abundance and
  delivers triage will feel like a lie on first contact.

An instrument metaphor may serve better than a voyage metaphor: altimeters,
fuel, weight and balance, go/no-go. Instruments are severe by nature, they are
about honest readings, and "pre-flight check" is a moment of real tension that
does not need decoration to feel consequential. Worth pushing on both.

## 7. Questions to push back on

1. Where does the magic live, given §5? Name the two or three moments that
   deserve it, and argue for each.
2. Is the metaphor load-bearing or a skin? If we removed every space word,
   would the product be worse — or just plainer?
3. What do we call the user's own machine? "Local" is accurate and lifeless.
   It is the hero of this product and it has no name.
4. What is the moment a model finishes downloading called? It is the one
   threshold we know is worth celebrating.
5. How do you say *"this number is an estimate, nobody has measured it"* in a
   way that reads as confidence rather than hedging? This appears eight times
   out of nine and it is the product's spine. Getting this line right may
   matter more than the metaphor.
6. What does Cockpit say when there is no cloud box, no model installed, and
   nothing to show? That is first contact, and today it is an empty page.

## 8. What done looks like

A concept strong enough that a design canvas can be built from it, for one
surface — Cockpit — restructured around the local machine, in the existing
design language, with the magic placed deliberately rather than sprayed.

Not a mood board. A position on the six questions above, in the product's own
voice, that a person can build from.

---

**Appendix — surfaces that exist:** Cockpit (this one), Create (prompt to
output), Studio (timeline and director view), Landing (public, live at
spacepilot.dev), Blueprint, Oven (internal), Docs. Cockpit and Create and
Landing are the three we intend to redesign.
