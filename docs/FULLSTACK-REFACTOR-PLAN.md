# Pluto Full-Stack Refactor Plan

> Vanilla monolith → production-grade, agent-friendly architecture

**Status**: 📋 Planning  
**Author**: Antigravity Audit  
**Date**: 2026-08-21  

---

## Current State Summary

| Layer | Files | Lines | Problem |
|-------|-------|-------|---------|
| **Backend** | 13 loose `.py` in `src/` | 6,023 | `studio_api.py` is 2,577 lines. No package, no service layer, no schemas module. |
| **Frontend** | 14 files in `studio/` | 15,561 | Vanilla JS, no components, no reactivity, no build step. |
| **Infra/DX** | `requirements.txt` + shell scripts | — | No lockfile, no `pyproject.toml`, loose mp4s in root. |
| **Tests** | 8 test files | 42 tests | ✅ Solid coverage — preserve this. |

---

## Quality Assurance & Zero-Regression Strategy

To guarantee zero breakage, this refactor follows a **surgical extraction** approach rather than a blind rewrite from scratch:

1. **Logic Preservation (Lift & Shift)**:
   - All critical domain logic (ffmpeg flags, 2-pass `loudnorm` audio normalization, ProRes 422 mastering, Kokoro ONNX voice generation, and SkyPilot/GPU token handshakes) remains 100% byte-for-byte identical.
   - Only the structural wiring changes (FastAPI `APIRouter`, Pydantic `Settings`, and dependency injection).

2. **Step-by-Step TDD Gate**:
   - Establish baseline with `pytest` across all 42 tests before touching any code.
   - Extract **one module at a time** (e.g. `audio.py` first) and immediately run its specific test suite (e.g. `pytest tests/test_audio_api.py`).
   - No module is committed until 100% of corresponding tests pass without altering test assertions.

3. **Parallel Strangler Fig Pattern (Zero UI Downtime)**:
   - The existing `studio/` vanilla UI remains live and fully functional throughout development.
   - The new React + Vite app is developed under `ui/`, hitting the exact same backend endpoints in parallel.
   - We only cut over to the new frontend once all features, canvas interactions, and keyboard shortcuts (JKL, ⌘K) match the baseline.


---

## Phase 1: Backend Restructure (days 1–3)

### 1A. Python Package Layout

```
src/pluto/
├── __init__.py
├── app.py                    ← FastAPI app factory
│
├── api/
│   ├── __init__.py
│   ├── deps.py               ← shared deps (auth, token validation, output dirs)
│   └── routes/
│       ├── __init__.py
│       ├── generate.py        ← POST /api/generate
│       ├── assets.py          ← GET /api/assets, /api/media/{file}
│       ├── gpu.py             ← POST /api/gpu/launch, /terminate, GET /api/status
│       ├── audio.py           ← POST /api/generate/music, /voice
│       ├── composite.py       ← POST /api/composite-motionvector, /upscale-4k
│       ├── storyboard.py      ← POST /api/storyboard/generate
│       ├── jobs.py            ← GET /api/jobs/{id}
│       └── health.py          ← GET /healthz, /api/token
│
├── core/
│   ├── __init__.py
│   ├── config.py              ← pydantic-settings: all env vars in one typed class
│   ├── schemas.py             ← shared Pydantic models (Job, Asset, GpuStatus, etc.)
│   └── exceptions.py          ← custom exception classes + FastAPI handlers
│
├── services/
│   ├── __init__.py
│   ├── generation.py          ← video generation orchestration
│   ├── audio.py               ← music (MLX proxy) + voice (Kokoro)
│   ├── gpu_lifecycle.py       ← launch/terminate/status for spot instances
│   ├── storyboard.py          ← AI storyboard decomposition
│   ├── upscale.py             ← 4K upscale + composite pipeline
│   └── job_manager.py         ← async job tracking (replaces in-memory dict)
│
├── workers/
│   ├── __init__.py
│   ├── ltx_worker.py          ← GPU-side Flask worker (unchanged, runs on EC2)
│   └── skypilot.py            ← SkyPilot orchestration
│
├── mcp/
│   ├── __init__.py
│   └── server.py              ← FastMCP server
│
└── cli/
    ├── __init__.py
    └── main.py                ← CLI entrypoint
```

### 1B. Key Refactors

**Split `studio_api.py` (2,577 lines) → routes + services:**

