#!/usr/bin/env python3
"""Tests for the music and voice generation endpoints.

The MLX backend is stubbed here. Live generation is verified separately against
a running mlx-serve; these cover the dispatcher, validation and job semantics.
"""

import json
import sys
import time
from pathlib import Path

PLUTO_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(PLUTO_ROOT))
sys.path.append(str(PLUTO_ROOT / "src"))

from fastapi.testclient import TestClient

import src.studio_api as studio_api
from src.studio_api import OUTPUTS_DIR, STUDIO_TOKEN, app

client = TestClient(app)
AUTH = {"X-Pluto-Token": STUDIO_TOKEN}

MUSIC_BODY = {"prompt": "warm ambient pad", "lyrics": "[Intro]\n[Instrumental]\n[Outro]"}
VOICE_BODY = {"text": "Diffusion models start from noise."}


def wait_for_job(job_id, timeout=60):
    for _ in range(timeout * 5):
        meta_path = OUTPUTS_DIR / f"{job_id}.json"
        if meta_path.exists():
            meta = json.loads(meta_path.read_text())
            if meta["status"] in ("completed", "failed"):
                return meta
        time.sleep(0.2)
    raise AssertionError(f"job {job_id} never settled")


def silent_wav(seconds=1):
    """A real WAV the ffmpeg stages can actually process."""
    out = OUTPUTS_DIR / "pytest_stub_source.wav"
    studio_api.run_ffmpeg([
        "-f", "lavfi", "-i", f"anullsrc=r=44100:cl=stereo", "-t", str(seconds), str(out)
    ])
    data = out.read_bytes()
    out.unlink()
    return data


def test_music_and_voice_require_the_token():
    assert client.post("/api/generate/music", json=MUSIC_BODY).status_code == 401
    assert client.post("/api/generate/voice", json=VOICE_BODY).status_code == 401


def test_cloud_backend_is_an_honest_501():
    """Scaffold only: say what is missing rather than pretending to dispatch."""
    for path, body in [("/api/generate/music", MUSIC_BODY), ("/api/generate/voice", VOICE_BODY)]:
        response = client.post(path, json={**body, "backend": "cloud"}, headers=AUTH)
        assert response.status_code == 501
        detail = response.json()["detail"].lower()
        assert "not implemented" in detail and "provisioned" in detail


def test_bounds_are_enforced():
    for body in [
        {**MUSIC_BODY, "duration_seconds": 0},
        {**MUSIC_BODY, "duration_seconds": 361},
        {**MUSIC_BODY, "duration_seconds": 1e9},
        {**MUSIC_BODY, "backend": "gpu"},
    ]:
        assert client.post("/api/generate/music", json=body, headers=AUTH).status_code == 422

    raw = '{"prompt":"x","lyrics":"y","duration_seconds":Infinity}'
    response = client.post(
        "/api/generate/music", content=raw,
        headers={**AUTH, "Content-Type": "application/json"},
    )
    assert response.status_code == 422

    for body in [
        {**VOICE_BODY, "speed": 0.1},
        {**VOICE_BODY, "speed": 5},
        {**VOICE_BODY, "voice": "../../etc/passwd"},
        {**VOICE_BODY, "voice": "a b"},
    ]:
        assert client.post("/api/generate/voice", json=body, headers=AUTH).status_code == 422


def test_music_job_completes_and_normalizes(monkeypatch):
    audio = silent_wav(2)
    monkeypatch.setattr(studio_api, "mlx_generate_audio", lambda path, payload, timeout: audio)

    response = client.post("/api/generate/music", json={**MUSIC_BODY, "duration_seconds": 2}, headers=AUTH)
    assert response.status_code == 200
    job_id = response.json()["job_id"]

    meta = wait_for_job(job_id)
    assert meta["status"] == "completed", meta.get("error")
    assert (OUTPUTS_DIR / f"{job_id}.wav").exists()
    assert meta["target_lufs"] == -16
    # The raw take is kept alongside the normalized master.
    assert (OUTPUTS_DIR / f"{job_id}_raw.wav").exists()

    # Served with the right media type, and visible through the job route.
    assert client.get(f"/api/media/{job_id}.wav").headers["content-type"] == "audio/wav"
    assert client.get(f"/api/jobs/{job_id}").json()["status"] == "completed"


