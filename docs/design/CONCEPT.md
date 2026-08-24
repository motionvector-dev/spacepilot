# SpacePilot — Concept

> **You decide what to run. SpacePilot decides how and where.**

## The problem

AI workloads change faster than the knowledge needed to run them. New models,
formats, runtimes, and prices arrive weekly; what fits where — and what it
actually costs — shifts under your feet. The result is measurable: open models
lead developer adoption (79% vs 71% closed), yet fewer of their teams reach
production (53% vs 63%) — and the stated reason is the deployment and compute
burden *(Mozilla/SlashData, State of Open Source AI, Jul 2026)*. The knowledge
gap is the product.

## What it is

Give SpacePilot an AI workload — serve a model, fine-tune, embed a corpus,
transcribe an archive. It discovers the feasible ways to run it, ranks them
against your constraints — cost, speed, privacy, reliability — and executes the
best one across three kinds of compute:

- **ships** — machines you own
- **docks** — machines you rent by the hour
- **providers** — managed APIs that serve models ready-made

Local when possible. Rented or managed when useful. Always your call on money.

## How it thinks

```
     YOUR COMPUTE                     THE AI WORLD
  what each machine has,          models · runtimes · formats
  holds, and is doing now         compatibility · live prices
          │                               │
          └──────────────┬────────────────┘
                         ▼
                    SPACEPILOT
             what runs where — right now
                         │
                         ▼
                  plan → run → measure
                         │
                         └──────▶ written back to both maps
                                  every run makes the map better
```

Two live maps, continuously reconciled. Three principles:

1. **Readiness beats specs.** Two identical GPUs are not equal — one already
   holds the model in memory and answers now; the other needs minutes of setup.
   Decisions weigh what is *ready*, not what is *rated*.
2. **Instruments, not memory.** SpacePilot measures your machines instead of
   assuming them, and tracks the AI world as it changes. No knowledge cutoff.
3. **Evidence, not confidence.** It doesn't claim to know the best way — it
   discovers feasible ways, ranks them, runs one, and learns from the result.
   The record of what actually ran, where, and how well is the asset that
   compounds.

## One pilot, many cockpits

One live picture of everything. Terminal, web UI, API, or an AI agent — every
interface is a window onto the same state, never a copy. An agent can ask for
compute without knowing what an instance family is. With your explicit
permission, SpacePilot acts on its own.

## Three words

**Ship**, **dock**, **flown** — a machine you own, a machine you rent, a number
we actually measured here. Everything else is plain English: model, workload,
files. A screen that needs a glossary has failed.

## Honesty rules

- Every number says how we know it: **flown**, **on paper** (cited, dated), or
  **unflown**. Never blended.
- Every live fact shows its age: `ready · checked 8s ago`. A stale "ready" is a
  lie wearing green.
- A sleeping machine is **asleep, not gone**. Work can wait for it, and says so.
- **Money is loud.** Renting is a decision, never a default — estimated cost
  before, actual after, clock always running.
- Ships keep their real names. Docks and providers get IDs, rates, and meters.

## The name

There has never been a space pilot. Spacecraft fly themselves; humans supervise.
When the job exists, it will be software. "Space" also reads the ML way:
territory too high-dimensional to navigate by feel.

## The bet

More models (open and closed), more kinds of compute, and more of the demand
coming from agents rather than people. Whoever holds the live map between them
owns the decision layer. Open-weight momentum is the tailwind, not the premise.

## We refuse to

Look like a fleet manager, a model catalog, or a cloud console. Persona modes,
collection mechanics, cosmic decoration in the UI, vocabulary ahead of the
product, spending that isn't visible, fallbacks that look like success.
