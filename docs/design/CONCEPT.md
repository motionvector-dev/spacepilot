# Concept — SpacePilot

**2026-08-24**

What SpacePilot is, the words it uses, and the rules every surface follows.
Written to stand alone: a new reader should need nothing else to understand
what we are building and why it looks the way it does.

---

## 1. The name is the thesis

**There has never been a space pilot.** Not one, ever. Astronauts do not
really pilot — spacecraft dock themselves, every engine burn is computed into
a precise window, and orbital mechanics famously defeat human intuition: you
speed up to fall behind, you burn backwards to catch up. When the profession
of space pilot finally exists, it will be a human supervising a machine that
does the flying, because the flying is beyond hands.

**The first space pilots will be software.** That is not a metaphor for this
product; it is a plain description of it. The world of compute — prices
moving daily, rented machines vanishing mid-job, models loaded here but not
there, rules and limits shifting under you — is exactly the kind of space
people cannot fly by feel. You do not hand-calculate an orbit. You should not
hand-decide, fifty times a day, which machine should run which model.

The word "space" also carries a second meaning for free: in machine learning,
a *space* is a mathematical territory — a search space, a latent space — that
you navigate with math because intuition fails there. SpacePilot is the pilot
of a space. Both readings are true, and neither needs explaining to our
audience.

So the brand looks forward, not back. The name is a job title from a
profession that does not exist yet, claimed early. We are betting the job is
about to exist, and that we are it.

---

## 2. What SpacePilot does, in one sentence

> **SpacePilot sends every job to whichever of your machines can answer it
> best right now — and spends money only when you would want it to.**

"Best right now" usually means: the machine that already has the model loaded
in memory, because that one answers instantly and costs nothing extra. When
nothing you own can do the job, SpacePilot can rent a machine — openly, with
the meter in plain view.

Every surface — the website, the app, the command line — must be able to say
this sentence in ten seconds. Everything else in this document exists to
serve it.

---

## 3. Three ideas everything hangs on

### 3a. Already aboard

SpacePilot installs on every machine you use and runs quietly on all of them
at the same time. A model lives in one place. A machine is one place. You are
in one place. **SpacePilot is the only thing in the system that is
everywhere at once** — that is what makes it the pilot rather than another
app.

What follows from this:

- **You don't open SpacePilot; it's already there.** Installing it on a new
  machine is the pilot coming aboard that machine. That moment — not a
  download finishing — is the real beginning.
- **Three doors, one pilot.** A person uses the visual app. An AI agent uses
  the programmatic interface. And with your permission, SpacePilot acts on
  its own. All three are doors into the same pilot, seeing the same facts.
  No door gets a prettier version of the truth.
- **One ceremony.** Letting SpacePilot act on its own — including spending
  money — is the single moment in the product that deserves ritual weight.
  It is designed like signing something, because it is.
- **Asleep is not gone.** No tool in this category, anywhere, treats a
  sleeping laptop differently from a dead one — they all fail the job or
  route around it, and some literally tell users to disable sleep. SpacePilot
  knows the difference: a sleeping machine is still yours, still holds its
  models, and can be woken. Work waits for it honestly. This small mercy is,
  as far as verified research can tell, ours alone.

### 3b. The picture

There is exactly **one shared picture** of everything: which machines exist,
what each carries, what is loaded and ready, what is asleep, what the rented
machine is costing this minute. Every screen — on any machine, in any browser,
from any terminal — is a *window onto that one picture*, never a separate
copy of it. It does not matter which window you look through; the picture is
the picture.

What follows from this:

- **Design one glanceable view, not a cockpit full of gauges.** The job of
  the interface is to show the whole picture at a glance and take orders —
  not to be headquarters. When an interface here grows complicated, it is
  almost always because it forgot it is a window.
- **The right analogy is git, not Docker.** Docker manages each machine
  separately; there is no merged truth. Git has one repository of truth and
  every checkout is a view of it. That is our lineage.
- **Three kinds of state, kept separate.** Facts that only ever accumulate
  (measurements, what happened when) are merged freely — everyone's log,
  combined, is the truth. Settings and intentions have one author — you.
  And "what is happening right now" is never stored at all — it is observed
  fresh, and always carries its age, because a stale "ready" is worse than an
  honest "unknown".
- **The picture is the moat.** Anyone can download the same models. Nobody
  else holds the live picture of *your* machines — what is warm, what is
  asleep, what the next job should do about it.

