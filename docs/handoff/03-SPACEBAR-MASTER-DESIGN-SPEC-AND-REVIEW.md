# SpaceBar — Principal Design Review
**Artifact:** `web/spacebar-artboard.html` · **Reviewer scope:** pixel, system-truth, motion, native ergonomics
**Verdict up front:** The token architecture (root→ground→panel→card→raised), the mono-for-truth discipline, and the 24px/1.5-stroke icon geometry are genuinely strong. But the artboard currently demonstrates **only the happy path of a machine that never lies** — and this product's entire thesis is machine truth. Three of your four semantic colors are dead code, the caveat contract has zero UI surface, and the VRAM dial contradicts your own probe contract. Those are P0s.

| Question | Verdict |
|---|---|
| Q1 Density & hierarchy | ⚠️ Job card wins; VRAM headroom doesn't. Remote fleet is *invisible* in Layer 1 |
| Q2 Native ergonomics | ⚠️ Reads as a premium web dashboard wearing macOS chrome. Fixable list |
| Q3 Caveat provenance | 🔴 **Not implemented.** `--warning`, `--error`, `--accent-blue` are never referenced |
| Q4 Motion | ⚠️ Tokens defined, discipline absent. Aurora unimplemented. No reduced-motion |
| Q5 Concrete fixes | ✅ Full prioritized list below |

---

## 1 · P0 — Truth-of-the-Machine Blockers

