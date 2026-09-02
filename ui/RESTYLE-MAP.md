# Restyle mapping

The one authority for turning a hardcoded colour into a token. Do not invent a
mapping; if something here does not cover a case, leave it and report it.

Tokens come from `ui/src/tokens.css` and are exposed as Tailwind utilities in
`ui/src/index.css`. Class names below are real and already build.

## Surfaces

Old names implied an elevation ladder. Keep the ladder, change the values.

| hex | was | use |
|---|---|---|
| `#000000` | bg-root | `bg-ground` |
| `#09090b` | bg-ground | `bg-surface` |
| `#111114` | bg-panel | `bg-raised` |
| `#18181b` | bg-card | `bg-inset` |
| `#222226` | bg-raised | `bg-strong` |

## Text

| hex | use |
|---|---|
| `#fafafa`, `#ffffff` | `text-ink` |
| `#d4d4d8` | `text-ink-900` |
| `#a1a1aa` | `text-ink-700` |
| `#71717a` | `text-ink-500` |
| `#52525b` | `text-ink-300` |

## Borders

| was | use |
|---|---|
| `rgba(255,255,255,0.08)` | `border-line-200` |
| `rgba(255,255,255,0.14)` | `border-line-300` |
| `rgba(255,255,255,0.22)` | `border-line-400` |
| `rgba(255,255,255,0.35)` | `border-line-500` |

## Colour — only three have meaning

**`verify`** — something is true, healthy, complete, connected.
`emerald-*`, `#10b981`, `#34d399`, `green-*` → `text-verify` / `bg-verify` /
`border-verify` / `bg-verify-soft`.

**`danger`** — something is wrong, failed, destructive.
`rose-*`, `red-*`, `#f43535`, `#f43f5e`, `#e5484d` → `text-danger` / `bg-danger`
/ `border-danger` / `bg-danger-soft`.

**`agent`** — the agent is speaking or acting. Not decoration.
`purple-*`, `violet-*`, `#a855f7`, `#8900ff` → `text-agent` / `bg-agent` /
`border-agent` / `bg-agent-soft` — **only** where it marks agent output,
AI suggestions, or model-authored content. Where purple was decoration, treat
it as decoration below.

## The rule the three colours are subject to

`verify`, `danger` and `agent` describe **a state of the world**, not a
category, a rank or a feature name. Check what the colour is attached to before
you convert it, because the source hue will happily lie to you:

| the thing is | example | use |
|---|---|---|
| genuinely true / healthy / connected | "Online", "Merged", VRAM headroom | `verify` |
| genuinely wrong / failed / destructive | an error, Terminate, Purge | `danger` |
| the model speaking or its output | agent chat avatar, AI-authored badge | `agent` |
| a rank or a severity level | P0, P1, "HIGH", "MED" | **neutral, weighted** |
| a category or a feature name | a skill card, a section icon, a tab | **neutral** |
| a selection or an active state | selected adapter, current tab | **neutral, weighted** |
| brand | the wordmark | **neutral** — the brand has no hue |

The first pass got three of these wrong by converting the hue rather than
reading the meaning: a **P0** badge became `danger` (P0 is the most urgent work,
not a failure), an **AI Director** skill card became `danger`, and half the
**wordmark** stayed green. All three were red or green in the source, so a
literal hex-to-token swap reproduced the error faithfully.

Where you need a ladder without a hue — p0 above p1, selected above unselected —
use weight and surface: `bg-strong` + `text-ink` + `border-line-500` +
`font-bold` reads as "more" without claiming anything.

**And note that agent is not only purple.** Several of the clearest "the agent
is speaking" moments in this app were emerald in the source — the agent panel's
own header, the Bot icon on Runway Agent Mode — so a purple-only rule sent them
to `verify`, where they said "this is true" about a chat window. Read the label
next to the colour, not the colour.

## Colour with no meaning in this system

`amber-*` `#f59e0b` · `cyan-*` `#06b6d4` · `blue-*` `sky-*` `indigo-*` `teal-*`
`#3b82f6` · `orange-*` `yellow-*`

These become neutral:

| was doing | use |
|---|---|
| emphasis, a value that matters | `text-ink` |
| secondary emphasis | `text-ink-900` |
| ordinary label | `text-ink-700` |
| a fill or chip background | `bg-inset` with `text-ink` |
| a border | `border-line-400` |

**Amber is the one that needs care.** Where amber meant *warning* or *careful*,
removing the colour removes the meaning. Add the word instead — "tight",
"outdated", "not enough memory", "will downgrade" — next to the value. A
neutral chip that says nothing is worse than the amber it replaced.

Report every amber you convert and what you did about the wording.

## Gradients, glows, shadows

Elevation is luminance, never a shadow, and there is no accent hue to glow.

- `bg-gradient-*` between two hues → a flat `bg-*` surface
- `shadow-[0_0_20px_rgba(16,185,129,.25)]` and similar glows → delete
- `drop-shadow`, `blur` used as decoration → delete
- Keep only `shadow-lg` on modal and popover layers

## Motion

If you touch a transition, use the tokens: `duration-[120ms]` for hover and
colour, `160ms` for small entrances, `220ms` for cards. Easing is
`ease-[cubic-bezier(0.22,1,0.36,1)]`. Exits are `120ms` and do not travel.
Do not add motion that was not there.

## Components

Where a hand-rolled button, card, input, badge or spinner exists, prefer the
class from `ui/src/ui.css`: `sp-btn` (+`.quiet`, `.danger`, `.sm`),
`sp-card`, `sp-input`, `sp-chip`, `sp-conf`, `sp-dot`, `sp-table`, `sp-kv`,
`sp-bar`, `sp-spinner`, `sp-rise`. Only when it is a drop-in — do not
restructure markup to force a fit.

## Out of scope

Layout, spacing, sizing, copy, logic, data flow, and anything in `dist/`.
This is colour, type and motion only.
