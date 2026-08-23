# Pluto Studio Architectural Audit & Implementation Plan

## 1. Executive Summary & Root Cause Audit

Following a deep-dive audit of `src/web_api.py`, `web/create.html`, `web/create.js`, `web/index.html`, and `web/app.css`, we have identified the root causes across the 4 reported issues:

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                         PLUTO STUDIO AUDIT & FINDINGS                            │
├──────────────────────────────────────────────────────────────────────────────────┤
│ 1. IMAGE UPLOAD & PERSISTENCE                                                    │
│    • Finding: Missing backend `/api/upload-image` endpoint.                     │
│    • Finding: `create.js` reads file into local dataURL but drops it from the    │
│      `/api/generate` POST request payload.                                       │
│                                                                                  │
│ 2. ASPECT RATIO & IMAGE KEYFRAME DISPLAY                                         │
│    • Finding: `.dropzone-preview` has hardcoded `height: 90px; object-fit: cover`│
│      which forcefully crops 9:16 portrait, 1:1 square, and 4:3 images.           │
│    • Finding: No natural aspect ratio detection (`naturalWidth / naturalHeight`). │
│                                                                                  │
│ 3. LTX DRAFT MODE VS PRO CINEMA MODE                                             │
│    • Finding: Absence of a Draft Mode toggle in the UI and API payload.          │
│    • Target: Draft Mode (15 steps, 768x432, ~4s generation, ~$0.01 compute) vs   │
│      Pro Cinema Mode (30 steps, 1024x576, full STG guidance, ~$0.04 compute).   │
│                                                                                  │
│ 4. STUDIO UI VIEWPORT & VERTICAL SCROLLING                                       │
│    • Finding: `body.obsidian-theme` enforced `overflow: hidden; height: 100vh;`  │
│      while fixed static heights in canvas, prompt bar, and timeline caused       │
│      overflow on standard laptop screens (<900px vertical height).               │
│    • Finding: Dead padding left wasted empty space on larger displays.           │
└──────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Implementation Blueprint

### Phase 1: Robust Image Upload & Aspect-Aware Dropzone
1. **Backend Endpoint (`src/web_api.py`)**:
   - Add `POST /api/upload-image` (and multipart form support):
     - Validates image MIME types (`image/jpeg`, `image/png`, `image/webp`).
     - Extracts image metadata (`natural_width`, `natural_height`, `aspect_ratio`).
     - Saves securely to `outputs/uploads/{job_id}_{filename}` preventing path traversal.
     - Returns `{ "image_path": str, "url": str, "width": int, "height": int, "aspect_ratio": "16:9" | "9:16" | "1:1" }`.
   - Update `POST /api/generate` to accept `image_path` and forward to LTX Image-to-Video pipeline.
2. **Frontend Dynamic Aspect Dropzone (`web/create.html` & `web/create.js`)**:
   - Replace fixed-height `.dropzone-preview` with a responsive letterboxed/pillarboxed container using `object-fit: contain` and max-height constraints.
   - Detect image dimensions on load: display an upfront badge `1080×1920 · 9:16 Vertical` and provide a 1-click **"Auto-match Aspect Ratio"** action.
   - Add a **"✕ Remove Image"** button to reset keyframe staging.
   - Upload file immediately or on generation trigger and attach `image_path` to the PatchCard payload.

---

### Phase 2: LTX Draft Mode vs Pro Mode
1. **Draft Mode Toggle**:
   - Add a 2-stage segmented control to `/create` and `/studio`:
     - ⚡ **Draft Mode**: 15 inference steps, fast preview (~4s), 768×432 resolution, compute quote: `~$0.01 (Draft Spot Compute)`.
     - 🎬 **Pro Cinema Mode**: 30 inference steps, 1024×576 (or 1080p), full STG guidance (0.8), compute quote: `~$0.04 (Full Master Compute)`.
2. **PatchCard & Engine Sync**:
   - Update PatchCard diff table to show `Engine Mode: Draft (15 steps)` vs `Pro Cinema (30 steps)` and dynamic compute quote.
   - Forward `draft_mode` and `steps` dynamically to `/api/generate`.

---

### Phase 3: Studio Viewport Space Optimization & Smooth Scrolling
1. **Adaptive 100vh Viewport Layout**:
   - Squeeze unnecessary padding in header (52px $\rightarrow$ 46px), filmstrip shelf, and prompt bar.
   - Make `.player-wrapper` dynamic:
     ```css
     .player-wrapper {
       max-height: calc(100vh - 330px);
       min-height: 180px;
       width: auto;
       max-width: 100%;
       aspect-ratio: 16 / 9;
     }
     ```
   - Ensure the Takes Filmstrip, Video Viewport, Transport Bar, Prompt Bar, and Timeline fit inside 100vh simultaneously without clipping or scrollbars.
2. **Graceful Scroll Fallback**:
   - For viewports $< 720\text{px}$ height or mobile/tablet windows, enable smooth `overflow-y: auto` on `.panel-main-viewport` and `.director-storyboard-view` so users can scroll naturally rather than getting cut off.
   - Allow sidebars (`.asset-bin-panel`, `.inspector-panel`) to fill available height with internal `.custom-scrollbar` scrollers.

---

## 3. Test-Driven Verification Plan
1. **API Unit Tests (`tests/test_web_api.py`)**:
   - Test `POST /api/upload-image` with valid PNG/JPEG and malicious filenames/traversals.
   - Test `POST /api/generate` with `image_path` and `draft_mode=True` (asserting 15 steps and draft quote).
2. **Frontend UI Tests (`tests/test_web_js.py`)**:
   - Test image dropzone aspect ratio calculation and draft mode toggle event handling.
   - Verify zero JS syntax errors and clean HTML escaping.
