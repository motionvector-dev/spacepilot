# Tech Spec: `spacepilot run video` & Video Execution Client

**Date**: 2026-10-07  
**Branch**: `feat/h3-aws-launch`  
**Status**: APPROVED FOR TDD IMPLEMENTATION  

---

## 1. Problem Statement

SpacePilot supports `run image` (mflux), `run speech` (Kokoro), `run transcribe` (Whisper), and `run text` (MLX-LM), but **has no `run video`** client command.
After `spacepilot launch` boots an EC2 node with MiniMax-H3 or Wan 2.1 resident in memory, there is no built-in mechanism to:
1. Submit an inference generation request to the warm backend (SGLang on port 30010 or worker on port 5000).
2. Monitor generation progress / step telemetry.
3. Retrieve and download the generated MP4 to the local `outputs/` folder.

---

## 2. CLI Interface & UX Contract

```bash
spacepilot run video --prompt "<prompt>" [OPTIONS]
```

### Options:
- `--prompt`: (Required) Text scene prompt.
- `--model`: (Optional) Model or variant ID (e.g. `minimax-h3-fl2va-fp8`, `wan-2.1-t2v-14b`). If omitted, auto-detects from resident model via `spacepilot status` / `get_resident_models` or active EC2 box.
- `--box`: (Optional) Explicit IP or instance ID. If omitted, uses active instance from config or `localhost:30010`.
- `--seconds`: (Optional) Video length in seconds (default: 4.0 or model default).
- `--steps`: (Optional) Number of inference diffusion steps (default: 30).
- `--resolution`: (Optional) Width Height (e.g. `1024 576` or `1280 720`).
- `--output`, `-o`: (Optional) Local path to save MP4. Defaults to `outputs/<model>-<timestamp>-<uuid>.mp4`.
- `--open`: (Optional) Open downloaded video immediately in macOS default viewer.
- `--async`: (Optional) Return job ID immediately without waiting for completion.

---

## 3. Architecture & Service Design

### Module: `spacepilot/services/video_client.py`

```python
class VideoClient:
    def __init__(self, endpoint_url: str, timeout: float = 300.0):
        ...
    
    def generate_video(
        self,
        prompt: str,
        model_id: str,
        output_path: Path,
        steps: int = 30,
        seconds: float = 4.0,
        resolution: tuple[int, int] = (1024, 576),
        seed: Optional[int] = None,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> VideoGenerationResult:
        ...
```

### Target Backends Supported:
1. **SGLang Native Multimodal Diffusion API**: Endpoint `http://<ip>:30010/v1/video/generations` or OpenAI-compatible video diffusion route.
2. **SpacePilot Remote Worker Daemon**: Endpoint `http://<ip>:5000/generate` (for active spot boxes running the SpacePilot worker).
3. **Local Fallback**: `http://localhost:30010`.

---

## 4. TDD Subagent Work Packages

### Package 1: Video Client Service (`spacepilot/services/video_client.py`)
- Unit tests: `tests/test_video_client.py`
- Test payload formation, timeout handling, retry logic, mock streaming progress, and file download to destination path.

### Package 2: CLI Wiring (`spacepilot/cli.py`)
- Unit tests: `tests/test_cli_run_video.py`
- Register `run video` subparser in `cli.py`.
- Implement `_cmd_run_video(args, cfg)`:
  - Discovers endpoint (checks active EC2 instance IP -> fallback localhost).
  - Prompts/confirms plan.
  - Executes video client with progress output.
  - Reports wall time, step speed, and saved MP4 path.