def test_voice_synthesizes_real_speech_in_process():
    """The default backend is Kokoro via onnxruntime — no server, no subprocess."""
    import wave

    import pytest

    if not studio_api.kokoro_assets()[0]:
        pytest.skip("kokoro-v1.0.onnx not on this machine")

    response = client.post("/api/generate/voice", json=VOICE_BODY, headers=AUTH)
    assert response.status_code == 200
    job_id = response.json()["job_id"]

    meta = wait_for_job(job_id, timeout=120)
    assert meta["status"] == "completed", meta.get("error")
    assert meta["backend"] == "local"

    with wave.open(str(OUTPUTS_DIR / f"{job_id}.wav")) as wav:
        assert wav.getframerate() == 24000
        assert wav.getnframes() > 0, "produced no audio"


def test_voice_job_completes_and_drops_its_raw(monkeypatch):
    audio = silent_wav(1)
    monkeypatch.setattr(studio_api, "synthesize_voice",
                        lambda text, voice, speed, out: out.write_bytes(audio))

    response = client.post("/api/generate/voice", json=VOICE_BODY, headers=AUTH)
    assert response.status_code == 200
    job_id = response.json()["job_id"]

    meta = wait_for_job(job_id)
    assert meta["status"] == "completed", meta.get("error")
    assert (OUTPUTS_DIR / f"{job_id}.wav").exists()
    assert not (OUTPUTS_DIR / f"{job_id}_raw.wav").exists(), "voice keeps no raw; it is cheap to redo"


def test_backend_failure_is_recorded_and_leaves_nothing_behind(monkeypatch):
    def boom(path, payload, timeout):
        raise OSError("connection refused")

    monkeypatch.setattr(studio_api, "mlx_generate_audio", boom)
    response = client.post("/api/generate/music", json=MUSIC_BODY, headers=AUTH)
    job_id = response.json()["job_id"]

    meta = wait_for_job(job_id)
    assert meta["status"] == "failed"
    assert "connection refused" in meta["error"]
    assert not (OUTPUTS_DIR / f"{job_id}_raw.wav").exists()
    assert not (OUTPUTS_DIR / f"{job_id}.wav").exists()


def test_normalization_failure_keeps_the_expensive_raw_take(monkeypatch):
    """The documented exception: ~25 min of GPU time is not thrown away."""
    monkeypatch.setattr(studio_api, "mlx_generate_audio", lambda path, payload, timeout: b"not audio")

    response = client.post("/api/generate/music", json=MUSIC_BODY, headers=AUTH)
    job_id = response.json()["job_id"]

    meta = wait_for_job(job_id)
    assert meta["status"] == "failed"
    assert "ffmpeg exited" in meta["error"]
    assert (OUTPUTS_DIR / f"{job_id}_raw.wav").exists(), "raw take was discarded"
    assert meta["raw_path"].endswith(f"{job_id}_raw.wav")


def test_music_payload_matches_the_backend_contract(monkeypatch):
    """The reference client's proven request shape, including required lyrics."""
    seen = {}

    def capture(path, payload, timeout):
        seen["path"] = path
        seen["payload"] = payload
        raise OSError("stop here")

    monkeypatch.setattr(studio_api, "mlx_generate_audio", capture)
    response = client.post(
        "/api/generate/music",
        json={**MUSIC_BODY, "duration_seconds": 10, "seed": 7},
        headers=AUTH,
    )
    wait_for_job(response.json()["job_id"])

    assert seen["path"] == "/v1/audio/music-generations"
    assert set(seen["payload"]) == {"model", "prompt", "lyrics", "duration_seconds", "seed"}
    assert seen["payload"]["seed"] == 7
    assert seen["payload"]["lyrics"] == MUSIC_BODY["lyrics"]


def test_voice_mlx_backend_payload_matches_the_contract(monkeypatch):
    """backend=mlx is kept as an alternative; its request shape must stay right."""
    seen = {}

    def capture(path, payload, timeout):
        seen.update(path=path, payload=payload)
        raise OSError("stop here")

    monkeypatch.setattr(studio_api, "mlx_generate_audio", capture)
    response = client.post(
        "/api/generate/voice",
        json={**VOICE_BODY, "voice": "af_heart", "backend": "mlx"},
        headers=AUTH,
    )
    wait_for_job(response.json()["job_id"])

    assert seen["path"] == "/v1/audio/speech"
    # OpenAI-compatible speech shape: the text field is "input", not "text".
    assert seen["payload"]["input"] == VOICE_BODY["text"]
    assert seen["payload"]["voice"] == "af_heart"
    assert seen["payload"]["response_format"] == "wav"
