# SpacePilot Backend Engineering Handoff
**Document Version**: 2.0.0 (Post-Modular Refactor)  
**Repository**: `motionvector-dev/pluto`  
**Status**: Current — describes the layout live on `main`
**Verified**: 2026-08-22, by reading `src/pluto/api/routes/` (14 modules present)
**Origin branch**: `feat/backend-modular-refactor` (PR #9) — **merged**, no longer a worktree branch
**Note**: this file existed only as an untracked file in the primary checkout until 2026-08-22. It is now committed.  
**Legacy Fallback Directory**: `/Users/saurabh/code/motionvector/pluto/studio_backup_original/`  
**Local Test Port**: `http://127.0.0.1:8080` (or `http://spacepilot.localhost:8088`)

---

## 1. Architecture & Package Structure

The legacy monolith in `src/studio_api.py` has been refactored into the structured, extensible `src.pluto` package layout while preserving 100% backwards compatibility for existing imports and CLI tools:

```
pluto/
├── src/
│   ├── pluto/                        # New modular package
│   │   ├── __init__.py
│   │   ├── app.py                    # FastAPI application factory (create_app)
│   │   ├── core/
│   │   │   ├── config.py             # Pydantic Settings & environment discovery
│   │   │   └── utils.py              # FFmpeg runners, safe write_meta, discard_partial
│   │   ├── services/
│   │   │   ├── audio.py              # Kokoro-82M ONNX TTS & -16 LUFS EBU R128 loudnorm
│   │   │   ├── generation.py         # LTX-2.5 daemon dispatcher, multi-take seed generator
│   │   │   ├── gpu_lifecycle.py      # SkyPilot spot broker, instance probe cache
│   │   │   ├── image_utils.py        # Aspect ratio parser, MIME sanitization
│   │   │   └── watchdog.py           # 30-minute idle auto-shutdown loop
│   │   └── api/
│   │       ├── deps.py               # Token auth (require_token) & activity timestamps
│   │       └── routes/
│   │           ├── health.py         # /healthz, /api/token, /api/status, /api/live-reload
│   │           ├── generate.py       # /api/generate, /api/jobs/{id}, /api/enhance-prompt
│   │           ├── compute.py        # /api/compute/models/download, cache info
│   │           ├── engines.py        # /api/generate/multi-engine (Wan2.1, Hunyuan, LTX)
│   │           ├── audio.py          # /api/audio/synthesize-local, /api/audio/mix-ducked
│   │           ├── storyboard.py     # /api/narrative/decompose-local
│   │           ├── gpu.py            # /api/gpu/launch, /api/gpu/terminate, spot failover
│   │           ├── assets.py         # /api/assets/list, /api/assets/delete
│   │           └── views.py          # Static files & /ws/cockpit Web SSH PTY bridge
│   ├── studio_api.py                 # Backwards-compatible facade importing from src.pluto
│   ├── cli.py                        # spacepilot CLI entrypoint
│   └── skypilot_orchestrator.py      # SkyPilot YAML generator & spot broker
├── tests/                            # 142 Pytest unit & integration tests
└── studio/                           # Legacy HTML files (also backed up in studio_backup_original/)
```

---

## 2. Key API Endpoints & Request Schemas

### A. Video Generation (`/api/generate`)
* **Method**: `POST`
* **Auth**: `X-Pluto-Token` (or session cookie)
* **Pydantic Model**: `GenerateRequest` in `src/pluto/services/generation.py`
```json
{
  "prompt": "Cyberpunk rainy alleyway, anamorphic reflections, 35mm cinematic drift",
  "negative_prompt": "blurry, jittery, low quality, artifacts",
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
  "image_path": "/path/to/first_frame.png",       // Optional for I2V
  "last_image_path": "/path/to/last_frame.png"    // Optional for FLF2V Morphing
}
```

### B. Job Status Polling (`/api/jobs/{job_id}`)
* **Method**: `GET`
* **Response**:
```json
{
  "job_id": "pluto_89abf012de",
  "status": "completed",
  "progress": 100,
  "takes": [
    { "id": 1, "seed": 42801, "video_url": "/outputs/pluto_89abf012de_take1.mp4", "pan_deg": 15, "zoom_ratio": 1.4 },
    { "id": 2, "seed": 42802, "video_url": "/outputs/pluto_89abf012de_take2.mp4", "pan_deg": 15, "zoom_ratio": 1.4 }
  ]
}
```

### C. In-Process Kokoro Voiceover (`/api/audio/synthesize-local`)
* **Method**: `POST`
* **Pydantic Model**: `LocalSynthesizeAudioRequest`
```json
{
  "text": "SpacePilot pilots your generative cinema with zero cold start.",
  "voice": "af_bella",
  "speed": 1.0,
  "target_lufs": -16.0
}
```

### D. Single-Flight GPU Status (`/api/status` & `/api/gpu/status`)
* **Method**: `GET` (Non-blocking, cached single-flight probe)
* **Response**:
```json
{
  "instance": "g6e.xlarge",
  "provider": "aws_spot",
  "gpu_online": true,
  "worker_ready": true,
  "vram_used_gb": 18.4,
  "vram_total_gb": 48.0,
  "gpu_utilization": 64.2,
  "hourly_cost_usd": 0.75,
  "uptime_minutes": 24.5,
  "dead_man_timeout_seconds": 1530
}
```

### E. Web SSH PTY WebSocket Bridge (`/ws/cockpit`)
* **Protocol**: `WebSocket`
* **Behavior**: Bridges remote SSH / local PTY session using xterm.js binary terminal protocol.

---

## 3. Open PR Inventory (Backend & Infrastructure)

| PR # | Branch | Summary |
| :---: | :--- | :--- |
| **#9** | `feat/backend-modular-refactor` | Core package reorganization into `src/pluto` with zero regressions. |
| **#10** | `feat/lora-studio-engine` | 1-Click PEFT LoRA fine-tuning runner and dynamic adapter hot-swap registry. |
| **#11** | `feat/model-recipes-importer` | Wan2.1, HunyuanVideo, DeepSeek-R1, and Qwen2.5-VL download recipes. |
| **#12** | `feat/polar-x402-payments` | Polar.sh webhook reconciliation and agent micropayments engine. |
| **#13** | `feat/checkpoint-r2-sync` | Spot preemption-resilient training checkpoints with Cloudflare R2 auto-resume. |
| **#15** | `feat/cli-doctor-serve` | SpacePilot CLI `doctor` diagnostic HUD and `serve` command. |

---

## 4. Immediate Action Item for Backend Session

* **Test Compatibility Import Fix**:
  In `src/studio_api.py`, ensure `require_token` is explicitly imported from `src.pluto.api.deps` so legacy tests in `tests/test_studio_api.py` pass cleanly:
  ```python
  from src.pluto.api.deps import require_token, update_activity
  ```
* **Command to Run Tests**:
  ```bash
  python3 -m pytest tests/ -v
  ```
* **Command to Start Backend**:
  ```bash
  python3 -m uvicorn src.studio_api:create_app --factory --port 8080 --host 0.0.0.0
  ```
