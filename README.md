# SpacePilot 🚀 (Pluto Engine)

> **"SkyPilot pilots your cloud servers. SpacePilot pilots your generative cinema."**

**SpacePilot** is the high-performance generative cinema workstation and zero-markup compute broker for macOS Apple Silicon. A zero-build studio web UI (`/create`, `/cockpit`, `/studio`), native FastMCP server, and CLI on the Mac, backed by a resident Quantized LTX-2.5 diffusion worker on AWS/Shadeform/RunPod spot GPUs ($0.012/take instead of 20x SaaS subscription markups).

Four core engines power SpacePilot:

| Component | What it is |
| --- | --- |
| `src/studio_api.py` | SpacePilot Studio backend & Web UI (FastAPI on `127.0.0.1:8000` / `:8088`). |
| `src/pluto_mcp_server.py` | Native FastMCP Server exposing generative cinema tools to Claude, Cursor & Antigravity. |
| `src/cli.py` (`bin/pluto` / `spacepilot`) | GPU lifecycle, deploys, generation, log streaming, and Spot arbitrage. |
| `src/ltx_worker.py` | PyTorch resident worker holding Quantized Float8 LTX-2.5 warm in 48GB VRAM (0.0s cold start). |


---

## Setup

```bash
conda env create -f environment.yml     # or: python -m venv .venv
pip install -r requirements.txt
```

Secrets come from Doppler, project `unfoundbox`, config `dev_personal`. The
scope is set at `~/code`, so it resolves here with no per-repo setup — verify
with `doppler configure`, then prefix commands with `doppler run --`.

**`LOCAL_WORKER_TOKEN` is required.** The GPU worker exits rather than start
without it, and `pluto launch` refuses to start a billing instance it could not
then deploy to. If it isn't in Doppler yet:

```bash
doppler secrets set LOCAL_WORKER_TOKEN="$(openssl rand -hex 32)"
```

See `.env.example` for every variable the code reads.

---

## Running the studio

```bash
doppler run -- ./bin/pluto studio        # or: python src/studio_api.py
```

Serves the UI and API on <http://localhost:8088>, bound to loopback only. LAN
access would need both the bind address and the CORS allowlist changed.

`bin/pluto` runs the CLI under bare `python3`, which usually lacks fastapi, so
the studio subprocess resolves its own interpreter: `PLUTO_PYTHON`, then
`python_bin` in `.pluto_config.json` (gitignored, machine-local), then
`sys.executable`. If none can import fastapi it says so instead of dying quietly.

---

## API

Everything that spends compute or money requires the session token in an
`X-Pluto-Token` header. Read-only routes are open. The UI fetches the token
itself; from a shell, `GET /api/token` or read `.studio_token`.

| Route | Auth | Purpose |
| --- | --- | --- |
| `POST /api/generate` | yes | Queue a video. Remote GPU if running, else a local mock. |
| `POST /api/upscale-4k` | yes | 4K upscale via videotoolbox. |
| `POST /api/composite-motionvector` | yes | 4K plate + vector overlay master. |
| `POST /api/generate/music` | yes | Music cue, normalized to -16 LUFS. |
| `POST /api/generate/voice` | yes | Voiceover, peak-normalized to -1 dBFS. |
| `POST /api/gpu/launch` · `/terminate` | yes | Spot GPU lifecycle. |
| `GET /api/jobs/{job_id}` | no | Job status. A failed job has no media, so it is invisible in `/api/assets`. |
| `GET /api/assets` · `/api/media/{file}` | no | Asset library and file serving. |
| `GET /healthz` | no | Dependency-free process liveness for local supervisors. |
| `GET /api/status` | no | GPU and worker telemetry. |

Jobs are asynchronous: the POST returns a `job_id`, then poll `/api/jobs/{id}`
until `status` is `completed` or `failed`. Failed jobs record the real error and
leave no partial file behind — with one deliberate exception, below.

### Audio

**Music** proxies to a local MLX server, so start one first:

```bash
mlx-serve serve --host 127.0.0.1 --port 11234 --skip-mem-preflight
```

Roughly 25× realtime — a 10s cue takes about 4 minutes. `lyrics` is required
even for instrumentals; pass section tags only, e.g.
`"[Intro]\n[Instrumental]\n[Break]\n[Outro]"`, and use four or more or the piece
ends early. Normalization is two-pass: single-pass `loudnorm` is an estimator
and lands 1–2 LU off the target. If normalization fails the raw take is kept
under a `_raw` suffix, because it cost minutes of compute and the cheap half is
what failed.

**Voice** needs no server. Kokoro runs in-process through `onnxruntime` against
`kokoro-v1.0.onnx` and `voices-v1.0.bin`, found via `PLUTO_KOKORO_MODEL` /
`PLUTO_KOKORO_VOICES` or a couple of known cache paths. 54 voices, 24 kHz, about
1.5× realtime. Output is peak-normalized rather than limited — a limiter only
caps peaks above the threshold and leaves quiet VO quiet.

`backend=cloud` returns 501 on both: MLX does not run on CUDA and the spot box
has no equivalent model provisioned.

---

## GPU box

```bash
doppler run -- ./bin/pluto launch      # spot instance + deploy + warm VRAM
doppler run -- ./bin/pluto status      # instance, cost, VRAM, worker health
doppler run -- ./bin/pluto generate "a prompt"
doppler run -- ./bin/pluto sync        # pull /scratch/out back to outputs/
doppler run -- ./bin/pluto terminate   # stop billing
```

`launch` starts a g6e.2xlarge spot instance at roughly $0.75/hour and bills
until terminated. Deploy sends the worker the token over stdin so it never
appears in the remote process list. The worker binds `0.0.0.0` because the Mac
has to reach it; its protection is the token plus the AWS security group, which
this repo does not define.

---

## Tests

```bash
python -m pytest tests/ -q
```

42 tests covering the API, the audio endpoints, worker auth, and frontend
escaping. `tests/conftest.py` points `PLUTO_OUTPUTS_DIR` at a temp directory, so
runs never write into the real asset library. Tests need `ffmpeg` on PATH and
the environment where `requirements.txt` was installed. The live voice test
skips if the Kokoro weights are absent.

---

## Layout

```
bin/pluto              CLI launcher
src/studio_api.py      studio backend + API
src/cli.py             CLI implementation
src/ltx_worker.py      GPU worker (runs on EC2)
src/server.py          legacy LTX bridge
studio/                web UI (index.html, studio.js, studio.css)
infra/                 gpu-box.sh, worker bootstrap, IAM policy
tests/                 pytest suite
docs/                  handoff notes and assets
outputs/               generated media (gitignored)
```