| Current function cluster | Target module |
|--------------------------|---------------|
| `/api/generate` handler + job polling | `routes/generate.py` + `services/generation.py` |
| `/api/generate/music`, `/voice` | `routes/audio.py` + `services/audio.py` |
| `/api/gpu/launch`, `/terminate`, `/api/status` | `routes/gpu.py` + `services/gpu_lifecycle.py` |
| `/api/assets`, `/api/media/*` | `routes/assets.py` |
| `/api/composite-motionvector`, `/upscale-4k` | `routes/composite.py` + `services/upscale.py` |
| Token auth, CORS, static file serving | `api/deps.py` + `app.py` |
| Job dict, background tasks | `services/job_manager.py` |

**Config consolidation** — scattered `os.getenv()` calls → one `Settings` class:

```python
# core/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    pluto_outputs_dir: str = "./outputs"
    local_worker_token: str
    pluto_kokoro_model: str | None = None
    pluto_kokoro_voices: str | None = None
    mlx_music_url: str = "http://127.0.0.1:11234"
    gpu_instance_type: str = "g6e.2xlarge"

    class Config:
        env_file = ".env"
```

**App factory** — testable, no import side effects:

```python
# app.py
def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    app = FastAPI(title="Pluto Studio")
    app.state.settings = settings
    app.include_router(generate_router, prefix="/api")
    app.include_router(audio_router, prefix="/api")
    return app
```

### 1C. Delete / Archive

- `src/server.py` — marked "legacy" in README. Archive or delete.
- `src/produce_welch_master.py` — superseded by opus version? Confirm and archive.
- Root `output_*.mp4` files — gitignore and delete from tree.

---

## Phase 2: Packaging & DX (days 3–4)

### 2A. `pyproject.toml`

```toml
[project]
name = "pluto"
version = "2.5.0"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.100.0,<1.0",
    "uvicorn>=0.22.0",
    "pydantic>=2.0",
    "pydantic-settings>=2.0",
]

[project.scripts]
pluto = "pluto.cli.main:main"
spacepilot = "pluto.cli.main:main"

[project.optional-dependencies]
gpu = ["torch>=2.1.0", "transformers>=4.36.0", "diffusers>=0.25.0", "accelerate>=0.25.0"]
voice = ["kokoro-onnx"]
dev = ["pytest", "httpx", "ruff"]
```

### 2B. Dependency Pinning

```bash
pip install uv
uv pip compile pyproject.toml -o requirements.lock
```

### 2C. Linting & Formatting

```bash
ruff check src/ tests/
ruff format src/ tests/
```

---

## Phase 3: Frontend Migration (days 4–10)

### 3A. Stack

| Concern | Choice | Rationale |
|---------|--------|-----------|
| Framework | React 19 + TypeScript | Best agent/tooling ecosystem |
| Build | Vite 6 | Fast HMR, trivial proxy to FastAPI |
| State | Zustand | Tiny, no boilerplate. 3 stores replace one global `let state` |
| Data fetching | TanStack Query v5 | Replaces manual `fetch` + `setInterval` polling |
| Styling | Tailwind v4 | DESIGN.md tokens map 1:1 to theme config |
| Routing | React Router v7 | 7 pages need a real router |
| Math | `react-katex` | Replaces manual `katex.render()` calls |
| Timeline | Canvas + React shell | Ruler and waveform stay canvas-rendered |

### 3B. Component Tree

```
<App>
├── <AppShell>
│   ├── <Header>
│   │   ├── <BrandLogo />
│   │   ├── <NavLinks />
│   │   ├── <ProjectTitle />
│   │   ├── <ModeTabs />
│   │   ├── <ThemeSwitcher />
│   │   ├── <CommandPalette />
│   │   ├── <GpuTelemetry />
│   │   ├── <GpuLaunchButton />
│   │   └── <ExportButton />
│   ├── <Sidebar />
│   └── <Outlet />            ← page router
│       ├── /studio
│       │   ├── <DirectorView>
│       │   │   ├── <StoryboardHeroBar>
│       │   │   ├── <StoryboardReel>
│       │   │   │   └── <SceneCard /> × N
│       │   │   └── <BatchRenderBar />
│       │   └── <VibeEditorView>
│       │       ├── <VideoCanvas>
│       │       ├── <InspectorPanel>
│       │       └── <AssetLibrary>
│       ├── /create    → <CreatePage />
│       ├── /cockpit   → <CockpitPage />
│       ├── /blueprint → <BlueprintPage />
│       ├── /oven      → <OvenPage />
│       ├── /onboarding→ <OnboardingPage />
│       └── /          → <HomePage />
├── <Timeline>
│   ├── <TransportControls />
│   ├── <SMPTETimecode />
│   ├── <TimelineRuler />     ← canvas
│   ├── <TimelineTrack /> × 3
│   ├── <Playhead />
│   └── <InOutMarkers />
└── <ExportDrawer />
```