### 3c. The bet

If AI keeps accelerating, intelligence itself becomes abundant — models are
already just large files anyone can download. The scarce thing, the thing
worth fighting over, becomes **where they run and what the run costs**. The
evidence is already visible: model weights cross every border freely while
the chips that run them are rationed, priced in two diverging lanes, and
carried through customs in suitcases. Free cargo, bordered territory.

This worldview is load-bearing, but it is always the *second* thing we say,
never the first. Lead with what the product does; let the worldview arrive
underneath as depth. A homepage that leads with a philosophy of compute reads
like an exchange, not a tool.

---

## 4. The words, in plain language

Four special words. Everything else on every surface is ordinary, precise
English.

| word | plain meaning |
| --- | --- |
| **ship** | a machine you own. Your laptop, a GPU box, a spare Mac in a drawer. Called a ship because the pilot is aboard it. |
| **dock** | a machine you rent by the hour. A cloud instance, a GPU pod. Called a dock because you pull in, pay, and leave — the meter always visible. |
| **cargo** | a model. Models are freight: big files you download, store, and carry on the machines that can lift them. |
| **flown** | measured for real. "Flown" means *we actually ran this model on this machine and wrote down the number* — as opposed to quoting someone else's benchmark. |

Words derived from these are free: **unflown** (never yet run on this
machine), **flight check** (the readiness report), **pilot / autopilot**
(SpacePilot itself; autopilot means it acts alone, with your permission),
**stowed** (a model finished downloading and is safely on disk). "On paper"
is not jargon at all — it means someone else's published number, quoted with
its source and date.

One word is **held in reserve**: *fuel* (what a run costs). It enters the
vocabulary the day there is a screen that shows costs being weighed, and not
before. A special word no screen uses is a lie about the product.

Two rules keep the vocabulary honest:

1. Everything else stays literal. Disk space is disk space, downloading is
   downloading, loading is loading. The metaphor is a voice, not a costume.
2. If a screen ever needs a glossary, the screen has failed.

One known rough edge, carried openly: a rented machine you set up yourself
and a commercial API that serves models ready-made are both "not yours", but
they behave very differently. For now, only the first is a *dock*; API
services are just called providers. We would rather have a small hole in the
metaphor than force it.

---

## 5. One voice

The register is working space, not Star Trek: owner-operators, freight
manifests, meters running, margins watched. Blue-collar space. No federation
grandeur, no cosmic wallpaper in the interface — galaxies and stars may
appear in storytelling and artwork, never as the name of a button or screen.

The cast is three:

- **You** — the captain. You own the ships; you authorize the spending.
- **The pilot** — SpacePilot, everywhere at once. Copilot by default,
  autopilot only when you grant it.
- **Cargo** — the models. Not characters, not a collection. Carried, because
  they are useful and they fit.

Every kind of user gets this same voice and these same facts. Different
audiences may see *fewer* facts — never softer ones. A casual user and an
engineer both see the real measured number; the casual user just sees fewer
rows around it. Which door you entered through (app, terminal, agent
interface) decides the density; nothing ever asks you to pick a persona.

---

## 6. Honesty about numbers

Most performance numbers in any tool like this were not measured on your
machine. Most tools hide that. Here it is the spine of the design.

Every number answers two questions: *did anyone actually run this?* and *was
it on this machine?*

- **flown** — we ran it, on this machine, on a date you can read. The gold
  standard.
- **on paper** — someone else's number, quoted with source and date. A true
  number about somebody else's hardware.
- **unflown** — nobody has run it here yet. Not a failure; just not yet.

The words matter. We do not say "estimated" (sounds like hedging), or
"unverified" (sounds like an accusation), or "unknown" (false — we know the
claim). *Unflown* is the honest state: finished, sitting on the runway,
never yet taken up from this particular field.

Rules that keep it honest:

- A claimed number and the "unflown here" status stack — both are shown,
  because both are true.
- The first real run flips *unflown* to *flown* forever, one way, per model,
  per machine. The running count (`3 flown · 9 unflown`) is the only
  progress bar the product needs, and it is always computed, never typed in.
- Measurements taken on an idle machine and measurements taken under real
  load are different numbers (often ~40% apart). Both are kept, labeled,
  and never averaged. An average of the two describes a machine nobody has.
