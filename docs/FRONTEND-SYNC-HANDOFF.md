# SpacePilot Frontend-to-Backend Integration Handoff
**Document Version:** 2.0.0  
**Target Repository:** `motionvector-dev/pluto`  
**Backend Branch:** `feat/backend-modular-refactor` (PR #9)  
**Frontend Branch:** `feat/frontend-react-ui` (PR #14)  
**Backend Base URL:** `http://localhost:8088` (or `http://spacepilot.localhost:8088`)  

---

## 1. Network, Ports & Vite Proxy Configuration

The backend is running the modular FastAPI engine on port `8088`. CORS is configured for `localhost`, `127.0.0.1`, `spacepilot.localhost`, and `pluto.localhost` across all ports.

### Recommended `vite.config.ts` Proxy Settings
In `ui/vite.config.ts`, forward all `/api`, `/outputs`, and WebSocket `/ws` traffic to the backend:

```typescript
// ui/vite.config.ts
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8088',
        changeOrigin: true,
      },
      '/outputs': {
        target: 'http://127.0.0.1:8088',
        changeOrigin: true,
      },
      '/ws': {
        target: 'ws://127.0.0.1:8088',
        ws: true,
      },
    },
  },
});
```

---

## 2. Authentication & Token Handshake

All mutating endpoints (`POST /api/generate`, `POST /api/gpu/launch`, `POST /api/lora/train`, etc.) require an admin token in the header:

```http
X-Pluto-Token: <token>
```

### Initial Token Bootstrap
When the React UI initializes, fetch the session token on local loopback:
```typescript
const res = await fetch('/api/token');
const { token } = await res.json();
// Store token in memory / sessionStorage for subsequent API calls
```

---

## 3. Core API Route Contracts

### A. Video Generation & 2×2 Director Take Grid
* **Trigger Generation**: `POST /api/generate`
  ```json
  {
    "prompt": "Cinematic drift down neon rain street, anamorphic lens flare",
    "negative_prompt": "blurry, jittery, low quality",
    "seconds": 4.0,
    "width": 1280,
    "height": 720,
    "seed": 42801,
    "takes": 4,
    "enhance": true,
    "draft_mode": false,
    "camera_pan": "right",
    "camera_tilt": "up",
    "camera_zoom": "in",
    "camera_intensity": 3,
    "image_path": null
  }
  ```
  **Response**: `200 OK` $\rightarrow$ `{ "job_id": "pluto_take_98ab", "status": "processing" }`

* **Job Polling**: `GET /api/jobs/{job_id}`
  **Response**:
  ```json
  {
    "job_id": "pluto_take_98ab",
    "status": "completed",
    "progress": 100,
    "takes": [
      { "id": 1, "seed": 42801, "video_url": "/outputs/pluto_take_98ab_take1.mp4", "pan_deg": 15 },
      { "id": 2, "seed": 42802, "video_url": "/outputs/pluto_take_98ab_take2.mp4", "pan_deg": 15 },
      { "id": 3, "seed": 42803, "video_url": "/outputs/pluto_take_98ab_take3.mp4", "pan_deg": 15 },
      { "id": 4, "seed": 42804, "video_url": "/outputs/pluto_take_98ab_take4.mp4", "pan_deg": 15 }
    ]
  }
  ```

---

### B. In-Process Kokoro TTS Voiceover
* **Endpoint**: `POST /api/audio/synthesize-local`
* **Request**:
  ```json
  {
    "text": "SpacePilot orchestrates DiT video generation with local audio synthesis.",
    "voice": "af_heart",
    "speed": 1.0,
    "target_lufs": -16.0
  }
  ```
* **Response**:
  ```json
  {
    "audio_url": "/outputs/audio_synth_1234.wav",
    "duration_sec": 3.8,
    "lufs": -16.0
  }
  ```

---

### C. Cockpit Spot GPU Telemetry & SSE Logs
* **Telemetry**: `GET /api/cockpit/status`
  ```json
  {
    "instance": { "id": "i-09abf12", "type": "g6e.xlarge", "ip": "54.210.12.44", "state": "running" },
    "gpu_online": true,
    "worker_ready": true,
    "vram_used_gb": 18.2,
    "vram_total_gb": 48.0,
    "uptime_minutes": 14.5,
    "estimated_cost_usd": 0.18,
    "watchdog": { "elapsed_mins": 2.1 }
  }
  ```
* **Live SSE Log Stream**: `GET /api/gpu/logs/stream`
  - Connect with `new EventSource('/api/gpu/logs/stream')` for terminal streaming.
* **WebSocket PTY Shell**: `ws://localhost:8088/ws/cockpit`
  - Attach directly to xterm.js via `WebSocket`.

---

### D. Wave Feature Extensions

#### 1. 1-Click LoRA Studio (PR #10)
* `GET /api/lora/adapters`: List trained/installed LoRA adapters.
* `POST /api/lora/train`: Start background training job (`{ "target_model": "wan-2.1", "rank": 16, "steps": 500 }`).
* `GET /api/lora/train/{job_id}`: Poll training progress and progressive loss telemetry array.

#### 2. Top Model Leaderboard Recipes (PR #11)
* `GET /api/compute/recipes`: List models (Wan2.1, Hunyuan, DeepSeek, Qwen) enriched with `is_local_runnable: boolean` matching host VRAM.
* `POST /api/compute/recipes/{id}/download`: Queue background weight download.
* `GET /api/compute/recipes/{id}/progress`: Download percentage, ETA, and speed metrics.

#### 3. Polar.sh Billing & Micropayments (PR #12)
* `GET /api/billing/usage`: Active subscription tier, remaining generation credits, and per-engine rate cards.
* `POST /api/billing/x402/verify`: Cryptographic payment verification for autonomous agents paying in USDC.

#### 4. Spot Checkpoint Sync & Auto-Resume (PR #13)
* `GET /api/checkpoints/snapshots`: List available multi-cloud restore points.
* `POST /api/checkpoints/restore/{id}`: Trigger preemption restore.

---

## 4. Static Asset Delivery

Generated video takes, audio wavs, and composite plates are saved to `outputs/` and served directly over HTTP:
- Direct video URLs: `/outputs/<filename>.mp4`
- Asset library listing: `GET /api/assets/list`
- Asset deletion: `DELETE /api/assets/delete` with `{ "filename": "<filename>.mp4" }`
