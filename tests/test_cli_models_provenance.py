"""`models` must surface local measurement evidence rather than a vague badge."""

import argparse

from spacepilot.device_probe import GIB, DeviceProfile
from spacepilot.pluto.measurements import Measurement


def _profile():
    return DeviceProfile(
        os_name="macOS", chip="Apple M1 Max", backend="metal",
        memory_total_bytes=32 * GIB, memory_free_bytes=20 * GIB,
        memory_limit_bytes=25 * GIB, memory_limit_source="metal",
        memory_unified=True, disk_free_bytes=100 * GIB,
    )


def _measurement():
    return Measurement(
        schema=1, system_id="apple-m1-max-32gb", model_id="kokoro",
        variant_id="kokoro-82m-onnx", metric="realtime_factor", value=4.0,
        contention="solo", measured_on="2026-08-24T10:00:00+00:00",
    )


def test_models_detail_keeps_local_stream_and_hides_estimated_working_set(monkeypatch, capsys):
    import spacepilot.cli as cli
    from spacepilot.pluto import measurements as ms

    monkeypatch.setattr("spacepilot.device_probe.probe_local_device", _profile)
    monkeypatch.setattr(ms, "load_measurements", lambda: [_measurement()])

    assert cli.cmd_models(argparse.Namespace(model_id="kokoro-82m-onnx")) == 0
    out = capsys.readouterr().out

    assert "speed here flown 4.0× realtime · solo · 1 sample · latest 2026-08-24" in out
    assert "needs     unflown · estimated" in out
    assert "0.7 GB" not in out, "an estimated working set must not look measured"
    assert "uses 3%" not in out, "derived fit percentages are estimated numbers too"
    assert "download  0.3 GB · on paper · huggingface-api · checked 2026-08-25" in out


def test_models_list_labels_rows_without_local_measurements_unflown(monkeypatch, capsys):
    import spacepilot.cli as cli
    from spacepilot.pluto import measurements as ms

    monkeypatch.setattr("spacepilot.device_probe.probe_local_device", _profile)
    monkeypatch.setattr(ms, "load_measurements", lambda: [])

    assert cli.cmd_models(argparse.Namespace(model_id=None)) == 0
    out = capsys.readouterr().out

    assert "SPEED HERE" in out
    assert "kokoro-82m-onnx" in out
    assert "unflown" in out
    assert "huggingface-api · checked 2026-08-25" in out
