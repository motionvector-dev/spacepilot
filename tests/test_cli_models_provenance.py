"""`models` must surface local measurement evidence rather than a vague badge."""

import argparse

from spacepilot.device_probe import GIB, DeviceProfile
from spacepilot.measurements import Measurement


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
    from spacepilot import measurements as ms

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
    from spacepilot import measurements as ms

    monkeypatch.setattr("spacepilot.device_probe.probe_local_device", _profile)
    monkeypatch.setattr(ms, "load_measurements", lambda: [])

    assert cli.cmd_models(argparse.Namespace(model_id=None)) == 0
    out = capsys.readouterr().out

    assert "SPEED HERE" in out
    assert "kokoro-82m-onnx" in out
    assert "unflown" in out
    assert "huggingface-api · checked 2026-08-25" in out


def test_models_detail_prints_full_caveat_evidence(monkeypatch, capsys):
    import spacepilot.cli as cli
    from spacepilot import measurements as ms

    monkeypatch.setattr("spacepilot.device_probe.probe_local_device", _profile)
    monkeypatch.setattr(ms, "load_measurements", lambda: [])

    assert cli.cmd_models(argparse.Namespace(model_id="distil-large-v3-ggml")) == 0
    out = capsys.readouterr().out

    assert "caveats" in out
    assert "audio.transcription — preserved · declared" in out
    assert "metric  long-form WER (English)" in out
    assert "method  GGML f16 conversion" in out
    assert "huggingface.co/distil-whisper/distil-large-v3-ggml" in out


def test_models_list_has_a_distinct_caveat_column_and_keeps_empty_rows_blank(monkeypatch, capsys):
    import spacepilot.cli as cli
    from spacepilot import measurements as ms

    monkeypatch.setattr("spacepilot.device_probe.probe_local_device", _profile)
    monkeypatch.setattr(ms, "load_measurements", lambda: [])

    assert cli.cmd_models(argparse.Namespace(model_id=None)) == 0
    lines = capsys.readouterr().out.splitlines()

    assert any("CAVEATS" in line for line in lines)
    distil = next(line for line in lines if "distil-large-v3-ggml" in line)
    assert "audio.transcription · preserved · declared" in distil
    kokoro = next(line for line in lines if "kokoro-82m-onnx" in line)
    assert not kokoro.rstrip().endswith(("none", "safe", "preserved"))


def test_missing_method_is_loud_for_a_quantized_caveat():
    import spacepilot.cli as cli
    from types import SimpleNamespace

    caveat = SimpleNamespace(method=None)
    assert cli._caveat_method(caveat, "q5_1") == "method unrecorded"
    assert cli._caveat_method(caveat, "f16") is None
