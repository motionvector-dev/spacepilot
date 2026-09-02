#!/usr/bin/env python3
"""Comprehensive unit and integration tests for SpacePilot in-process local execution drivers."""

import os
import sys
import wave
import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(REPO_ROOT))
sys.path.append(str(REPO_ROOT / "spacepilot"))

from spacepilot.drivers.base import DriverSpec, InferenceDriver
from spacepilot.drivers.kokoro_driver import KokoroDriver, VOICE_CATALOGUE
from spacepilot.drivers.gguf_driver import GGUFDriver
from spacepilot.local_workers import LocalWorkerManager, local_worker_manager
from spacepilot.web_api import app, STUDIO_TOKEN, OUTPUTS_DIR

client = TestClient(app)
AUTH = {"X-Pluto-Token": STUDIO_TOKEN}


@pytest.fixture(autouse=True)
def _fake_heavy_model_sessions(monkeypatch):
    """Lifecycle tests exercise orchestration, never machine-local weights."""
    import re
    import numpy as np

    class FakeKokoro:
        def create(self, text, voice, speed, lang):
            return np.full(24000, 0.1, dtype=np.float32), 24000

    def load_kokoro(self):
        self._session = FakeKokoro()
        self.spec.is_loaded = True
        return True

    class FakeLlama:
        def create_chat_completion(self, messages, **kwargs):
            prompt = messages[0]["content"]
            count = int(re.search(r"exactly (\d+)", prompt).group(1))
            duration = float(re.search(r"Total duration must be ([0-9.]+)", prompt).group(1))
            seed = kwargs["seed"]
            scenes = []
            for index in range(count):
                scenes.append({
                    "scene_id": f"scene_{index + 1:02d}", "scene_idx": index + 1,
                    "title": f"Scene {index + 1}", "duration_sec": duration / count,
                    "prompt": "A real model-produced scene", "camera_motion": "static",
                    "camera_vector": {"pan": 0, "tilt": 0, "zoom": 1, "roll": 0, "orbit": 0},
                    "shot_type": "wide", "lighting": "natural", "environment": "exterior",
                    "transition": "cut", "audio_cue": "room tone",
                    "character_seed": seed, "takes_ready": 0,
                })
            return {"choices": [{"message": {"content": json.dumps({"scenes": scenes})}}]}

    def load_gguf(self):
        self._llm = FakeLlama()
        self.spec.is_loaded = True
        return True

    monkeypatch.setattr(KokoroDriver, "load", load_kokoro)
    monkeypatch.setattr(GGUFDriver, "load", load_gguf)


class DummyDriver(InferenceDriver):
    """Test stub for InferenceDriver abstract class validation."""
    def load(self) -> bool:
        self.spec.is_loaded = True
        return True

    def unload(self) -> bool:
        self.spec.is_loaded = False
        return True

    def infer(self, **kwargs):
        return {"dummy": "result", **kwargs}


def test_driver_spec_and_base_driver():
    """Verify DriverSpec initialization and InferenceDriver lifecycle properties."""
    spec = DriverSpec(
        driver_id="test-stub-driver",
        task="custom_task",
        backend="cpu",
        resident_vram_gb=1.5,
        is_loaded=False,
    )
    assert spec.driver_id == "test-stub-driver"
    assert spec.resident_vram_gb == 1.5
    data = spec.to_dict()
    assert data["backend"] == "cpu"
    assert data["is_loaded"] is False

    driver = DummyDriver(spec)
    assert driver.driver_id == "test-stub-driver"
    assert driver.task == "custom_task"
    assert driver.backend == "cpu"
    assert driver.resident_vram_gb == 1.5
    assert not driver.is_loaded

    assert driver.load() is True
    assert driver.is_loaded is True

    res = driver.infer(val=42)
    assert res["val"] == 42

    assert driver.unload() is True
    assert driver.is_loaded is False


def test_kokoro_driver_lifecycle_and_catalogue():
    """Verify KokoroDriver voice catalogue, validation, and load/unload cycle."""
    driver = KokoroDriver(driver_id="kokoro-82m-onnx")
    assert driver.task == "voiceover"
    assert driver.backend == "onnx"
    assert driver.resident_vram_gb == 0.32

    # Verify voice catalogue
    catalogue = driver.get_voice_catalogue()
    assert len(catalogue) == 10
    voice_ids = [v["id"] for v in catalogue]
    assert "af_heart" in voice_ids
    assert "am_michael" in voice_ids
    assert "am_onyx" in voice_ids

    assert driver.is_valid_voice("af_heart") is True
    assert driver.is_valid_voice("am_michael") is True
    assert driver.is_valid_voice("invalid_voice_xyz") is False

    # Load / Unload
    assert driver.load() is True
    assert driver.is_loaded is True
    assert driver.unload() is True
    assert driver.is_loaded is False


