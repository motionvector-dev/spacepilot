"""Video generation client for communicating with remote or local inference backends.

Supports SGLang multimodal diffusion endpoints, SpacePilot remote worker daemon,
and standard HTTP video generation protocols.
"""

from __future__ import annotations

import base64
import logging
from urllib.parse import urljoin, urlsplit
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Tuple

import httpx

logger = logging.getLogger(__name__)


@dataclass
class VideoGenerationResult:
    """Telemetry and output result for a completed video generation."""
    output_path: Path
    wall_seconds: float
    steps: int
    seconds_per_step: float
    model_id: str


class VideoClient:
    """HTTP client for video generation services."""

    def __init__(self, endpoint_url: str, timeout: float = 300.0):
        parsed = urlsplit(endpoint_url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("Video endpoint must be an HTTP URL without credentials")
        self.endpoint_url = endpoint_url.rstrip("/")
        self.timeout = timeout
        self._client = httpx.Client(timeout=timeout)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "VideoClient":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    def generate_video(
        self,
        prompt: str,
        model_id: str,
        output_path: Path,
        steps: int = 20,
        seconds: float = 4.0,
        resolution: Tuple[int, int] = (1024, 576),
        seed: Optional[int] = None,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> VideoGenerationResult:
        """Submit generation request, track progress, download video to output_path.

        Args:
            prompt: Text prompt describing the video scene.
            model_id: Model identifier (e.g. minimax-h3, wan-2.1-t2v-14b).
            output_path: Destination path for the output MP4.
            steps: Number of diffusion steps.
            seconds: Duration in seconds.
            resolution: (width, height) tuple.
            seed: Optional RNG seed.
            progress_callback: Optional callable receiving (current_step, total_steps).

        Returns:
            VideoGenerationResult with execution metrics and saved path.
        """
        output_path = Path(output_path).expanduser().resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)

        width, height = resolution
        payload: Dict[str, Any] = {
            "prompt": prompt,
            "model": model_id,
            "steps": steps,
            "seconds": seconds,
            "width": width,
            "height": height,
        }
        if seed is not None:
            payload["seed"] = seed

        # Target endpoint resolution:
        # 1. If worker endpoint (port 5000), use /generate
        # 2. If standard SGLang or OpenAI diffusion endpoint, try /v1/video/generations or /generate
        url = (
            f"{self.endpoint_url}/generate"
            if ":5000" in self.endpoint_url or not self.endpoint_url.endswith("/v1/video/generations")
            else self.endpoint_url
        )

        start_time = time.perf_counter()

        try:
            resp = self._client.post(url, json=payload)
        except Exception as exc:
            raise RuntimeError(f"Generation request failed to connect to {url}: {exc}") from exc

        if resp.status_code >= 400:
            raise RuntimeError(f"Generation failed with HTTP {resp.status_code}: {resp.text}")

        content_type = resp.headers.get("content-type", "")

        # Handle direct MP4 binary response
        if "video/mp4" in content_type or (resp.content and resp.content[:8] == b"\x00\x00\x00\x18ftyp"):
            output_path.write_bytes(resp.content)
            wall_time = float(resp.headers.get("x-inference-wall-seconds", time.perf_counter() - start_time))
            actual_steps = int(resp.headers.get("x-inference-steps", steps))
            s_per_step = wall_time / actual_steps if actual_steps > 0 else 0.0
            if progress_callback:
                progress_callback(actual_steps, actual_steps)
            return VideoGenerationResult(
                output_path=output_path,
                wall_seconds=wall_time,
                steps=actual_steps,
                seconds_per_step=s_per_step,
                model_id=model_id,
            )

        # Handle JSON response: could be base64 video, job status, or worker job_id
        try:
            data = resp.json()
        except Exception:
            raise RuntimeError("Unexpected empty or non-JSON response from server")

        # 1. Base64 video embedded in JSON
        if "video_base64" in data or "video_b64" in data:
            b64_raw = data.get("video_base64") or data.get("video_b64")
            video_bytes = base64.b64decode(b64_raw)
            output_path.write_bytes(video_bytes)
            wall_time = float(data.get("wall_seconds", time.perf_counter() - start_time))
            actual_steps = int(data.get("steps", steps))
            s_per_step = wall_time / actual_steps if actual_steps > 0 else 0.0
            if progress_callback:
                progress_callback(actual_steps, actual_steps)
            return VideoGenerationResult(
                output_path=output_path,
                wall_seconds=wall_time,
                steps=actual_steps,
                seconds_per_step=s_per_step,
                model_id=model_id,
            )

        # 2. Worker asynchronous job pattern: job_id
        if "job_id" in data:
            job_id = data["job_id"]
            if not isinstance(job_id, str) or not job_id or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for c in job_id):
                raise ValueError("Invalid worker job ID")
            return self._poll_and_download_worker(
                job_id=job_id,
                output_path=output_path,
                steps=steps,
                model_id=model_id,
                start_time=start_time,
                progress_callback=progress_callback,
            )

        # 3. Direct URL to download
        if "url" in data or "video_url" in data:
            dl_url = data.get("url") or data.get("video_url")
            dl_url = urljoin(self.endpoint_url + "/", dl_url)
            origin = urlsplit(self.endpoint_url)
            target = urlsplit(dl_url)
            if (target.scheme, target.hostname, target.port) != (origin.scheme, origin.hostname, origin.port) or target.username or target.password:
                raise ValueError("Video download URL must use the endpoint origin")
            dl_resp = self._client.get(dl_url, follow_redirects=False)
            if 300 <= dl_resp.status_code < 400:
                raise ValueError("Video download redirects are not allowed")
            dl_resp.raise_for_status()
            output_path.write_bytes(dl_resp.content)
            wall_time = float(data.get("wall_seconds", time.perf_counter() - start_time))
            actual_steps = int(data.get("steps", steps))
            s_per_step = wall_time / actual_steps if actual_steps > 0 else 0.0
            return VideoGenerationResult(
                output_path=output_path,
                wall_seconds=wall_time,
                steps=actual_steps,
                seconds_per_step=s_per_step,
                model_id=model_id,
            )

        raise RuntimeError(f"Unrecognized response format from backend: {data}")

    def _poll_and_download_worker(
        self,
        job_id: str,
        output_path: Path,
        steps: int,
        model_id: str,
        start_time: float,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> VideoGenerationResult:
        """Poll job status on worker and download completed video."""
        status_url = f"{self.endpoint_url}/status/{job_id}"
        poll_interval = 0.5
        max_polls = int(self.timeout / poll_interval)

        wall_seconds = 0.0
        final_steps = steps

        for _ in range(max_polls):
            time.sleep(poll_interval)  # small delay before poll
            resp = self._client.get(status_url)
            if resp.status_code != 200:
                raise RuntimeError(f"Failed to check job status: {resp.status_code} {resp.text}")

            st = resp.json()
            cur_step = st.get("step")
            tot_steps = st.get("total_steps", steps)
            if cur_step is not None and progress_callback:
                progress_callback(cur_step, tot_steps)

            state = st.get("status")
            if state == "completed":
                wall_seconds = float(st.get("wall_seconds", time.perf_counter() - start_time))
                final_steps = int(st.get("total_steps") or st.get("step") or steps)
                break
            elif state in ("failed", "error"):
                raise RuntimeError(f"Job failed on remote worker: {st.get('error', 'unknown error')}")

        else:
            raise TimeoutError(f"Video job {job_id} did not complete within {self.timeout}s")

        download_url = f"{self.endpoint_url}/download/{job_id}"
        dl_resp = self._client.get(download_url)
        if dl_resp.status_code != 200:
            raise RuntimeError(f"Failed to download video from {download_url}: {dl_resp.status_code}")

        output_path.write_bytes(dl_resp.content)
        if wall_seconds <= 0.0:
            wall_seconds = time.perf_counter() - start_time
        s_per_step = wall_seconds / final_steps if final_steps > 0 else 0.0

        return VideoGenerationResult(
            output_path=output_path,
            wall_seconds=wall_seconds,
            steps=final_steps,
            seconds_per_step=s_per_step,
            model_id=model_id,
        )