- A model that cannot run on a given machine is a wall, not a to-do. It gets
  a plain dash, never an invitation.
- Whether a model *fits* on a machine is a separate question from how it
  performs, shown separately, never blended.

The deep reason this matters is old: harbors force incoming ships to take a
local pilot because knowing *these waters* beats general skill. A benchmark
from someone else's datacenter is general skill. A measurement from your own
machine is local knowledge — and local knowledge cannot be shipped in.

---

## 7. Honesty about presence

The same honesty applies to whether machines are ready:

| state | plain meaning | how it is treated |
| --- | --- | --- |
| **warm** | model already loaded in memory; answers now | the prize — this is what the pilot hunts for |
| **cold** | on disk; must load first, which takes real time | fine, with the load time stated |
| **asleep** | the machine is sleeping. Not gone. | its own state, never drawn like an error |
| **gone** | a rented machine was reclaimed, or a machine vanished | said plainly, with when |

"Asleep" is the one competitors do not have. Work queues for a sleeping
machine, wakes it if it can be woken, and says what it is waiting for.

And every "right now" fact shows its age. A ten-second-old "warm" is
information; a ten-minute-old "warm" shown as fresh is a lie wearing green.

---

## 8. Machines are named honestly

**Your machines keep the names they already have.** The OS already calls it
something ("Maya's MacBook Pro"); we use that. We never ask you to name a
machine — invented names are a toy tax, and the cute name will haunt every
screenshot. Under the display name sits a hardware fingerprint (chip, cores,
memory ceiling, OS build) that ties every measurement to the exact machine
that produced it.

**Rented machines never get friendly names.** They are shown as what they
are: instance type, region, ID, hourly price, and a running clock. Friendly
names on metered things are how people forget the meter. The contrast — warm
names for what you own, cold IDs for what bills you — is itself part of the
honesty.

Every list of machines is built to hold many, even when it holds one. A
design that assumes one machine lies to the future; a design that fakes a
fleet lies today. Show the real list, however short.

---

## 9. Money is loud

Renting compute is a decision, never a default. Prices, limits, and quotas
are said out loud, in numbers, computed from reality — never hard-coded, so
when a limit changes the sentence survives. The meter on anything rented is
always visible, always running, always current.

The reason this is a feature and not an apology: everyone has been burned by
a tool that quietly scaled up and billed them. A tool that says "this will
cost about this much, per hour, until you stop it" is a tool that respects
its owner. An instrument that does not flatter you does not flatter itself
either.

---

## 10. First contact

Install with one command. No account, no API key, no configuration file. The
first thing a new user ever sees is the readiness report: the pilot reads the
machine and reports what it found — including what it could *not* read, and
why. A tool that opens by telling you the truth about your own hardware,
including its own blind spots, has proven its character before asking for
anything.

That first report also quietly teaches all four special words in one pass,
which is why no screen ever needs a glossary.

Three moments in the whole product earn visual craft, each crossed once: the
first reading of a machine, a model arriving safely, and a model's first real
run flipping *unflown* to *flown*. Plus the one ceremony: granting autopilot.
Everything routine stays severe — numbers never animate, nothing celebrates
twice.

---

## 11. What we deliberately do not do

- No collection mechanics. Models are not creatures to catch; most will not
  fit most machines, and a design that promises abundance delivers
  disappointment. Carrying four that fit beats displaying four hundred that
  do not.
- No persona modes. Views differ in density, never in truth.
- No naming your machine, no friendly names for rented ones.
- No cosmic decoration in the interface. Scenery lives in storytelling only.
- No leading with worldview. The product speaks first; the bet speaks second.
- No special vocabulary ahead of the product. Words earn their place by
  having a screen to live on.
- No blank cells where an honesty mark belongs, no averaged measurements, no
  hidden meters, no fallback that looks like success.

---

## 12. Open questions

- **Providers.** The right word and surface for ready-made API services,
  versus machines you control. Deliberately unresolved until that surface is
  designed.
- **Waking.** "Queue and wake" needs a real mechanism per machine type —
  wake-on-LAN, cloud start, or honestly waiting for a lid to open. The
  concept commits to the honesty, not to magic.
- **The sparse view.** The dense, engineer-grade rendering is specified; the
  calm few-facts rendering is not yet.
- **Scenery budget.** How much story-layer atmosphere the website can carry
  before it fights the ten-second job. To be resolved by building, not
  debating.