def test_kokoro_driver_synthesizes_24khz_normalized_wav(tmp_path):
    """Verify KokoroDriver synthesizes 24kHz 16-bit PCM audio with -16 LUFS sidechain normalization."""
    driver = KokoroDriver()
    out_file = tmp_path / "test_kokoro_speech.wav"

    res = driver.infer(
        text="MotionVector Pluto synthesizes neural speech directly in-process.",
        voice="af_heart",
        speed=1.0,
        out_path=out_file,
        target_lufs=-16.0,
    )

    assert res["status"] == "completed"
    assert res["sample_rate"] == 24000
    assert res["duration_sec"] > 0.5
    assert res["target_lufs"] == -16.0
    assert res["voice"] == "af_heart"
    assert res["file_path"] == str(out_file)
    assert out_file.exists()

    # Validate WAV headers
    with wave.open(str(out_file), "rb") as wav:
        assert wav.getnchannels() == 1      # Mono
        assert wav.getsampwidth() == 2      # 16-bit PCM
        assert wav.getframerate() == 24000  # 24 kHz
        num_frames = wav.getnframes()
        assert num_frames > 12000          # > 0.5s


def test_gguf_driver_narrative_decomposition():
    """Verify GGUFDriver parses screenplays into structured scene beats with camera vectors and locked seeds."""
    driver = GGUFDriver(driver_id="qwen2.5-3b-instruct-gguf", resident_vram_gb=2.1)
    assert driver.task == "storyboard"
    assert driver.backend == "gguf"
    assert driver.resident_vram_gb == 2.1

    assert driver.load() is True
    assert driver.is_loaded is True

    script = (
        "EXT. CYBERNETIC METROPOLIS - NIGHT. Neon rain falls over monolithic glass spires. "
        "A lone hover-car accelerates across the upper sky-lane. "
        "Inside the cockpit, Captain Sarah dials into the telemetry matrix. "
        "The mainframe reveals a quantum singularity approaching orbit. "
        "She initiates emergency thruster sequence as sirens wail."
    )

    res = driver.infer(
        script=script,
        scene_count=6,
        target_duration_sec=60.0,
        style="cyberpunk",
        character_seed=424242,
    )

    assert res["status"] == "success"
    assert res["scene_count"] == 6
    assert res["target_duration_sec"] == 60.0
    assert res["total_duration_sec"] == 60.0
    assert res["character_seed"] == 424242
    assert len(res["scenes"]) == 6

    # Verify each scene beat contract
    for sc in res["scenes"]:
        assert "scene_id" in sc
        assert "scene_idx" in sc
        assert "title" in sc
        assert sc["duration_sec"] > 0
        assert "prompt" in sc
        assert "camera_motion" in sc
        assert "camera_vector" in sc
        assert isinstance(sc["camera_vector"], dict)
        assert "pan" in sc["camera_vector"]
        assert "tilt" in sc["camera_vector"]
        assert "zoom" in sc["camera_vector"]
        assert "roll" in sc["camera_vector"]
        assert "orbit" in sc["camera_vector"]
        assert "shot_type" in sc
        assert "lighting" in sc
        assert "environment" in sc
        assert "transition" in sc
        assert "audio_cue" in sc
        assert sc["character_seed"] == 424242

    assert driver.unload() is True
    assert driver.is_loaded is False


def test_local_worker_manager_singleton_and_coordination():
    """Verify LocalWorkerManager singleton behavior, VRAM headroom tracking, and auto LRU eviction."""
    LocalWorkerManager.reset_instance()
    mgr1 = LocalWorkerManager.get_instance(max_vram_gb=3.0)
    mgr2 = LocalWorkerManager.get_instance()
    assert mgr1 is mgr2
    assert mgr1.max_vram_gb == 3.0
    assert mgr1.resident_vram_gb == 0.0

    # 1. Load Kokoro (0.32 GB)
    kokoro = mgr1.load_driver("kokoro-82m-onnx")
    assert kokoro.is_loaded is True
    assert mgr1.resident_vram_gb == 0.32

    # 2. Load GGUF Driver (2.1 GB) -> Total 2.42 GB <= 3.0 GB
    gguf = mgr1.load_driver("qwen2.5-3b-instruct-gguf")
    assert gguf.is_loaded is True
    assert round(mgr1.resident_vram_gb, 2) == 2.42

    # 3. Register and load a third driver that forces LRU eviction of kokoro
    class HeavyDriver(InferenceDriver):
        def load(self):
            self.spec.is_loaded = True
            return True
        def unload(self):
            self.spec.is_loaded = False
            return True
        def infer(self, **kwargs):
            return {}

    heavy_spec = DriverSpec(
        driver_id="heavy-driver-1gb",
        task="heavy_task",
        backend="cpu",
        resident_vram_gb=1.0,
    )
    mgr1.register_driver_class("heavy-driver-1gb", lambda **kw: HeavyDriver(heavy_spec))

    # Loading heavy driver (1.0 GB) when 2.42 GB is resident and max is 3.0 GB forces kokoro eviction
    heavy = mgr1.load_driver("heavy-driver-1gb")
    assert heavy.is_loaded is True
    assert kokoro.is_loaded is False  # Evicted

    # 4. Exceeding max VRAM on a single driver raises MemoryError
    impossible_spec = DriverSpec(
        driver_id="impossible-10gb",
        task="impossible",
        backend="cpu",
        resident_vram_gb=10.0,
    )
    mgr1.register_driver_class("impossible-10gb", lambda **kw: HeavyDriver(impossible_spec))
    with pytest.raises(MemoryError):
        mgr1.load_driver("impossible-10gb")

    # Clean up
    mgr1.unload_all()
    assert mgr1.resident_vram_gb == 0.0


