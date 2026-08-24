"""The corpus API/MCP surfaces are open reads and retain evidence context."""

from fastapi.testclient import TestClient

from spacepilot.pluto import measurements as ms
from spacepilot.pluto.api.routes.measurements import router as measurements_router
from spacepilot.pluto.services import corpus
from spacepilot.web_api import app, require_token


def _records():
    return [
        ms.Measurement(
            schema=1, system_id="test-system", model_id="distil-whisper",
            variant_id="distil-large-v3-ggml", metric="realtime_factor", value=3.0,
            contention="solo", measured_on="2026-08-24T10:00:00+00:00",
        ),
        ms.Measurement(
            schema=1, system_id="test-system", model_id="distil-whisper",
            variant_id="distil-large-v3-ggml", metric="realtime_factor", value=5.0,
            contention="loaded", measured_on="2026-08-25T10:00:00+00:00",
        ),
    ]


def _systems():
    return {"test-system": ms.System(id="test-system", chip="Test Chip", backend="cpu")}


def _fixture_corpus(monkeypatch):
    monkeypatch.setattr(corpus.ms, "load_measurements", _records)
    monkeypatch.setattr(corpus.ms, "load_systems", _systems)


def test_corpus_routes_are_open_and_keep_provenance_streams_and_caveats(monkeypatch):
    _fixture_corpus(monkeypatch)
    client = TestClient(app)

    measurements = client.get("/api/measurements")
    systems = client.get("/api/systems")
    summary = client.get("/api/summary")

    assert measurements.status_code == systems.status_code == summary.status_code == 200
    row = measurements.json()["measurements"][0]
    assert row["provenance"] == "flown"
    assert row["variant_id"] == "distil-large-v3-ggml"
    assert row["caveats"][0]["capability"] == "audio.transcription"
    assert systems.json()["systems"] == [
        {"schema": 1, "id": "test-system", "chip": "Test Chip", "machine_model": None,
         "backend": "cpu", "os_name": None, "os_version": None, "cpu_cores": None,
         "gpu_cores": None, "memory_total_bytes": None, "memory_limit_bytes": None,
         "memory_limit_source": None, "memory_unified": False, "vram_total_bytes": None,
         "host_fingerprint": None, "recorded_on": None, "unknown": {}},
    ]
    item = summary.json()["summaries"][0]
    assert item["provenance"] == "flown"
    assert item["solo_median"] == 3.0
    assert item["observed_median"] == 4.0
    assert item["solo_latest_on"] == "2026-08-24T10:00:00+00:00"
    assert item["observed_latest_on"] == "2026-08-25T10:00:00+00:00"
    assert item["caveats"][0]["provenance"] == "declared"


def test_corpus_routes_have_no_token_dependency():
    routes = {
        route.path: route for route in measurements_router.routes
    }
    assert set(routes) == {"/api/measurements", "/api/systems", "/api/summary"}
    for route in routes.values():
        assert all(dependency.call is not require_token for dependency in route.dependant.dependencies)


def test_corrupt_measurements_are_a_503_not_a_plausible_empty_corpus(monkeypatch):
    monkeypatch.setattr(corpus.ms, "load_measurements", lambda: (_ for _ in ()).throw(ValueError("bad record")))
    response = TestClient(app).get("/api/measurements")
    assert response.status_code == 503
    assert "measurements could not be read" in response.json()["detail"]


def test_mcp_corpus_tools_filter_exact_ids_and_preserve_caveats(monkeypatch):
    _fixture_corpus(monkeypatch)
    from spacepilot.pluto_mcp_server import pluto_measurements, pluto_system_summary

    rows = pluto_measurements("distil-large-v3-ggml")["measurements"]
    assert len(rows) == 2
    assert rows[0]["caveats"][0]["capability"] == "audio.transcription"
    assert pluto_measurements("not-a-variant")["measurements"] == []

    summaries = pluto_system_summary("test-system")["summaries"]
    assert len(summaries) == 1
    assert summaries[0]["variant_id"] == "distil-large-v3-ggml"
    assert summaries[0]["caveats"][0]["status"] == "preserved"


def test_mcp_check_is_a_read_only_probe_with_local_summary(monkeypatch):
    _fixture_corpus(monkeypatch)
    from spacepilot.device_probe import DeviceProfile
    from spacepilot.pluto_mcp_server import pluto_check

    profile = DeviceProfile(chip="Test Chip", backend="cpu", memory_total_bytes=8 * 1024 ** 3)
    monkeypatch.setattr("spacepilot.device_probe.probe_local_device", lambda: profile)

    result = pluto_check()
    assert result["profile"]["chip"] == "Test Chip"
    assert result["system"]["id"] == "test-chip-8gb"
    # The fixture's records are another system class; check does not pretend
    # those numbers were flown here.
    assert result["summaries"] == []