**T1 · The VRAM dial contradicts `spacepilot probe`.**
Your own contract says **25.0 GB allocatable working set** (this matches Metal's `recommendedMaxWorkingSetSize` on a 32 GB M1 Max, ~75–78% of UMA). The UI says `18.2 / 32 GB`, `purgeVram()` claims "32.0 GB Free", and the dashboard says "13.8 GB Free." A director — or worse, an **agent** making a mount decision via WebMCP — reads 13.8 GB headroom when the real allocatable headroom is **6.8 GB**. Mounting FLUX.1 (+11.4 GB) against the UI's number succeeds on paper and OOMs in Metal. This is the single most dangerous pixel in the file.
**Fix:** axis = 32 GB physical, with a tick at 25.0 GB allocatable and a hatched amber zone between them. Every readout becomes `18.2 / 25.0 GB allocatable · of 32 GB UMA`.

**T2 · "VRAM" is a lie on Unified Memory.**
You call it "AI Resident" in one component and "VRAM USED" in the dial, "Purge VRAM" on the button. Pick the truthful vocabulary: **Resident Weights / GPU Working Set**. "Purge VRAM" → "Evict Weights" (there is nothing to *purge*; you're tearing down resident buffers).

**T3 · The caveat contract has no surface (see §4).** `caveat` appears nowhere in the file. FLUX.1 shows "Q4_K" with no consequence attached.

**T4 · Fleet tab contradicts `fleet status`.**
The table row says "**Local** RTX 5090 Node" — your contract says *remote, 24 ms WireGuard RTT*. And the file contains **no RTT, no Tailscale/WireGuard state, no per-node free VRAM, no queue depth** — the exact metrics a routing decision needs. Jobs/24h and $ are history; RTT and headroom are *decision* telemetry. Also: "STANDBY" is rendered in emerald — emerald means Online/Warm; standby must be neutral (`--ink3`).

**T5 · Spec drift.** Context says **360px** popover; the artboard column and frame label say **340px** (`.artboard-grid { grid-template-columns: 340px 1fr }`). The Studio label claims 940px; the grid actually gives it ~912px. The artboard is the source of truth for implementation — it must match DESIGN.md exactly.

**T6 · Light theme breaks semantic truth.**
`[data-theme="light"]` remaps neutrals but not semantics. Computed contrast on white: emerald `#10b981` ≈ **2.5:1**, amber `#f59e0b` ≈ **2.1:1** — both fail WCAG AA for the 9–11px text they're applied to. `.badge-verified` (hard-coded `rgba(16,185,129,…)`, itself a tokenization miss) fails in light mode too. **Fix:** light-theme text variants (`--online-text: #047857`, `--warning-text: #b45309`), keep bright variants for dots/fills/glow. Also `.mock-macos-bar` is hard-coded `rgba(17,17,20,0.85)` — untokenized, stays dark in light mode.

**T7 · Dead semantic system.** Grep the stylesheet: `var(--warning)`, `var(--error)`, `var(--accent-blue)` — **zero usages**. The active-job progress bar is `var(--ink)` (white) when your design language says Cyber Blue = Active Routing and Aurora = active inference. The "Semantic Truth" layer is currently a palette, not a system.

---

## 2 · Q1 — Information Density & Hierarchy at 360px

**What the eye does today:** header → job card → four *equal-weight* 12px dials → button. The job card correctly wins. But:

- **The hero metric is missing.** `spacepilot run` streams **token/s and s/it** — the number every director glances at — and neither the pill nor the HUD shows it. Add a mono throughput chip to the job card: `45.2 it/s · 3.4 s/it`. (The dashboard's "45.2 FPS" is buried in prose.)
- **VRAM is not the hero it must be.** Four identical dial chips flatten priority. Promote VRAM to a **full-width memory rail** (6px track, resident fill, allocatable tick at 25/32, hatched amber zone), demote temp/fans to chips. One glance answers the only question that matters: *"can I mount the next thing?"*
- **Predictive fit check** — the killer feature this surface enables: hovering **Mount** on FLUX.1 ghosts `+11.4 GB` onto the rail, overflows into the hatch, and inlines `exceeds allocatable by 4.6 GB → evict Wan first`. That's telemetry becoming *decision support*.
- **Local vs remote: currently indistinguishable because remote doesn't exist in Layer 1.** If a job bursts to the 5090 or Modal, the HUD and menu bar pill still describe local silicon. Add a **routing chip** to the HUD header: `⌁ LOCAL · M1 Max` (emerald) vs `5090 · 24 ms` (Cyber Blue) vs `Modal · burst` (blue outline). Encoding contract: **emerald = local warm, blue = remote engaged, neutral = standby, amber = degraded (RTT jitter >80 ms or caveat), crimson = unreachable.** Remote nodes in Studio get a blue left truth-rail + mono RTT badge; never color state with emerald unless it's local-and-warm.
- **Telemetry freshness is provenance.** The header shows "Port 8088" in emerald — a port number isn't a state, and dev-speak doesn't belong in a director surface. Replace with node identity + **staleness**: `M1 Max · Warm · probe 2s ago` (this is where your unused `#i-probe` icon lives). On daemon loss: freeze values at 40% opacity, crimson rail, `STALE 12s` — never let old numbers look alive.
- **Type scale is too flat:** 13/12/11/10/9 with weight doing little work. Go 15/13/11/10 and let mono carry all numerals — including `#hud-job-pct`, which currently inherits **sans** while every neighboring number is mono. Inconsistency in the truth channel is worse than smallness.
- **State coverage gap:** your probe contract's actual idle state — **42°C, 0 RPM, passive** — appears nowhere. The artboard only shows mid-inference. Define the state machine (`IDLE → WARM → HOT → THROTTLE`) and artboard all of it (see §7).

---

## 3 · Q2 — Native macOS Ergonomics

**The "too web-like" inventory (with evidence):**

| Tell | Evidence | Native answer |
|---|---|---|
| Pointer cursors on chrome | `.bar-item-active`, `.dot`, `.nav-item` all `cursor: pointer` | macOS shows arrow on buttons; hand only for URLs |
| `alert()` as interaction | `purgeVram`, fleet ping, pause, pull recipe ×3 | Inline status line in HUD; toast; never modal alert |
| Emoji as button glyphs | "⚡ Max Fan Boost", "❄️ Normal Fan Curve", "☕ Caffeinate" | Your own 27-icon suite (or SF Symbols for system verbs) |
| 9px microcopy | `.dial-label`, `.badge` | 10px floor; 9px uppercase-tracked mono is a web-dashboard signature |
| Inverted-pill nav selection | `.nav-item.active { background: var(--ink) }` | Very Linear/Vercel. Own it as brand *or* move to accent-tinted sidebar selection — but know it's your #1 foreignness signal |
| Fake vibrancy | `.popover-hud` opaque `#111114` + `backdrop-filter: blur(30px)` | Blur over an opaque fill does nothing. Decide: translucent `NSVisualEffectView` (.popover/.HUD material) behind brand cards, **or** commit opaque and delete the filter. Also missing `-webkit-backdrop-filter` — required in WKWebView today |
| No popover arrow / anchor | `.popover-hud` is a floating rounded rect | NSPopover arrow to status item, or declare it a detached panel and design the pin |
| Traffic lights | 11px, always saturated, `alert()` on close | 12px, glyphs on hover only, inert until hovered |
| Runtime web fonts | Google Fonts + `display=swap` in a popover | FOUT shifts telemetry layout on first open. **Bundle Geist/Geist Mono in the app bundle**; drop unused weight 300 |
| Scrollbars, selection | unstyled `overflow-y: auto`; everything selectable | Overlay-style thumbs; `user-select: none` on labels, text-only on values |

**Missing micro-interactions (the native feel lives here):**
- **No `:focus-visible` anywhere.** Add the focus ring; nav items are `<li onclick>` — not focusable, no `role="tab"`. In the real app this maps to NSAccessibility, but the kit must demonstrate the ring.
- **Keyboard map (make it contractual):** `⌘1–⌘6` tabs · `⌘K` command palette · `⌘P` **pin popover** (monitoring HUDs must survive focus loss — this is non-negotiable for the product) · `⌘R` force probe · `⌘,` settings · `Space` mount/eject focused capsule · `Esc` close/cancel · right-click capsule → Mount / Evict / **Copy caveat** / Pin.
- **Pressed states** (`:active` scale 0.98, 60ms) — hovers exist, presses don't.
- **Copy-on-click telemetry:** click any value → copies the CLI equivalent (`spacepilot probe --json`). This is your UI-as-CLI parity principle made tactile.
- **Menu bar pill right-click** → quick menu (Pause / Evict / Pin / Prefs) — also the AppIntents surface.
- **Status item adaptive tiers — required, not nice:** the pill (icon + name + % + GB + °C ≈ 230–250px) will collide with the notch on the exact hardware you target (M1 Max ships in 14"/16" notched MBPs; menu bar ≈ 37px there, and your mock is 32px — and it hides the collision by omitting Clock/Control Center). Tiers: **Full** (icon·model·%·GB·°C) → **Medium** (icon·%·GB) → **Compact** (icon·%) → **Icon** (tinted by state). Measure available width; degrade gracefully.
- **Icon division of labor:** SF Symbols for system verbs (gear, shell, pause), your custom suite for domain nouns (models, fleet, probes). And note: `#i-unflown` (dashed circle = "not yet flown") is the wrong glyph for **Pause** — draw `i-pause`.
- **Icon suite audit: 27 drawn, 20 wired.** Unused: `i-probe`, `i-warning`, `i-refusal`, `i-slot`, `i-install`, `i-quota`, `i-licence`. The seven orphans are *exactly* the truth/provenance icons. That's the review in miniature.
- Tahoe note: system chrome is going translucent (Liquid Glass). Either adopt the system material for the popover sleeve with Obsidian Zinc content cards inside, or commit fully opaque "instrument panel" and delete the blur pretense. Both are defensible; the current middle is not.

---

## 4 · Q3 — Negative Provenance: The Differentiator Is Invisible

The product's moat is *the machine admitting what it's bad at* — and the artboard contains zero amber, zero crimson, zero blue. Spec it:

1. **Truth Rail (systemic):** every capsule gets a 2px left border in provenance color — emerald = verified run, **amber = caveat attached**, dashed (`#i-slot` language) = never flown, crimson = refused/failed. State becomes scannable in the roster grid.
2. **Caveat chip anatomy** (on FLUX.1, per your contract):
```html
<div class="caveat-chip" role="note">
  <svg class="icn icn-sm"><use href="#i-warning"/></svg>
  <span class="mono">Q4_K · word-timestamps drift &gt;120 ms</span>
  <button class="chip-act mono" title="Copy full caveat">⌘C spacepilot caveat flux.1-schnell</button>
</div>
```
One-line truncation in the capsule; full text + first-seen timestamp + affected pipeline stages in the detail drawer.
3. **Pre-mount interstitial:** Mount on a caveated model flips the button to an inline amber confirm — *"Mount anyway? Q4 quant breaks word-timestamps"* — inside the popover, never a modal sheet.
4. **Menu bar propagation:** caveated model ⇒ amber dot on the pill. Negative provenance must be visible *before* you're 26 steps into a doomed render.
5. **Agent parity (this is the agentic-OS play):** `#i-refusal` exists for a reason. When a WebMCP/AppIntents caller requests a pipeline a caveat blocks, the refusal is a first-class event — logged in the Console pane, surfaced in the HUD as `refused · agent · flux.1/timestamps`. Human and agent see the same truth from the same token set. Which implies the deeper rule: **ad-hoc strings like "Whisper Quiet" / "Normal" / "Ready" must become rendered state tokens** (`fan: idle`, `thermal: nominal`) — the popover and the agent API must never be able to diverge.
6. **Build the Console pane.** The footer's "Honesty Terminal" currently just… opens the Telemetry tab. Give it a real pane: mono stream of `probe` / `run` / `caveat` / agent-invocation events. It's the honesty pillar *and* the WebMCP audit log in one surface.

---

## 5 · Q4 — Motion & Fluidity Spec

**Current state:** tokens defined (`--t-enter/exit/crossfade`) but the tab animation hard-codes `180ms`; four components use `transition: all 0.15s` (animates layout, janky, non-tokenized); `--t-exit` and `--t-crossfade` are **never used**; progress animates `width` (layout thrash at telemetry rates); no `prefers-reduced-motion`; **Aurora is in DESIGN.md and nowhere in the file.**

**Curve sheet (contractual):**

| Interaction | Spec |
|---|---|
| Popover in | 200ms `cubic-bezier(0.16,1,0.3,1)`, scale .96→1 + fade, transform-origin at status-item anchor |
| Popover out | 140ms **ease-in** (`cubic-bezier(0.55,0,1,0.45)`) — exits accelerate; your exit token wrongly reuses ease-out |
| Tab switch | Out 100ms ease-in → in 160ms ease-out-expo with 4px rise; incoming only moves. Header persists |
| Progress | `transform: scaleX()` origin-left, 150ms linear continuous; step-jumps 200ms ease-out. Never animate `width` |
| Value swaps | Instant text at ≤2Hz; 120ms ink-flash on change; 200ms crossfade only for regime changes (fan boost) |
| Hover / press | 120ms ease-out on `background-color, border-color, color` only; press scale .98 @ 60ms |
| Mount docking | Border→emerald 200ms; memory rail re-flows 300ms ease-out-expo; badge crossfade 160ms; optional 400ms blue sweep — this is the product's signature moment, make it feel like magnetic docking |
| Pulse dot | Idle-warm: static glow (current `box-shadow` never animates — the class promises motion that doesn't exist). Inferring: 2s ring-expand. Error: 2× 160ms crimson blink |

**Aurora implementation (missing from file):**
```css
@property --aur { syntax: '<angle>'; inherits: false; initial-value: 0deg; }
.aurora::before {
  content:""; position:absolute; inset:0; border-radius:inherit; padding:1px;
  background: conic-gradient(from var(--aur),
    var(--accent-blue), #8b5cf6, var(--online), var(--accent-blue));
  -webkit-mask: linear-gradient(#000 0 0) content-box, linear-gradient(#000 0 0);
  -webkit-mask-composite: xor; mask-composite: exclude;
  animation: aur 4s linear infinite;
}
@keyframes aur { to { --aur: 360deg; } }
/* in: 300ms fade on run-start · out: 600ms fade, one emerald settle pulse */
```
4s/rev — instrument-slow, not gamer-RGB. `@property` is supported in Safari/WKWebView 16.4+.

**Reduced motion (mandatory for macOS):**
```css
@media (prefers-reduced-motion: reduce) {
  * { animation-duration: .01ms !important; transition-duration: 80ms !important; }
  .aurora::before { animation: none;
    background: linear-gradient(135deg, var(--accent-blue), #8b5cf6, var(--online)); }
}
```

**Cadence tiers (systems):** text values 2–4Hz · sparklines 10Hz ring-buffer into rAF (never tween a scope — tweens read as lag) · progress on step events. The "100Hz sampling" claim is a *storage* rate, not a paint rate. Also: sparkline SVGs use default `preserveAspectRatio` (letterboxes, won't fill width) and lack `vector-effect: non-scaling-stroke` — set `preserveAspectRatio="none"` + non-scaling stroke, or render on canvas/WebGPU from the ring buffer.

---

## 6 · Q5 — Prioritized Fix List

**P0 — truth & blockers**
1. Rebase all memory readouts on **25.0 GB allocatable** (T1/T2): dial, rail, purge copy, dashboard row.
2. Wire the semantic system: progress fill → Cyber Blue; STANDBY → neutral; build amber/crimson/blue states into the artboard (T7).
3. Caveat chip + Truth Rail + pre-mount confirm on FLUX.1 (§4).
4. Fleet tab: "Remote 5090 · 24 ms WireGuard", add RTT / free VRAM / queue columns, Tailscale state (T4).
5. Width 340→360px; fix the 940px label; light-theme semantic variants (T5/T6).
6. `-webkit-backdrop-filter` + resolve the opaque-blur contradiction; bundle fonts.

**P1 — native credibility**
7. `:focus-visible` ring, `role="tablist"`, keyboard map, right-click menus, pressed states.
8. Popover arrow + **pin mode**; status-item adaptive tiers with notch math (add ghost Clock/CC to the mock).
9. Replace `alert()`/emoji buttons; pause gets a real glyph and moves into the HUD (it's the most urgent action during a runaway job).
10. Throughput chip (`it/s` / `s/it`) in job card; routing chip for local/remote; staleness indicator with `#i-probe`.
11. Consolidate Studio IA: Telemetry + Sensors + Power overlap → one **Silicon** tab; spend the freed nav slots on **Console** and **Provenance**. 6 tabs → 5.
12. `transition: all` → property-scoped tokenized transitions; progress → `scaleX`; tab animation → `var(--t-enter)`.

**P2 — polish**
13. 9px → 10px floor; unify `#hud-job-pct` to mono; mono `font-feature-settings: "tnum" 1, "zero" 1` for any sans numerals.
14. Sparkline `preserveAspectRatio` + non-scaling stroke + time-window label ("60s"); min/max ticks.
15. Traffic-light hover glyphs; scrollbar styling; selection policy; °C/°F + GB-decimal locale policy.
16. Fan boost: ramp animation, confirmation, auto-clear on thermal settle; stale `dash-active-format` badge bug in `purgeVram()`.
17. Drop unused Geist 300; `.badge-verified` → `color-mix(in oklab, var(--online) 15%, transparent)`.

---

## 7 · Artboard Coverage Gaps (add before engineering consumes this)

- **State matrix sheet:** {Idle, Warm, Hot, Throttle} × {Local, Remote, Offline, Stale} — every cell rendered. Today only one cell exists.
- **Idle probe state** (42°C · 0 RPM · passive) — your contract's actual resting truth.
- **Menu bar tiers** Full→Icon, shown against a notch + Clock + Control Center.
- **Caveat drawer, Console pane, refusal event, agent-initiated job tag** (`#i-agent` + "via Agent" — directors must know *who* started a render).
- **Notification mock** (job complete) and the **empty state** after Evict (currently a text string, not a designed moment).
- **Settings pane** — the gear icon has no destination.

**Three strategic notes to close:** (1) Make **UI-as-CLI parity** a law — every control exposes its `spacepilot` invocation; it keeps human and agent surfaces honest by construction. (2) Write the **energy budget** into the spec: 100Hz only while Studio telemetry is visible; 1Hz pill when closed; App Nap + clamshell suspension — a menu bar app that burns battery contradicts its own hardware-respect thesis. (3) The deepest fix is philosophical: right now the artboard shows a machine that's always fine. Ship the version where the machine can be *degraded, stale, caveated, and refused* — because that's the only version of SpaceBar that's telling the truth.