def test_local_worker_manager_dispatch():
    """Verify local_worker_manager task-based dispatch for voiceover and storyboard."""
    LocalWorkerManager.reset_instance()
    mgr = LocalWorkerManager.get_instance()

    # Dispatch voiceover
    voice_res = mgr.dispatch("voiceover", text="Testing local worker dispatch.")
    assert voice_res["status"] == "completed"
    assert voice_res["sample_rate"] == 24000

    # Dispatch storyboard
    story_res = mgr.dispatch(
        "storyboard",
        script="Ancient temple in misty mountains with hidden chamber.",
        scene_count=4,
    )
    assert story_res["status"] == "success"
    assert len(story_res["scenes"]) == 4

    mgr.unload_all()


def test_local_worker_manager_telemetry():
    """Verify local_worker_manager telemetry snapshot."""
    LocalWorkerManager.reset_instance()
    mgr = LocalWorkerManager.get_instance()
    mgr.load_driver("kokoro-82m-onnx")

    status = mgr.get_status()
    assert status["status"] == "online"
    assert "device" in status
    assert status["resident_vram_gb"] > 0
    # None here means the machine's accelerator memory was never measured — a
    # CPU-only CI runner reports exactly that, and it is not the same as 0.
    usable = status["usable_vram_gb"]
    assert usable is None or usable > 0
    assert isinstance(status["has_accelerator"], bool)
    assert status["loaded_drivers_count"] >= 1
    assert any(d["driver_id"] == "kokoro-82m-onnx" for d in status["loaded_drivers"])

    mgr.unload_all()


def test_web_api_local_synthesize_endpoint_security_and_execution():
    """Verify /api/audio/synthesize-local auth gating, validation, and generation."""
    payload = {"text": "Local in-process Kokoro synthesis test.", "voice": "af_heart", "speed": 1.0}

    # 1. Gating checks
    assert client.post("/api/audio/synthesize-local", json=payload).status_code == 401
    assert client.post("/api/audio/synthesize-local", json=payload, headers={"X-Pluto-Token": "invalid"}).status_code == 401

    # 2. Validation check (empty text)
    res_empty = client.post("/api/audio/synthesize-local", json={"text": ""}, headers=AUTH)
    assert res_empty.status_code in [400, 422]

    # 3. Successful execution
    res = client.post("/api/audio/synthesize-local", json=payload, headers=AUTH)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "completed"
    assert "id" in data
    assert data["voice"] == "af_heart"
    assert data["sample_rate"] == 24000
    assert data["target_lufs"] == -16.0
    assert data["audio_url"].startswith("/api/media/")

    job_id = data["id"]
    wav_file = OUTPUTS_DIR / f"{job_id}.wav"
    json_file = OUTPUTS_DIR / f"{job_id}.json"
    assert wav_file.exists()
    assert json_file.exists()

    # Clean up generated test output files
    wav_file.unlink(missing_ok=True)
    json_file.unlink(missing_ok=True)


def test_web_api_local_decompose_endpoint_security_and_execution():
    """Verify /api/narrative/decompose-local auth gating, validation, and scene decomposition."""
    payload = {
        "script": "Deep sea research submarine discovers an underwater alien structure.",
        "scene_count": 5,
        "target_duration_sec": 50.0,
        "style": "cinematic_scifi",
    }

    # 1. Gating checks
    assert client.post("/api/narrative/decompose-local", json=payload).status_code == 401
    assert client.post("/api/narrative/decompose-local", json=payload, headers={"X-Pluto-Token": "invalid"}).status_code == 401

    # 2. Validation check (empty script)
    res_empty = client.post("/api/narrative/decompose-local", json={"script": ""}, headers=AUTH)
    assert res_empty.status_code in [400, 422]

    # 3. Successful execution
    res = client.post("/api/narrative/decompose-local", json=payload, headers=AUTH)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["scene_count"] == 5
    assert data["target_duration_sec"] == 50.0
    assert len(data["scenes"]) == 5
    assert data["scenes"][0]["camera_vector"]["zoom"] is not None
    assert "character_seed" in data
