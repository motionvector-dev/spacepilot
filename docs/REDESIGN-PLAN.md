# Pluto Studio Redesign Plan

> **Status:** Superseded. This plan assumes a zero-build vanilla stack. The product now ships as a built React app: `https://spacepilot.dev` returns HTTP 200 from Vercel and is deployed to actively.
> **Verified:** 2026-08-22, by `curl -I https://spacepilot.dev` and `gh pr view 14 16`.
> **Superseded by:** the React `ui/` tree on `feat/frontend-react-ui` (PR #14). Context in docs/DECISION-INBOX-frontend-react-vs-vanilla.md.
> **Kept because:** the Runway-derived interaction design here is not tied to the vanilla stack and can inform the React surfaces.
> **Date:** 2026-08-21  
> **Reference:** Runway ML Gen-4 / Agent Interface (10 screenshots captured 2026-08-21)  
> **Goal:** Transform Pluto Studio from a header-nav NLE layout into a modern, agent-first creative studio — while preserving MotionVector Obsidian design DNA and zero-build vanilla stack.

---

## 1. Design Reference Audit

### Runway ML Patterns Observed (10 screenshots)

| Pattern | Runway Implementation | Pluto Equivalent |
|---|---|---|
| **Left sidebar** | Persistent icon rail (collapsed 48px → expanded 200px): Home, Agent, Tool, Apps, Workflows, Recents, Projects, Assets, Favorited, More | Currently a slideout config drawer (`sidebar.js`). **Needs full rebuild** |
| **Top header** | Minimal — chat title left, credits + upgrade + settings right | Heavy header with brand, nav, mode tabs, GPU telemetry, export. **Needs simplification** |
| **Center stage** | Full-bleed hero prompt: "Hi Saurabh, what do you want to create?" with rotating suggestions, skill pills | No equivalent. Home page is separate. **Need to merge** |
| **Prompt input** | Floating card with media upload (+), Tab-completion, `Ask · Quality` config, submit arrow | Page-specific and simpler. **Adopt this pattern** |
| **Skills system** | Starters/Media tabs, searchable `/Skill` cards with thumbnails, "Write it myself" / "Create with Agent" CTAs, custom skill creator modal | No equivalent. **Add entirely new** |
| **Agent chat** | Right panel — multi-turn conversation, wizard cards (radio choices), "Reasoning" expanders, "Thought for Xs" traces | AI Director storyboard — not conversational. **Adapt** |
| **Gen preferences** | Dropdown: Ask/Auto toggle, Quality/Speed/Cost/Custom optimization, "Set as default" | No equivalent. **Add** |
| **Timeline** | Bottom dock — multi-track NLE with split/undo/redo, timecode, download, zoom | Timeline exists. **Polish to match** |
| **Chat/Session toggle** | Bottom sidebar — switch Chat ↔ Session modes | No equivalent. **Map to Director/Vibe modes** |
| **Credits/Account** | Top-right: credit counter, upgrade button, avatar | GPU telemetry capsule. **Add credits display** |
| **Create Skill modal** | Modal: Name, Description, Instructions (5000 char), Sharing, Cancel/Create | No equivalent. **Add** |
| **Category tabs** | Below prompt: Marketing, Movies, Social media, Educational, Other — with example cards | No equivalent. **Add to home** |

---

## 2. Architecture: Before → After

### Current Layout (Header-First)

```
┌─────────────────────────────────────────────────────┐
│  HEADER: Brand │ Nav Links │ Mode Tabs │ GPU │ Btns │
├─────────────────────────────────────────────────────┤
│                                                     │
│              MAIN CONTENT (full width)              │
│         (Director View / Vibe Editor View)          │
│                                                     │
├─────────────────────────────────────────────────────┤
│              TIMELINE (bottom dock)                 │
└─────────────────────────────────────────────────────┘
  + Slideout Config Sidebar (hidden by default)
```

### New Layout (Sidebar-First, Runway-Inspired)

```
┌──┬──────────────────────────────────────────┬──────┐
│  │  MINI HEADER: Chat Title │ Credits │ ··· │      │
│  ├──────────────────────────────────────────┤      │
│  │                                          │      │
│ S│            CENTER STAGE                  │ A    │
│ I│     (Prompt Hero / Preview / Editor)     │ G    │
│ D│                                          │ E    │
│ E│                                          │ N    │
│ B│  ┌────────────────────────────────────┐  │ T    │
│ A│  │  Prompt Input  │ Ask·Quality │ →   │  │      │
│ R│  └────────────────────────────────────┘  │ P    │
│  │                                          │ A    │
│  │  [Skill Pill] [Skill Pill] [Skill Pill]  │ N    │
│  │                                          │ E    │
│  ├──────────────────────────────────────────┤ L    │
│  │           TIMELINE (when active)         │      │
└──┴──────────────────────────────────────────┴──────┘
```

---

## 3. Component-by-Component Spec

### 3.1 Left Navigation Sidebar (NEW — replaces `sidebar.js/css`)

**Collapsed state:** 56px wide icon rail  
**Expanded state:** 240px with labels

| Section | Icon | Label | Route/Action |
|---|---|---|---|
| — Primary — | | | |
| + New Chat | ✨ | New Chat (dropdown: Chat / Session) | Creates new generation session |
| Home | 🏠 | Home | `/` or `/home` |
| Agent | 🤖 | Agent (AI Director) | `/studio` (director mode) |
| Create | 🎬 | Create | `/create` |
| Cockpit | ⚡ | Cockpit | `/cockpit` |
| — Library — | | | |
| Recents | 🕐 | Recents | Shows recent generations |
| Projects | 📁 | Projects | Project browser |
| Assets | 🖼️ | Assets | Media library |
| — System — | | | |
| Oven | 🔥 | Oven (Swarm) | `/oven` |
| Settings | ⚙️ | Settings | Opens config (replaces old sidebar) |
| — Bottom — | | | |
| Mode toggle | | Chat / Session | Switches Director ↔ Vibe modes |
| Account | 👤 | "Saurabh" + tier badge | Account menu |

**Behavior:**
- Hover → expand with labels (200ms ease)
- Click hamburger icon → pin expanded
- On studio/timeline pages → auto-collapse to icon rail
- Recents section shows last 5 sessions with thumbnails

### 3.2 Top Header (SIMPLIFIED)

**Current:** 46px, packed with brand, nav links, mode tabs, theme toggle, command palette, GPU telemetry, Launch GPU, Export Master

**New:** 44px minimal bar

```
┌────────────────────────────────────────────────────────────┐
│  ✨ New chat ···          │  117 credits │ ⬆ Upgrade │ ··· │
└────────────────────────────────────────────────────────────┘
```

| Element | Behavior |
|---|---|
| Left: Chat/session title | Editable inline, "···" opens rename/delete dropdown |
| Center: *empty* | Clean negative space |
| Right: GPU Cost pill | Shows GPU cost remaining, click → usage breakdown |
| Right: Launch GPU | Primary CTA pill |
| Right: ··· overflow | Theme toggle, Command Palette (⌘K), Export, GPU Diagnostics |

**What moves:**
- Mode tabs → removed (sidebar determines mode)
- Brand logo → moved to sidebar top
- Nav links → removed (sidebar handles navigation)
- GPU telemetry → moved to overflow menu + cockpit page
- Export Master → moved to overflow menu

### 3.3 Prompt Input Bar (NEW — universal component)

Appears on: Home, Agent/Create, anywhere a generation starts.

```
┌──────────────────────────────────────────────────────────────┐
│ [+] [image thumb] [image thumb]                              │
│                                                              │
│ Build a Mood Board to pitch a campaign concept    Tab        │
│                                                              │
│ [+]                                   Ask · Quality    [→]   │
└──────────────────────────────────────────────────────────────┘
```

**Features:**
- Media upload button (+) — opens file picker / drag-and-drop zone
- Inline media thumbnails — attached images/videos as small chips
- Tab completion — rotating placeholder suggestions
- "Ask · Quality" config — opens generation preferences popover
- Submit arrow (→) — sends generation request
- Auto-resize textarea — grows with content, max 6 lines
- Slash commands — type `/` to open skills picker inline

### 3.4 Generation Preferences Popover (NEW)

Triggered by clicking "Ask · Quality" on the prompt bar.

```
┌─────────────────────────────────────────┐
│  When generating media                  │
│  ┌──────────┐ ┌──────────┐              │
│  │   Ask    │ │   Auto   │              │
│  └──────────┘ └──────────┘              │
│                                         │
│  Optimize generations                   │
│  ┌─────┐ ┌─────┐ ┌─────┐ ┌──────┐      │
│  │Qual.│ │Speed│ │ Cost│ │Custom│      │
│  └─────┘ └─────┘ └─────┘ └──────┘      │
│                                         │
│  FAQs                    [Set default]  │
└─────────────────────────────────────────┘
```

- **Ask/Auto:** Whether the agent asks clarifying questions before generating
- **Quality/Speed/Cost/Custom:** Maps to existing model/resolution presets
- **Set as default:** Persists preference via `/api/cockpit/config`

### 3.5 Skills System (NEW)

#### Skills Drawer

Below the prompt input, triggered by `+` icon or typing `/`:

```
┌──────────────────────────────────────────────────────────────┐
│  ⚡ Starters    📁 Media                              ✕    │
├──────────────────────────────────────────────────────────────┤
│  Skills                                             🔍     │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                  │
│  │  [thumb] │  │  [thumb] │  │  [thumb] │                  │
│  │ /T2V     │  │ /I2V     │  │ /Upscale │                  │
│  │ Text to  │  │ Image to │  │ 4K Super │                  │
│  │ Video    │  │ Video    │  │ Res      │                  │
│  └──────────┘  └──────────┘  └──────────┘                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                  │
│  │ /Loop    │  │ /Style   │  │ /Extend  │                  │
│  │ Seamless │  │ Transfer │  │ Video    │                  │
│  │ Loop     │  │          │  │ Extend   │                  │
│  └──────────┘  └──────────┘  └──────────┘                  │
│                                                              │
│  📝 New Skill — Teach Agent a task you'll want again         │
│  ┌──────────────────┐  ┌───────────────────────┐            │
│  │  Write it myself │  │  Create with Agent   │            │
│  └──────────────────┘  └───────────────────────┘            │
└──────────────────────────────────────────────────────────────┘
```

**Skills map to Pluto capabilities:**
- `/T2V` — Text-to-Video (current create.html primary mode)
- `/I2V` — Image-to-Video (current create.html with image input)
- `/Upscale` — 4K Super Resolution
- `/Loop` — Seamless Loop generation
- `/Style` — Style Transfer
- `/Extend` — Video Extension
- `/Director` — Full AI Director workflow (multi-scene storyboard)
- `/Motion` — MotionVector-specific motion controls

#### Create Skill Modal

```
┌─────────────────────────────────────────┐
│  📝 Create Skill                        │
│  Give the Agent a set of instructions   │
│  it can follow anytime.                 │
│                                         │
│  Name ________________________________  │
│  Description __________________________  │
│  Instructions (0/5000) _______________  │
│  Sharing [Private ▼]                    │
│                                         │
│  [     Cancel     ]  [     Create     ] │
└─────────────────────────────────────────┘
```

### 3.6 Agent Chat Panel (RIGHT SIDE — enhanced AI Director)

When in Agent/Director mode, a 360px right panel becomes a conversational agent:

**Features:**
- Multi-turn Q&A wizard cards with radio selections
- "Reasoning" / "Thought for Xs" collapsible traces
- Paginated questions (1 of N)
- Message input at bottom
- Can reference attached media
- Storyboard cards render inline as generation results

### 3.7 Home Page (REDESIGNED)

Transform from minimal landing into a creative hub:
- Hero greeting: "Hi {name}, what do you want to create?"
- Universal prompt bar
- Quick-action skill pills: `[Edit Timeline]` `[T2V]` `[I2V]` `[Upscale]` `[Skills ≡]`
- Category tabs: Marketing | Films | Social | Educational | Other
- Example cards grid with thumbnails
- "New at MotionVector" feature showcase section

### 3.8 Timeline (POLISH — keep structure, refine chrome)

- Reduce toolbar visual weight — match Runway's minimal chrome
- Add glassmorphism (`backdrop-filter: blur(16px)`) to floating toolbar
- Tighter track heights (32px → 28px)
- Timecode in monospace, smaller
- Keep Split/Undo/Redo, add Download button
- Zoom slider matches Runway's minimal style

---

## 4. CSS Design Token Updates

### Keep (Already Aligned)

```css
/* Already matching Runway — no changes needed */
--bg-root: #000000;
--bg-ground: #09090b;
--bg-panel: #111114;
--bg-card: #18181b;
--border-subtle: rgba(255,255,255,0.08);
--text-main: #fafafa;
--text-muted: #a1a1aa;
```

### Add / Modify

```css
/* Layout tokens */
--sidebar-width-collapsed: 56px;
--sidebar-width-expanded: 240px;
--header-height: 44px;
--agent-panel-width: 360px;

/* Accent color — blue for primary CTAs */
--accent-primary: #3b82f6;
--accent-primary-hover: #2563eb;

/* Glass surfaces */
--bg-glass-toolbar: rgba(17, 17, 20, 0.75);
--backdrop-blur: blur(16px);

/* Prompt input */
--prompt-bg: var(--bg-card);
--prompt-border: var(--border-medium);
--prompt-focus-border: var(--border-highlight);

/* Skill cards */
--skill-card-bg: var(--bg-card);
--skill-card-hover: var(--bg-raised);
--skill-card-radius: 12px;

/* Credits pill */
--credits-bg: rgba(255, 255, 255, 0.06);
--credits-text: var(--text-muted);

/* Typography — tighter tracking for hero text */
--tracking-tight: -0.02em;
--tracking-tighter: -0.03em;
--text-hero: 32px;
--text-hero-weight: 600;
```

---

## 5. File Impact Map

| File | Change Type | Scope |
|---|---|---|
| `sidebar.css` | **REWRITE** | Full replacement — new nav sidebar system |
| `sidebar.js` | **REWRITE** | New sidebar: nav items, expand/collapse, recents, mode toggle |
| `studio.css` | **MODIFY** | Add new tokens, update header, add agent panel, update timeline |
| `index.html` | **MAJOR MODIFY** | Restructure layout (sidebar + header + center + agent panel) |
| `studio.js` | **MODIFY** | Update layout state, add agent chat panel, skills system |
| `home.html` | **REWRITE** | Complete redesign to creative hub |
| `create.html` | **MAJOR MODIFY** | New prompt input bar, skills integration, gen preferences |
| `create.js` | **MODIFY** | Skills drawer logic, prompt tab-completion, gen prefs |
| `cockpit.html` | **MINOR MODIFY** | Adapt to new sidebar layout |
| `cockpit.js` | **MINOR** | Config loading adapted |
| `onboarding.html` | **MINOR MODIFY** | Adapt to new sidebar layout |
| `oven.html` | **MINOR MODIFY** | Adapt to new sidebar layout |
| `theme.js` | **NO CHANGE** | Theme system works as-is |

### New Files

| File | Purpose |
|---|---|
| `components/prompt-bar.js` | Universal prompt input component |
| `components/skills-drawer.js` | Skills browser + create-skill modal |
| `components/agent-panel.js` | Right-side conversational agent panel |
| `components/gen-prefs.js` | Generation preferences popover |
| `components/nav-sidebar.js` | New navigation sidebar (may replace `sidebar.js`) |

> **Note:** We stay vanilla HTML/JS/CSS — no build tooling. "Components" are ES6 modules or self-mounting IIFEs like the current `sidebar.js`.

---

## 6. What We Keep / Don't Adopt

### ✅ Keep from Current Pluto
- Obsidian Zinc color system — already Runway-aligned
- Zero-build vanilla stack — no React, no bundler
- GPU telemetry capsule — unique to Pluto, moves to overflow
- Command palette (⌘K) — powerful, stays in overflow
- Timeline architecture — solid NLE, just chrome polish
- Theme system — dark/light/system toggle stays
- All backend API endpoints — no backend changes

### ❌ Don't Adopt from Runway
- Runway's specific model names (Seedance, Aleph) — we use LTX terminology
- Credit-based billing UI — we're self-hosted, show GPU cost
- "Upgrade" button — not applicable for self-hosted

### 🔄 Adapt for Pluto
- Credits → GPU Cost meter
- "Upgrade" → "Launch GPU"
- Agent skills → Pluto capabilities (T2V, I2V, Upscale, Loop, Director)
- "New at Runway" → "New at MotionVector"

---

## 7. Implementation Strategy

### Branch Strategy

```
main
 └── feat/pluto-studio-redesign
      ├── Phase 1: Layout Foundation
      ├── Phase 2: Home + Prompt
      ├── Phase 3: Agent + Skills
      └── Phase 4: Polish + Integration
```

### Phase 1: Layout Foundation (~3-4 sessions)
1. Rewrite `sidebar.css` + `sidebar.js` — new nav sidebar
2. Simplify `studio-header` in `studio.css`
3. Update `index.html` layout — three-column grid
4. Update all pages to use new sidebar layout wrapper

### Phase 2: Home + Universal Prompt (~2-3 sessions)
1. Rewrite `home.html` — hero greeting, prompt bar, category tabs
2. Create `components/prompt-bar.js`
3. Create `components/gen-prefs.js`
4. Integrate prompt bar into `create.html`

### Phase 3: Agent Panel + Skills (~3-4 sessions)
1. Create `components/agent-panel.js`
2. Create `components/skills-drawer.js`
3. Add Create Skill modal
4. Wire skills to existing generation modes
5. Adapt AI Director to render inside agent panel

### Phase 4: Polish + Integration (~2-3 sessions)
1. Timeline polish — glassmorphism, tighter tracks
2. Recents system in sidebar
3. Transitions & micro-interactions
4. Responsive adjustments
5. Cross-page consistency pass
6. Regression testing

---

## 8. Risk & Mitigation

| Risk | Mitigation |
|---|---|
| Breaking existing generation workflows | Phase 1 is layout-only; test each phase independently |
| Large file sizes growing | Extract patterns into component modules |
| Sidebar conflicts with full-width timeline | Auto-collapse sidebar to icon rail when timeline active |
| Backend API changes needed | **None** — pure frontend redesign |
| Multi-page component sharing | Self-mounting IIFEs/ES6 modules via `<script>` tags |

---

## 9. Open Questions

1. **Sidebar pinning:** Persistent expanded, or hover-expand with pin toggle?
2. **Agent panel:** Always-visible on studio/create, or togglable?
3. **Skills:** Beyond T2V/I2V/Upscale/Loop/Director — other capabilities to surface?
4. **Credits vs. GPU cost:** Keep GPU spot pricing, or credit abstraction?
5. **"New Chat" concept:** Each generation as a "chat" (thread), or keep individual sessions?
