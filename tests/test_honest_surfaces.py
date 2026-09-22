"""Three surfaces, one truth.

Each test here pins a claim SpacePilot was making that was not true of the
machine it was made about:

* `loaded_models` listed a 75-byte marker file as a loaded model, and the MCP
  tool and the HTTP route answered the same question two different ways at the
  same instant.
* usable memory was computed and printed independently by `doctor`, `probe` and
  the local-status surfaces, so the same machine had three different capacities.

Where a bug was a divergence, the test asserts the surfaces *agree*, so they
cannot drift apart again.
"""

import re
import sys
from io import StringIO
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from spacepilot import model_recommender
from spacepilot.cli import cmd_doctor, cmd_probe
from spacepilot.device_probe import GIB, DeviceProfile
from spacepilot.mcp_server import spacepilot_get_local_status
from spacepilot.web_api import app

client = TestClient(app)


def _profile():
    """An M1 Max whose platform limit was measured — the machine all three lied about."""
    return DeviceProfile(
        os_name="macOS", arch="arm64", backend="metal",
        chip="Apple M1 Max", machine_model="MacBookPro18,4",
        gpu_name="Apple M1 Max",
        memory_total_bytes=32 * GIB, memory_free_bytes=8 * GIB,
        cpu_cores=10, gpu_cores=32, memory_unified=True,
        memory_limit_bytes=26_803_140_608, memory_limit_source="metal",
    )


def _fake_subprocess(*args, **kwargs):
    """`doctor` shells out to ffmpeg and aws; neither is what these tests measure."""
    return MagicMock(stdout='{"Arn": "arn:aws:iam::000000000000:user/test"}')


def _capture(fn, *args):
    out = StringIO()
    old = sys.stdout
    sys.stdout = out
    try:
        fn(*args)
    finally:
        sys.stdout = old
    return out.getvalue()


# ---------------------------------------------------------------- bug 1


@pytest.fixture
def stub_marker_cache(tmp_path, monkeypatch):
    """A cache holding exactly what a gated mock download left behind: markers."""
    canonical = tmp_path / "canonical"
    legacy = tmp_path / "legacy"
    canonical.mkdir()
    legacy.mkdir()
    (legacy / "kokoro-82m-tts").write_text(
        "model_id: kokoro-82m-tts\nsize_gb: 0.3\nsha256: mock_sha256_kokoro\n"
    )
    (legacy / "span-4k-upscaler").write_text(
        "model_id: span-4k-upscaler\nsize_gb: 0.1\nsha256: mock_sha256_span\n"
    )
    monkeypatch.setattr(
        model_recommender, "model_recommender_cache_read_dirs",
        lambda: [canonical, legacy],
    )
    return canonical, legacy


def test_a_stub_marker_is_never_reported_as_a_loaded_model(stub_marker_cache):
    """75 bytes of YAML is not a model. `doctor` says the weights are missing."""
    mcp = spacepilot_get_local_status()
    http = client.get("/api/compute/local-status").json()

    for payload in (mcp, http):
        assert payload["loaded_models"] == []
        assert sorted(payload["stub_marker_ids"]) == [
            "kokoro-82m-tts", "span-4k-upscaler",
        ]
        assert payload["cached_weight_model_ids"] == []


def test_a_real_weight_file_is_reported(stub_marker_cache):
    canonical, _ = stub_marker_cache
    (canonical / "ltx-video-2b").write_bytes(b"\0" * (2 * 1024 * 1024))

    mcp = spacepilot_get_local_status()
    http = client.get("/api/compute/local-status").json()

    for payload in (mcp, http):
        assert payload["cached_weight_model_ids"] == ["ltx-video-2b"]
        assert "ltx-video-2b" not in payload["stub_marker_ids"]


def test_mcp_and_http_local_status_answer_identically(stub_marker_cache):
    """Same field names, same moment: one answer, not two."""
    with patch("spacepilot.device_probe.probe_local_device", return_value=_profile()):
        mcp = spacepilot_get_local_status()
        http = client.get("/api/compute/local-status").json()
    assert mcp == http


def test_a_stub_marker_is_not_a_downloaded_model_either(stub_marker_cache):
    """`is_downloaded` is the same claim under another name.

    It used its own `> 10 bytes` threshold, so the cache report and this call
    answered opposite things about one file — and this one is what the MCP
    recommender tool and the cockpit's "Downloaded" badge read.
    """
    assert model_recommender.is_model_downloaded("kokoro-82m-tts") is False

    recommendations = model_recommender.recommend_models_for_device()["recommendations"]
    kokoro = next(r for r in recommendations if r["model_id"] == "kokoro-82m-tts")
    assert kokoro["is_downloaded"] is False


