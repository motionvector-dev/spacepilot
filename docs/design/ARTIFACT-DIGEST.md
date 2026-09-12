# Artifact Digest — Cockpit and SpaceBar

Twenty artifacts, read 2026-09-02. All 20 loaded; none failed. Six of them
turned out not to be about the cockpit, SpaceBar, concept, or landing at
all — they're MotionVector-engine or general-agent-harness pieces that
share the artifact list by accident of timing. Cross-referenced against
`docs/design/CONCEPT.md`, `VISION.md`, `~/code/design.md` (the binding
design system), the current `web/cockpit.html`, and PRs #14/24/27/28/94/97
— **all six are still open, none merged.** Nothing here is shipped.

## 1. What each artifact is

| Artifact | Date | Proposes | Surface | Status |
|---|---|---|---|---|
| The Machine's Interface | 09-02 | MotionVector investor pitch (docIR/mvec, not SpacePilot) | other | finished pitch, off-topic |
| Cross-Domain Map | 08-31 | Essay mapping AgentWorth/SpacePilot/MotionVector provenance | other | exploratory essay |
| Prompt to Response | 08-31 | How an agent turn works (context, permissions, tools) | other | finished reference, off-topic |
| Input-State Ballot | 08-29 | MotionVector engine input-layer RFC | other | **Ratified** — MotionVector, not SpacePilot |
| SpacePilot Build Board | 08-25 | Build status ledger; cockpit "mid-redesign" | other | living snapshot, supersedes 08-23 board |
| Six Claims | 08-23 | Quantization quality is unverifiable in the wild | concept | "Round two," supersedes its own first pass |
| The Unclaimed Layer | 08-24 | Positioning: decision layer is unclaimed | concept | settled thesis, no supersession |
| SpacePilot Flight Check | 08-23 | Architecture, scheduler formula, 3 journeys | other | explicitly "a description, not a plan" |
| Scope Creep | 08-23 | 5-panel comic about the project's own scope creep | other | joke, not a proposal |
| SpacePilot Interface | 08-22 | Cockpit UI, 8 screens, tiered Create/Cockpit/Console | cockpit | concrete exploration, no finality claim |
| you already own the hardware | 08-24 | Landing page, warm-machine-wins pitch | landing | polished, undated as draft |
| Cockpit — Playground | 08-24 | 8-section IA replacing shipped cockpit | cockpit | explicit critique-and-replace of shipped code |
| SpacePilot Concept | 08-24 | 8-slide thesis (ship/dock/flown, waist) | concept | canonical thesis, matches CONCEPT.md |
| SpacePilot Logo Concepts | 08-26 | 3 logo directions (Instrument/Hauler/Waist) | other | open, none picked |
| SpacePilot Hero Directions | 08-24 | 7 landing-hero visuals | landing | **explicit pick: "01 + 02" (Bezel+Ceiling)** |
| SpacePilot | 08-23 | Dark/orange landing, "generative cinema workstation" | landing | confident pitch, teases cockpit, shows none |
| SpacePilot Concept (2) | 08-24 | 6-artboard ships/docks/providers/honesty explainer | concept | labeled exploratory ("Concept · 2026-08-24") |
| The Input Diary | 08-26 | MotionVector engine InputState teaching demo | other | pre-decision, off-topic |
| Someone Else's GPU | 08-23 | Decentralized-GPU market field study | other | dated snapshot, off-topic |
| Inference Fleet | 08-16 | Provider-credential inventory, 12 providers | other | dated snapshot, off-topic |

Four of the cockpit/landing/concept artifacts exist as committed files too —
`design-system/pages/{interface,playground,concept-wall,landing}.html` and
`flight-check-v1..v5` — all on the still-open PR #94 branch
(`feat/spacebar-menubar-hud`). Title strings match exactly; I didn't diff
byte-for-byte, so treat that correspondence as strong, not proven.

## 2. Cockpit

Three incompatible shapes are on the table, plus what's actually shipped:

- **As shipped** (`web/cockpit.html`, main): flat top nav (Home/Create/
  Cockpit/Editor/Oven/Docs), then tabs inside Cockpit (Hardware Metrics/Web
  SSH Shell/Service Actions). Lands on a 4-metric grid that reads "—" when
  the rented box is idle, six credential fields before any output.
- **SpacePilot Interface** artifact: three tiers — Create (default), Cockpit,
  Console — "never auto-promoted." Cockpit shows "Where it runs" cards and a
  per-model verdict ("Runs well" / "Runs slowly" / "Won't fit"), numbers
  behind a disclosure. Spend is a persistent, self-terminating ceiling set
  once, with a giant Stop button — not a per-run prompt.
