# Antigravity Developer Agents Setup & Architecture

This document tracks the background agent workflows, collaborative task splits, and optimizations implemented during the setup and tuning of the Katana AI Video Generator.

---

## 1. Collaborative Agent Workflow

To accelerate development and prevent file write conflicts, tasks were distributed across three specialized agent domains:

```
                  ┌───────────────────────┐
                  │   Parent Agent: CLI   │
                  │ (Coordinator / Router)│
                  └───────────┬───────────┘
                              │
             ┌────────────────┴────────────────┐
             ▼                                 ▼
 ┌───────────────────────┐         ┌───────────────────────┐
 │ FastAPI Backend Dev   │         │   Vue Frontend Dev    │
 │ (Subagent f3b22e8a)   │         │ (Subagent 7eb38636)   │
 └───────────────────────┘         └───────────────────────┘
```

### Agent Roles & Responsibilities

1. **Parent CLI Coordinator**:
   - Manages uvicorn and vite background task lifetimes.
   - Monitors HuggingFace cache sizes and TCP connection pools.
   - Creates the Tailscale SSH local port-forwarding tunnel.
   - Routinely inspects local ports (`8000`, `3001`, `11434`) and handles runtime errors.
2. **FastAPI Backend Agent (`f3b22e8a`)**:
   - Initialized the Python FastAPI `server.py` bridge.
   - Refactored pipeline initialization to leverage `enable_model_cpu_offload` under MPS.
   - Created the serialized asyncio lock to prevent GPU thread collisions.
3. **Vue Frontend Agent (`7eb38636`)**:
   - Built the V2 user interface route (`VideoGenV2.vue`).
   - Integrated backdrop-filter blurred overlays and active style cards.
   - Programmed the Cloud Upscale handoff animation (`upscaleVideo`).

---

## 2. VRAM & Compute Optimization Strategies

Running a 13-Billion parameter video model (LTX-Video) concurrently with a language model (Qwen 2.5) on a 32 GB unified memory M1 Max required key architectural modifications:

| Constraint | Problem | Mitigation Strategy |
| :--- | :--- | :--- |
| **Swapping & Thrashing** | Qwen (1.5B) + LTX (13B) loaded in Python memory exceeded 32 GB RAM. | Completely disabled local Qwen execution. Offloaded language modeling to a remote Tailscale-networked Lenovo server. |
| **GPU Component Overhead** | Raw `.to("mps")` loading of LTX components exhausted GPU VRAM. | Implemented `enable_model_cpu_offload(device="mps")`. Components are held in system RAM and loaded to GPU on-demand. |
| **Concurrent Generation OOM** | Concurrently executing multiple generation calls doubled VRAM spikes. | Implemented an async `asyncio.Lock` to block concurrent requests, placing them into a FIFO queue. |
| **Network Startup Delays** | Hugging Face snapshot validations on startup caused uvicorn timeouts. | Enabled `HF_TOKEN` validation for authenticated CDN requests. Configured a `MOCK_VIDEO` environment flag for instantaneous UI/UX testing. |

---

## 3. Ollama SSH Local Port Forwarding

To enable remote language model calls without security/network overhead:
- **Challenge**: The remote Ollama daemon was configured strictly to listen on local interface `127.0.0.1:11434` inside the Lenovo box.
- **Solution**: Established a local SSH port forwarding tunnel:
  ```bash
  ssh -N -L 11434:127.0.0.1:11434 lenovo &
  ```
- **Fallback**: Written a fail-safe urllib fetch handler inside `/enhance` that cleanly prints tunnel timeouts and resumes rule-based prompt enhancement locally, preventing server-side downtime.

---

## 4. AWS EC2 Cloud GPU Migration (July 2026)

To fully resolve Apple Silicon GPU execution lag, the backend is transitioning to a dedicated AWS EC2 `g5.xlarge` (A10G GPU, 24GB VRAM) instance in **`us-east-1` (N. Virginia)**.

### Billing Security & Guardrails
*   **Daily Budget safety net**: Established a `$3.00/day` budget alert triggering email notifications to prevent overnight runaway GPU compute billing.
*   **Monthly Budget ceiling**: Active at `$100.00/month` tracking resources tagged with `CreatedBy=antigravity-dev-user`.
*   **Restricted IAM Profile**: Created `antigravity-dev-user` credentials profile locally, restricted strictly to EC2, VPC, and Service Quota operations.
*   **Private naming policy**: All resources named under the `pluto-` prefix (e.g. `pluto-gpu-sg`, `pluto-gpu-key`) to maintain account privacy.

### Code & Plumbing Preparation
*   **Vite Env Injection**: Replaced hardcoded `localhost:8001` URLs in `VideoGen.vue` and `VideoGenV2.vue` with `import.meta.env.VITE_VIDEO_API_URL`.
*   **CUDA & Health Check support**: Refactored `server.py` to auto-detect best available hardware (CUDA/MPS/CPU), utilize FP16 precision on NVIDIA devices, and added a `GET /health` endpoint for remote reachability checks.
*   **Vite Dev Server**: Active on port `3002`.