def test_a_real_weight_file_is_downloaded(stub_marker_cache):
    canonical, _ = stub_marker_cache
    (canonical / "kokoro-82m-tts").write_bytes(b"\0" * (2 * 1024 * 1024))
    assert model_recommender.is_model_downloaded("kokoro-82m-tts") is True


# ------------------------------------------------- one refusal idiom, not three


def test_every_gated_capability_reports_the_same_shape():
    """Three gated subsystems, one capability-absence shape.

    Without this they drift into three idioms: the reader of a listing then
    needs to know which subsystem it is looking at to know it is looking at a
    gate.
    """
    from spacepilot.model_recommender import MODEL_DOWNLOAD
    from spacepilot.services.checkpoint_sync import CHECKPOINT_SYNC
    from spacepilot.services.lora import LORA_TRAINING

    for capability in (CHECKPOINT_SYNC, LORA_TRAINING, MODEL_DOWNLOAD):
        assert set(capability) == {"name", "implemented", "gated", "detail"}
        assert capability["implemented"] is False
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", capability["gated"])
        assert capability["gated"] in capability["detail"], "the gate names its date"


def test_a_gated_call_refuses_in_its_capability_s_own_words():
    from spacepilot.model_recommender import MODEL_DOWNLOAD, download_model_mock
    from spacepilot.services.checkpoint_sync import CHECKPOINT_SYNC, CheckpointSyncEngine
    from spacepilot.services.lora import LORA_TRAINING, lora_manager

    with pytest.raises(NotImplementedError) as exc:
        CheckpointSyncEngine().create_snapshot("j", 1, 1, 0.1, [])
    assert str(exc.value) == CHECKPOINT_SYNC["detail"]

    with pytest.raises(NotImplementedError) as exc:
        lora_manager.create_training_job(
            name="n", base_model="b", image_paths=[], trigger_word="t")
    assert str(exc.value) == LORA_TRAINING["detail"]

    with pytest.raises(NotImplementedError) as exc:
        download_model_mock("kokoro-82m-tts")
    assert str(exc.value) == MODEL_DOWNLOAD["detail"]


# ---------------------------------------------------------------- bug 3


def _usable_from(text):
    """Every surface prints usable memory the one way: `NN.NN GiB`."""
    m = re.search(r"([0-9]+\.[0-9]{2}) GiB usable", text)
    assert m, f"no usable-memory line in:\n{text}"
    return float(m.group(1))


def test_every_surface_reports_one_usable_memory_and_one_source():
    profile = _profile()
    expected_gib = round(profile.memory_limit_bytes / GIB, 2)

    with patch("spacepilot.device_probe.probe_local_device", return_value=profile), \
         patch("spacepilot.measurements.write_system"), \
         patch("subprocess.run", side_effect=_fake_subprocess):
        doctor = _capture(cmd_doctor, MagicMock(), {})
        probe = _capture(cmd_probe, MagicMock(save=False, json=False), {})
        mcp = spacepilot_get_local_status()
        http = client.get("/api/compute/local-status").json()

    assert _usable_from(doctor) == expected_gib
    assert _usable_from(probe) == expected_gib
    assert mcp["vram_usable_gib"] == mcp["vram_usable_gb"] == expected_gib
    assert http["vram_usable_gib"] == http["vram_usable_gb"] == expected_gib

    assert "source: metal" in doctor
    assert "source: metal" in probe
    assert mcp["memory_limit_source"] == "metal"
    assert http["memory_limit_source"] == "metal"


def test_the_heuristic_is_named_as_a_heuristic_on_every_surface():
    """An unmeasured platform limit must read as a guess, not as a measurement."""
    profile = _profile()
    profile.memory_limit_bytes = None
    profile.memory_limit_source = None

    with patch("spacepilot.device_probe.probe_local_device", return_value=profile), \
         patch("spacepilot.measurements.write_system"), \
         patch("subprocess.run", side_effect=_fake_subprocess):
        doctor = _capture(cmd_doctor, MagicMock(), {})
        probe = _capture(cmd_probe, MagicMock(save=False, json=False), {})
        mcp = spacepilot_get_local_status()
        http = client.get("/api/compute/local-status").json()

    expected_gib = round((32 * GIB - int(32 * GIB * 0.10)) / GIB, 2)
    assert _usable_from(doctor) == expected_gib
    assert _usable_from(probe) == expected_gib
    assert mcp["vram_usable_gb"] == expected_gib
    assert http["vram_usable_gb"] == expected_gib
    for text in (doctor, probe):
        assert "source: heuristic" in text
    assert mcp["memory_limit_source"] == "heuristic"
    assert http["memory_limit_source"] == "heuristic"
