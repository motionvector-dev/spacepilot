# Pluto Studio → React + Vite + Tailwind Migration Plan

## Current State

```
web/
├── index.html      (993 lines)   ← Studio main: Director + Vibe Editor
├── create.html     (1,832 lines) ← Create page
├── blueprint.html  (1,488 lines) ← Blueprint editor
├── cockpit.html    (996 lines)   ← GPU cockpit
├── home.html       (357 lines)   ← Landing
├── onboarding.html (482 lines)   ← Onboarding
├── oven.html       (650 lines)   ← Render queue
├── app.js       (1,977 lines, 54 functions) ← ALL studio logic
├── create.js       (1,347 lines)
├── cockpit.js      (845 lines)
├── sidebar.js      (607 lines)
├── theme.js        (84 lines)
├── app.css      (3,402 lines)
└── sidebar.css     (501 lines)
```

**Total**: ~15,500 lines, 0 components, 0 reactivity, 104 functions across 4 JS files.

---

## Component Tree

```
<App>
├── <AppShell>                          # Layout frame + router
│   ├── <Header>                        # Top bar (shared across all pages)
│   │   ├── <BrandLogo />
│   │   ├── <NavLinks />                # Home, Create, Cockpit, Studio
│   │   ├── <ProjectTitle />            # Editable input
│   │   ├── <ModeTabs />                # Director / Vibe Editor switcher
│   │   ├── <ThemeSwitcher />
│   │   ├── <CommandPalette />          # ⌘K modal
│   │   ├── <GpuTelemetry />            # Status dot, VRAM, cost
│   │   ├── <GpuLaunchButton />
│   │   └── <ExportButton />
│   │
│   ├── <Sidebar />                     # sidebar.js → component
│   │
│   └── <Outlet />                      # Page router
│       │
│       ├── 📄 /studio
│       │   ├── <DirectorView>              # AI Director mode
│       │   │   ├── <StoryboardHeroBar>
│       │   │   │   ├── <DirectorInput />   # Topic prompt
│       │   │   │   └── <TopicChips />      # Inspiration presets
│       │   │   ├── <StoryboardReel>
│       │   │   │   └── <SceneCard />       # × N scenes
│       │   │   │       ├── <KaTeXFormula />
│       │   │   │       ├── <TakeFilmstrip />
│       │   │   │       └── <SceneActions />
│       │   │   └── <BatchRenderBar />
│       │   │
│       │   └── <VibeEditorView>            # Vibe Editor mode
│       │       ├── <VideoCanvas>
│       │       │   ├── <CanvasViewport />   # 16:9 video + overlays
│       │       │   ├── <OverlayCard />      # Draggable glass card
│       │       │   └── <SafeGridOverlay />
│       │       ├── <InspectorPanel>
│       │       │   ├── <PromptEditor />
│       │       │   ├── <GenerationSettings /> # Duration, resolution, takes
│       │       │   ├── <ImageKeyframe />
│       │       │   └── <MotionVectorInspector />
│       │       │       ├── <FormulaEditor />
│       │       │       ├── <ColorSwatches />
│       │       │       └── <PositionPresets />
│       │       └── <AssetLibrary>
│       │           ├── <AssetFilters />
│       │           └── <AssetGrid />
│       │
│       ├── 📄 /create    → <CreatePage />
│       ├── 📄 /cockpit   → <CockpitPage />
│       ├── 📄 /blueprint → <BlueprintPage />
│       ├── 📄 /oven      → <OvenPage />       # Render queue
│       ├── 📄 /onboarding→ <OnboardingPage />
│       └── 📄 /           → <HomePage />
│
├── <Timeline>                          # Bottom dock (shared)
│   ├── <TimelineToolbar>
│   │   ├── <TransportControls />       # Play/pause, shuttle, JKL
│   │   ├── <SMPTETimecode />
│   │   └── <ZoomSlider />
│   ├── <TimelineRuler />
│   ├── <TimelineTrack type="v2" />     # Video plate
│   ├── <TimelineTrack type="v1" />     # MotionVector overlay
│   ├── <TimelineTrack type="audio" />  # Audio waveform
│   ├── <Playhead />
│   └── <InOutMarkers />
│
└── <ExportDrawer />                    # Slide-out export panel
```

---

## State Architecture (Zustand)