### 3C. State Architecture (Zustand)

```typescript
// stores/studio.ts
interface StudioStore {
  activeMode: 'director' | 'vibe';
  isGenerating: boolean;
  engineMode: 'draft' | 'pro';
  duration: number;
  width: number;
  height: number;
  takesCount: number;
  assets: Asset[];
  activeAsset: Asset | null;
  storyboard: Storyboard | null;
  overlayConfig: OverlayConfig;
  exportConfig: ExportConfig;
}

// stores/gpu.ts
interface GpuStore {
  status: GpuStatus | null;
  isLaunching: boolean;
  launch: () => Promise<void>;
  terminate: () => Promise<void>;
}

// stores/timeline.ts
interface TimelineStore {
  isPlaying: boolean;
  currentTime: number;
  timelineZoom: number;
  shuttleRate: number;
  inPoint: number | null;
  outPoint: number | null;
}
```

### 3D. Migration Sequence

| Sub-phase | Days | Deliverable |
|-----------|------|-------------|
| Scaffold + Tailwind theme | 4 | Vite project, proxy, design tokens |
| Shell + Router | 4–5 | AppShell, Header, Sidebar, all routes |
| Director Mode | 5–6 | Storyboard, scene cards, KaTeX |
| Vibe Editor | 6–7 | Canvas, inspector, asset library |
| Timeline | 7–8 | Transport, ruler, waveform, scrubbing |
| Remaining pages | 8–9 | Create, Cockpit, Blueprint, Oven |
| Cutover | 10 | Delete `studio/`, serve from `ui/dist/` |

### 3E. Project Structure

```
pluto/ui/
├── src/
│   ├── components/
│   │   ├── layout/       (AppShell, Header, Sidebar)
│   │   ├── studio/       (DirectorView, SceneCard, VibeEditor, Canvas, Inspector)
│   │   ├── timeline/     (Timeline, Track, Transport, Ruler)
│   │   ├── gpu/          (Telemetry, LaunchButton)
│   │   └── shared/       (CommandPalette, ExportDrawer, ThemeSwitcher)
│   ├── stores/           (studio.ts, gpu.ts, timeline.ts)
│   ├── hooks/            (useApi, useJobPoller, useGpuStatus, usePlayback, useKeyboard)
│   ├── lib/              (api.ts, smpte.ts)
│   ├── pages/            (7 page components)
│   └── styles/           (globals.css with Tailwind + custom tokens)
├── tailwind.config.ts
├── vite.config.ts
└── package.json
```

---

## Phase 4: Agentic & Production Readiness (days 10–14)

### 4A. Event-Driven Jobs

Replace polling with **Server-Sent Events (SSE)**:

```python
@router.get("/api/jobs/{job_id}/stream")
async def stream_job(job_id: str):
    async def event_generator():
        while True:
            job = job_manager.get(job_id)
            yield {"data": job.model_dump_json()}
            if job.status in ("completed", "failed"):
                break
            await asyncio.sleep(1)
    return EventSourceResponse(event_generator())
```

### 4B. Expanded MCP Tools

Each service module becomes an MCP tool:

- `generate_video`, `generate_storyboard`
- `gpu_launch`, `gpu_status`, `gpu_terminate`
- `list_assets`
- `generate_voice`, `generate_music`
- `export_master`

### 4C. Observability

OpenTelemetry instrumentation on FastAPI + service calls for structured tracing.

### 4D. Structured Error Responses

```python
class PlutoError(Exception):
    def __init__(self, message: str, code: str, status: int = 400):
        self.message = message
        self.code = code
        self.status = status

# Returns: {"error": {"code": "GPU_NOT_RUNNING", "message": "..."}}
```

---

## Execution Dependencies

```
Phase 1 (Backend)           Phase 3 (Frontend)
    │                            │
    ├── 1A: Package layout       │    ← can run in parallel
    ├── 1B: Split studio_api     │
    ├── 1C: Cleanup              │
    │                            │
Phase 2 (DX)                     │
    ├── 2A: pyproject.toml       ├── 3A-3E: Build UI
    ├── 2B: Lock deps            ├── 3F: Cutover
    ├── 2C: Linting              │
    │                            │
Phase 4 (Production)  ← depends on Phase 1 + 3
    ├── 4A: SSE jobs
    ├── 4B: MCP expansion
    ├── 4C: Observability
    └── 4D: Structured errors
```

> **Phases 1–2 and 3 can run in parallel.** The API surface doesn't change — just the internal organization.

> **Highest ROI single change**: Split `studio_api.py`. Even alone, going from 1×2,577 lines to 8×~300 lines makes every future change dramatically easier.