- **Cockpit — Playground** artifact: an 8-group sidebar tree (first-run,
  ship, cargo, runtimes, measurements, system, settings, docks) that puts
  the local machine ("ship") on the default landing screen instead of an
  idle rental. Its own words on the shipped layout: *"This is a structural
  error, not a styling one — restyling it in metal would produce a
  beautiful screen that still opens on a machine that does not exist."*
  Renting shows six facts before a dollar moves; destructive actions ask
  twice, second control deliberately not styled as a button.

Where they agree: local-first landing, verdict-over-numbers, spend shown
before it happens. Where they conflict: the nav shape itself (three tiers vs.
eight sidebar groups vs. flat tabs), and how spend gets confirmed (ceiling
vs. six-fact gate vs. shipped modal). PR #27 (open) already ships a real
version of the Playground's runtime-install states — four states, two-click
downgrade confirm — so that piece has independent momentum outside the
artifacts. No artifact, PR, or doc says which nav shape wins. Build Board's
line stands as the only explicit status marker: *"In Saurabh's design
session now. No agent touches copy or layout meanwhile."*

## 3. SpaceBar

None of the 20 artifacts is a SpaceBar mockup. The only SpaceBar design work
is in-repo, not published as an artifact: PR #94 (`web/menubar.html`,
`web/spacebar-artboard.html`, an "Obsidian Zinc" design-system dump with gold
attention accents and an Apple Intelligence aurora glow border) and PR #97 on
top of it (native Swift status item, modular state pages — idle/active/
caveated/remote — voice bridge, four handoff docs under
`docs/handoff/01`–`04`). Both PRs are open, unmerged. The token file
(`web/spacebar/tokens.css`) is dark-root with no light-default block at
all — `:root`, the dark media query, and `[data-theme="dark"]` all carry the
same near-black values; `[data-theme="light"]` exists but isn't the fallback.
Nothing in the 20 artifacts confirms or contests any of this — it's simply
absent from the set.

## 4. Design language

`~/code/design.md` is binding: Geist/Geist Mono, light-default on bare
`:root`, violet accent (`#7c6bb3` light / `#a396d6` dark), motion at
120/160/220/300ms with `cubic-bezier(.22,1,.36,1)`. Only two artifacts use
it verbatim — **The Machine's Interface** and **Prompt to Response** —
and neither is a cockpit or SpaceBar piece; they're generic MotionVector
pages that happen to share the artifact list.

Every cockpit/SpaceBar/landing/concept-specific artifact instead converges
on a second, unrelated family: near-black root (`#000`–`#09090b`), gold
`#c9a227` as a threshold/attention accent, a silver or four-step chrome
ramp, `true`/`wrong`/`agent` as the semantic triad, Geist kept but the
violet accent dropped entirely. This family spans you-already-own-the-
hardware, Cockpit Playground, SpacePilot Concept, Logo Concepts, Hero
Directions, and SpaceBar's own Obsidian Zinc tokens. It's dark-default or
dark-only everywhere it appears (SpacePilot Interface has no light/dark
toggle at all), which conflicts directly with design.md's 2026-08-31
light-is-default ruling. The shipped `web/cockpit.html` itself defines
`--bg-root:#000000` on bare `:root` with light values only under the
media query and `[data-theme]` overrides — backwards from the mandate.

PR #24/#28 (React app restyle, open) independently landed on the same
three-color idea — `verify`/`danger`/`agent` — but without gold. The gold
accent is cockpit/SpaceBar-artifact-only; it never made it into shipped or
PR-proposed code.

## 5. Open questions, none answered by any artifact

- Cockpit nav: flat top-tabs, three-tier Create/Cockpit/Console, or the
  8-group ship-centric sidebar — which one?
- Does SpacePilot get design.md's light-default violet system, or does it
  keep the dark-default gold/chrome family every cockpit artifact converged
  on independently?
- Spend confirmation: persistent auto-terminating ceiling, six-fact
  pre-rent disclosure, or the shipped modal?
- Is gold a fourth accent color alongside verify/danger/agent, or does the
  PR #24 three-color rule stay final?
- Does SpaceBar get its own artifact design pass, or stay in-repo-only
  (PR #94/#97)?
- Should `web/cockpit.html` be patched to comply with design.md's
  light-default rule, or does SpacePilot get an exemption?
- Of PR #14, #24, #27, #28 — all open, none referencing each other's
  layout choice — which one actually becomes `/cockpit`?
- Hero Directions recommended "Bezel + Ceiling" to replace an existing
  ring graphic — was that ever acted on?