```typescript
// stores/studio.ts — replaces the global `let state = {...}`
interface StudioStore {
  // Active workspace
  activeMode: 'director' | 'vibe';
  
  // Generation
  isGenerating: boolean;
  engineMode: 'draft' | 'pro';
  duration: number;
  width: number;
  height: number;
  takesCount: number;
  
  // Playback & Timeline
  isPlaying: boolean;
  currentTime: number;
  timelineZoom: number;
  shuttleRate: number;
  inPoint: number | null;
  outPoint: number | null;
  
  // Assets
  assets: Asset[];
  activeAsset: Asset | null;
  
  // Storyboard
  storyboard: Storyboard | null;
  
  // Overlay / MotionVector
  overlayConfig: OverlayConfig;
  
  // Export
  exportConfig: ExportConfig;
}

// stores/gpu.ts — GPU lifecycle state
interface GpuStore {
  status: GpuStatus | null;
  isLaunching: boolean;
  launch: () => Promise<void>;
  terminate: () => Promise<void>;
  refresh: () => Promise<void>;
}
```

---

## Hooks (replaces raw fetch + polling)

```typescript
// hooks/useApi.ts
useAuthHeaders()          // replaces authHeaders()
useJobPoller(jobId)       // replaces pollJob() — auto-polls, returns status
useGpuStatus(interval)    // replaces refreshStatus() polling
useAssets(filter?)        // replaces refreshAssets() + filterAssets()

// hooks/useTimeline.ts
usePlayback()             // play/pause/shuttle/step/scrub
useTransport()            // JKL keyboard shortcuts
useInOutPoints()          // in/out mark management
```

---

## Migration Phases

### Phase 1: Scaffold (day 1)

```bash
# Inside pluto/
npm create vite@latest ui -- --template react-ts
cd ui
npm i react-router-dom zustand @tanstack/react-query tailwindcss @tailwindcss/vite
npm i -D @types/react @types/react-dom
```

- Port CSS variables from `app.css :root` → `tailwind.config.ts` theme tokens
- Set up Vite proxy to `localhost:8088` for API calls
- Add `pluto studio` to serve both API + Vite dev server

### Phase 2: Shell + Router (day 1-2)

- `<AppShell>`, `<Header>`, `<Sidebar>` — the chrome that's shared everywhere
- React Router with routes for all 7 pages
- `<GpuTelemetry>` widget (good first "real" component — isolated, polls API)

### Phase 3: Studio Page — Director Mode (day 2-3)

- Port `renderStoryboardScenes()` → `<SceneCard>` components
- `<DirectorInput>` + `<TopicChips>` (straightforward form)
- KaTeX rendering via `react-katex` or `useEffect` + KaTeX API
- Zustand store for storyboard state

### Phase 4: Studio Page — Vibe Editor (day 3-4)

- `<VideoCanvas>` with `<video>` element + overlay compositing
- `<InspectorPanel>` — the prompt/settings sidebar
- `<AssetLibrary>` grid with filtering
- Image keyframe upload

### Phase 5: Timeline (day 4-5)

- `<Timeline>` as a bottom-docked panel
- Canvas-rendered ruler + waveform (keep the canvas approach, it's correct for this)
- Transport controls with JKL keyboard bindings
- Scrubbing via pointer events

### Phase 6: Remaining Pages (day 5-6)

- `/create`, `/cockpit`, `/blueprint`, `/oven`, `/onboarding` — smaller pages
- `/cockpit` is mostly GPU telemetry + log streaming

### Phase 7: Cleanup

- Remove `web/` directory
- Update `web_api.py` to serve Vite build output from `ui/dist/`
- Delete legacy HTML/JS/CSS

---

## Key Decisions

| Decision | Recommendation | Why |
|----------|---------------|-----|
| **State management** | Zustand | Tiny API, no boilerplate, works great with React 18+. Overkill to use Redux for this. |
| **Data fetching** | TanStack Query | Caching, polling, optimistic updates — replaces all your manual `fetch` + `setInterval` patterns |
| **Styling** | Tailwind v4 | Your DESIGN.md tokens map directly to a Tailwind theme. Eliminates the 3,400-line CSS file. |
| **Timeline rendering** | Canvas + React wrapper | DOM-based timelines don't scale. Keep canvas for ruler/waveform, React for controls. |
| **KaTeX** | `react-katex` package | Drop-in, replaces manual `katex.render()` calls |
| **Routing** | React Router v7 | You have 7 pages, need a real router. Currently served as separate HTML files. |

> [!TIP]
> **Agentic benefit**: With this structure, an agent can be told "add a batch render progress bar to `<SceneCard>`" and it knows exactly which file to edit. Today it has to parse a 1,000-line HTML blob and a 2,000-line JS file to find the right spot.
