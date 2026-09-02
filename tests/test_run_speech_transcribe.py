"""Phase 1.4 speech and transcribe execution tests.

Plan-level tests start no model. The one real-synthesis test runs Kokoro only
when its assets are already on this machine, and skips honestly otherwise.
"""

import json
import wave
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from spacepilot import cli
from spacepilot.device_probe import DeviceProfile, GIB
from spacepilot.drivers.whisper_cpp_driver import (
    WhisperCppDriver, WhisperSubprocessError, audio_duration_seconds,
)
from spacepilot.measurements import Measurement
from spacepilot.services.audio_execution import (
    SPEECH_ROUTES,
    TRANSCRIBE_ROUTES,
    SpeechExecutionService,
    SpeechRequest,
    TranscribeExecutionService,
    TranscribeRequest,
)
from spacepilot.services.execution import LocalExecutionError


def _profile(*, backend="metal", memory_gb=32, free_gb=30):
    return DeviceProfile(
        chip="Apple M1 Max",
        backend=backend,
        memory_total_bytes=memory_gb * GIB,
        memory_free_bytes=free_gb * GIB,
        memory_unified=True,
        memory_limit_bytes=int(memory_gb * GIB * 0.78),
        memory_limit_source="metal",
        disk_free_bytes=100 * GIB,
    )


def _measurement(variant_id, contention, metric="realtime_factor"):
    return Measurement(
        schema=1,
        system_id="apple-m1-max-32gb",
        model_id=variant_id,
        variant_id=variant_id,
        metric=metric,
        value=4.0,
        contention=contention,
        measured_on="2026-08-25T00:00:00+00:00",
    )


class _KokoroFake:
    def __init__(self, *, assets=("model.onnx", "voices.bin"), write=True,
                 duration=2.5, elapsed=1.0, error=None):
        self.assets = assets
        self.write = write
        self.duration = duration
        self.elapsed = elapsed
        self.error = error
        self.resolved_revision = "abc123"
        self.calls = []

    def asset_paths(self):
        return self.assets

    def infer(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        if self.write:
            Path(kwargs["out_path"]).write_bytes(b"RIFF real audio bytes")
        return {
            "status": "completed",
            "model_revision": self.resolved_revision,
            "duration_sec": self.duration,
            "elapsed_sec": self.elapsed,
        }


class _WhisperFake:
    def __init__(self, *, exe="/fake/whisper-cli", model="ggml-base.en.bin",
                 write=True, wall=1.5, audio_seconds=3.0, error=None):
        self.exe = exe
        self.model = model
        self.write = write
        self.wall = wall
        self.audio_seconds = audio_seconds
        self.error = error
        self.calls = []

    def executable(self):
        return self.exe

    def asset_path(self, variant_id=None):
        return self.model

    def infer(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        if self.write:
            Path(kwargs["out_path"]).write_text("a real transcript\n")
        return {
            "status": "completed",
            "model_revision": None,
            "weights": self.model,
            "audio_seconds": self.audio_seconds,
            "wall_seconds": self.wall,
        }


def _speech_service(tmp_path, *, driver=None, rows=(), recorder=None, writer=None):
    return SpeechExecutionService(
        driver=driver or _KokoroFake(),
        profile_probe=_profile,
        measurement_loader=lambda: list(rows),
        measurement_recorder=recorder or (lambda **kw: tmp_path / "measurement.yaml"),
        system_writer=writer or (lambda *a, **kw: tmp_path / "system.yaml"),
        contention_sampler=lambda: "solo",
    )


def _transcribe_service(tmp_path, *, driver=None, rows=(), recorder=None, writer=None):
    return TranscribeExecutionService(
        driver=driver or _WhisperFake(),
        profile_probe=_profile,
        measurement_loader=lambda: list(rows),
        measurement_recorder=recorder or (lambda **kw: tmp_path / "measurement.yaml"),
        system_writer=writer or (lambda *a, **kw: tmp_path / "system.yaml"),
        contention_sampler=lambda: "solo",
    )


def _wav(path: Path, seconds=1.0, rate=16000):
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(b"\x00\x00" * int(rate * seconds))
    return path


def test_routes_are_exact_and_narrow():
    assert [(r.variant_id, r.runtime_id) for r in SPEECH_ROUTES] == [
        ("kokoro-82m-onnx", "kokoro-onnx"),
    ]
    assert [(r.variant_id, r.runtime_id) for r in TRANSCRIBE_ROUTES] == [
        ("whisper-base-en", "whisper-cpp"),
        ("whisper-small-en", "whisper-cpp"),
    ]


def test_only_exact_workloads_are_supported(tmp_path):
    with pytest.raises(ValueError, match="supported: speech"):
        _speech_service(tmp_path).plan("speach")
    with pytest.raises(ValueError, match="supported: transcribe"):
        _transcribe_service(tmp_path).plan("transcription")


def test_speech_missing_assets_is_no_route_and_selects_nothing(tmp_path):
    plan = _speech_service(
        tmp_path, driver=_KokoroFake(assets=(None, None))).plan("speech")
    assert plan.selected is None
    assert plan.candidates[0].route_state == "no route"
    assert "not cached" in plan.candidates[0].route_detail
    text = "\n".join(cli.audio_run_confirmation_lines(plan, tmp_path / "x.wav"))
    assert "No safe local route is available" in text


def test_speech_broken_explicit_assets_state_the_reason(tmp_path):
    class Broken(_KokoroFake):
        def asset_paths(self):
            raise FileNotFoundError("explicit Kokoro model_path/voices_path do not both exist")

    plan = _speech_service(tmp_path, driver=Broken()).plan("speech")
    assert plan.selected is None
    assert "do not both exist" in plan.candidates[0].route_detail


def test_speech_execute_records_realtime_factor_with_exact_variant(tmp_path):
    recorded = {}
    written = []

    def recorder(**fields):
        recorded.update(fields)
        return tmp_path / "measurement.yaml"

    driver = _KokoroFake(duration=2.5, elapsed=1.0)
    service = _speech_service(
        tmp_path, driver=driver, recorder=recorder,
        writer=lambda system: written.append(system) or tmp_path / "system.yaml",
    )
    plan = service.plan("speech")
    output = tmp_path / "out.wav"
    result = service.execute(plan, SpeechRequest("speech", "hello there", "af_heart", output))

    assert result.status == "completed"
    assert result.output.read_bytes().startswith(b"RIFF")
    assert result.realtime_factor == pytest.approx(2.5)
    assert recorded["model_id"] == recorded["variant_id"] == "kokoro-82m-onnx"
    assert recorded["metric"] == "realtime_factor"
    assert recorded["value"] == pytest.approx(2.5)
    assert recorded["runtime_id"] == "kokoro-onnx"
    assert recorded["resolved_revision"] == "abc123"
    assert recorded["knobs"]["voice"] == "af_heart"
    assert len(written) == 1


def test_speech_driver_failure_never_records(tmp_path):
    recorded = MagicMock()
    written = MagicMock()
    driver = _KokoroFake(error=RuntimeError("onnx exploded"))
    service = _speech_service(tmp_path, driver=driver, recorder=recorded, writer=written)
    plan = service.plan("speech")
    with pytest.raises(RuntimeError, match="onnx exploded"):
        service.execute(plan, SpeechRequest("speech", "hello", "af_heart", tmp_path / "x.wav"))
    recorded.assert_not_called()
    written.assert_not_called()


def test_speech_completion_without_artifact_is_failure_and_records_nothing(tmp_path):
    recorded = MagicMock()
    driver = _KokoroFake(write=False)
    service = _speech_service(tmp_path, driver=driver, recorder=recorded)
    plan = service.plan("speech")
    with pytest.raises(LocalExecutionError, match="no new non-empty artifact"):
        service.execute(plan, SpeechRequest("speech", "hello", "af_heart", tmp_path / "x.wav"))
    recorded.assert_not_called()


def test_speech_unknown_voice_refuses_before_the_driver_runs(tmp_path):
    driver = _KokoroFake()
    service = _speech_service(tmp_path, driver=driver)
    plan = service.plan("speech")
    with pytest.raises(LocalExecutionError, match="unknown voice 'af_sarah'"):
        service.execute(plan, SpeechRequest("speech", "hello", "af_sarah", tmp_path / "x.wav"))
    assert driver.calls == []


def test_transcribe_missing_binary_is_no_route_stated(tmp_path):
    class NoBinary(_WhisperFake):
        def executable(self):
            return None

    plan = _transcribe_service(tmp_path, driver=NoBinary()).plan("transcribe")
    assert plan.selected is None
    assert all("whisper-cli not found" in c.route_detail for c in plan.candidates)


def test_transcribe_missing_weights_is_no_route_stated(tmp_path):
    class NoWeights(_WhisperFake):
        def asset_path(self, variant_id=None):
            return None

    plan = _transcribe_service(tmp_path, driver=NoWeights()).plan("transcribe")
    assert plan.selected is None
    assert all("not cached" in c.route_detail for c in plan.candidates)


def test_transcribe_execute_records_realtime_factor_with_exact_variant(tmp_path):
    recorded = {}

    def recorder(**fields):
        recorded.update(fields)
        return tmp_path / "measurement.yaml"

    driver = _WhisperFake(wall=1.5, audio_seconds=3.0)
    service = _transcribe_service(tmp_path, driver=driver, recorder=recorder)
    plan = service.plan("transcribe")
    audio = _wav(tmp_path / "clip.wav")
    result = service.execute(plan, TranscribeRequest("transcribe", audio, tmp_path / "out.txt"))

    assert result.status == "completed"
    assert result.output.read_text() == "a real transcript\n"
    assert result.realtime_factor == pytest.approx(2.0)
    assert recorded["variant_id"] == plan.selected.variant.id
    assert recorded["variant_id"] in {"whisper-base-en", "whisper-small-en"}
    assert recorded["metric"] == "realtime_factor"
    assert recorded["runtime_id"] == "whisper-cpp"
    assert driver.calls[0]["variant_id"] == plan.selected.variant.id


def test_transcribe_without_audio_duration_completes_but_records_nothing(tmp_path):
    recorded = MagicMock()
    driver = _WhisperFake(audio_seconds=None)
    service = _transcribe_service(tmp_path, driver=driver, recorder=recorded)
    audio = _wav(tmp_path / "clip.wav")
    result = service.execute(
        service.plan("transcribe"),
        TranscribeRequest("transcribe", audio, tmp_path / "out.txt"),
    )
    assert result.status == "completed"
    assert result.realtime_factor is None
    assert result.measurement_path is None
    recorded.assert_not_called()


def test_transcribe_driver_failure_never_records(tmp_path):
    recorded = MagicMock()
    driver = _WhisperFake(error=WhisperSubprocessError("boom"))
    service = _transcribe_service(tmp_path, driver=driver, recorder=recorded)
    audio = _wav(tmp_path / "clip.wav")
    with pytest.raises(WhisperSubprocessError, match="boom"):
        service.execute(
            service.plan("transcribe"),
            TranscribeRequest("transcribe", audio, tmp_path / "out.txt"),
        )
    recorded.assert_not_called()


def test_transcribe_missing_input_refuses_before_the_driver_runs(tmp_path):
    driver = _WhisperFake()
    service = _transcribe_service(tmp_path, driver=driver)
    with pytest.raises(LocalExecutionError, match="missing or empty"):
        service.execute(
            service.plan("transcribe"),
            TranscribeRequest("transcribe", tmp_path / "absent.wav", tmp_path / "out.txt"),
        )
    assert driver.calls == []


def test_explicit_whisper_weights_must_match_the_variant_file(tmp_path):
    wrong = tmp_path / "ggml-small.en.bin"
    wrong.write_bytes(b"weights")
    driver = WhisperCppDriver(model_path=str(wrong))
    with pytest.raises(FileNotFoundError, match="needs ggml-base.en.bin"):
        driver.asset_path("whisper-base-en")
    assert driver.asset_path("whisper-small-en") == str(wrong)
    assert driver.resolved_revision is None


def test_audio_duration_reads_wav_and_refuses_to_guess(tmp_path):
    audio = _wav(tmp_path / "clip.wav", seconds=2.0)
    assert audio_duration_seconds(audio) == pytest.approx(2.0)
    junk = tmp_path / "clip.mp3"
    junk.write_bytes(b"not a wav")
    assert audio_duration_seconds(junk) is None


def test_confirmation_has_exact_fact_parity_between_modes(tmp_path):
    plan = _speech_service(
        tmp_path, rows=[_measurement("kokoro-82m-onnx", "solo")]).plan("speech")
    plain = cli.audio_run_confirmation_lines(plan, tmp_path / "x.wav")
    live = cli.audio_run_confirmation_lines(plan, tmp_path / "x.wav")
    assert plain == live
    text = "\n".join(plain)
    assert "FIT" in text and "PROVENANCE" in text and "ROUTE" in text
    assert "flown 4.0× realtime" in text
    assert "network    local files only" in text


def test_cli_speech_non_tty_never_executes_without_yes(tmp_path, capsys):
    service = _speech_service(tmp_path)
    service.execute = MagicMock()
    args = type("Args", (), {
        "run_workload": "speech", "text": "hello", "voice": "af_heart",
        "output": str(tmp_path / "x.wav"), "yes": False,
    })()
    with patch("spacepilot.services.audio_execution.SpeechExecutionService",
               return_value=service), \
         patch.object(cli.sys, "stdin", StringIO("y\n")):
        assert cli.cmd_run(args, {}) == 1
    service.execute.assert_not_called()
    assert "Re-run with --yes" in capsys.readouterr().out


def test_cli_transcribe_refuses_missing_audio_before_confirmation(tmp_path, capsys):
    service = _transcribe_service(tmp_path)
    service.execute = MagicMock()
    args = type("Args", (), {
        "run_workload": "transcribe", "audio": str(tmp_path / "absent.wav"),
        "output": str(tmp_path / "x.txt"), "yes": True,
    })()
    with patch("spacepilot.services.audio_execution.TranscribeExecutionService",
               return_value=service):
        assert cli.cmd_run(args, {}) == 1
    service.execute.assert_not_called()
    assert "does not exist" in capsys.readouterr().out


def test_cli_parser_accepts_speech_and_transcribe(tmp_path):
    with patch("spacepilot.cli.cmd_run", return_value=0) as handler:
        assert cli.main([
            "run", "speech", "--text", "hello", "--voice", "am_michael",
            "--out", str(tmp_path / "x.wav"), "--yes",
        ]) == 0
    args = handler.call_args.args[0]
    assert args.run_workload == "speech"
    assert args.text == "hello"
    assert args.voice == "am_michael"
    assert args.output == str(tmp_path / "x.wav")

    with patch("spacepilot.cli.cmd_run", return_value=0) as handler:
        assert cli.main(["run", "transcribe", str(tmp_path / "a.wav"), "--yes"]) == 0
    args = handler.call_args.args[0]
    assert args.run_workload == "transcribe"
    assert args.audio == str(tmp_path / "a.wav")
    assert args.output is None


def test_speech_honors_spacepilot_python_when_host_venv_lacks_kokoro(tmp_path, monkeypatch):
    """Simulate a bare pipx venv (no kokoro_onnx in host sys.executable) where
    SPACEPILOT_PYTHON points to an interpreter that has kokoro_onnx installed."""
    import subprocess
    from spacepilot.drivers.kokoro_driver import KokoroDriver

    fake_py = "/mock/envs/local-ml-py311/bin/python"
    monkeypatch.setenv("SPACEPILOT_PYTHON", fake_py)

    model_file = tmp_path / "kokoro-v1.0.onnx"
    voices_file = tmp_path / "voices-v1.0.bin"
    model_file.write_bytes(b"mock onnx")
    voices_file.write_bytes(b"mock voices")

    driver = KokoroDriver(
        model_path=str(model_file),
        voices_path=str(voices_file),
        python_bin=fake_py,
    )

    def mock_subprocess_run(cmd, *args, **kwargs):
        if "-c" in cmd and "import kokoro_onnx" in cmd:
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
        if "spacepilot.drivers.kokoro_runner" in cmd:
            out_idx = cmd.index("--output") + 1
            out_wav = Path(cmd[out_idx])
            _wav(out_wav, seconds=2.0)
            payload = json.dumps({
                "status": "completed",
                "voice": "af_heart",
                "speed": 1.0,
                "sample_rate": 24000,
                "duration_sec": 2.0,
                "target_lufs": -16.0,
                "elapsed_sec": 0.8,
                "load_seconds": 0.2,
                "file_path": str(out_wav),
            })
            return subprocess.CompletedProcess(cmd, 0, stdout=f"SPACEPILOT_RESULT {payload}\n", stderr="")
        raise AssertionError(f"unexpected command: {cmd}")

    monkeypatch.setattr(subprocess, "run", mock_subprocess_run)

    service = _speech_service(tmp_path, driver=driver)
    plan = service.plan("speech")
    assert plan.selected is not None
    assert plan.candidates[0].route_state == "ready"
    assert "kokoro-onnx" in plan.candidates[0].route_detail

    output = tmp_path / "speech.wav"
    result = service.execute(plan, SpeechRequest("speech", "hello from external venv", "af_heart", output))
    assert result.status == "completed"
    assert result.output == output
    assert result.audio_seconds == 2.0
    assert result.realtime_factor == pytest.approx(2.0 / 0.8)


def test_speech_missing_kokoro_states_clear_error_naming_spacepilot_python(tmp_path, monkeypatch):
    """When neither host nor configured interpreter has kokoro-onnx, the candidate
    detail explicitly names SPACEPILOT_PYTHON and marks no route."""
    import subprocess
    from spacepilot.drivers.kokoro_driver import KokoroDriver

    fake_py = "/mock/bare/bin/python"
    monkeypatch.setenv("SPACEPILOT_PYTHON", fake_py)

    model_file = tmp_path / "kokoro-v1.0.onnx"
    voices_file = tmp_path / "voices-v1.0.bin"
    model_file.write_bytes(b"mock onnx")
    voices_file.write_bytes(b"mock voices")

    driver = KokoroDriver(
        model_path=str(model_file),
        voices_path=str(voices_file),
        python_bin=fake_py,
    )

    def mock_subprocess_run(cmd, *args, **kwargs):
        if "-c" in cmd and "import kokoro_onnx" in cmd:
            return subprocess.CompletedProcess(
                cmd, 1, stdout="", stderr="ModuleNotFoundError: No module named 'kokoro_onnx'"
            )
        raise AssertionError(f"unexpected command: {cmd}")

    monkeypatch.setattr(subprocess, "run", mock_subprocess_run)

    service = _speech_service(tmp_path, driver=driver)
    plan = service.plan("speech")
    assert plan.selected is None
    assert plan.candidates[0].route_state == "no route"
    detail = plan.candidates[0].route_detail
    assert "kokoro-onnx is unavailable in /mock/bare/bin/python" in detail
    assert "SPACEPILOT_PYTHON" in detail


def _kokoro_assets_here():
    model = Path.home() / ".cache/hyperframes/tts/models/kokoro-v1.0.onnx"
    voices = Path.home() / ".cache/hyperframes/tts/voices/voices-v1.0.bin"
    if model.is_file() and voices.is_file():
        return str(model), str(voices)
    return None


@pytest.mark.skipif(_kokoro_assets_here() is None,
                    reason="Kokoro ONNX assets are not on this machine")
def test_real_kokoro_synthesis_records_a_real_measurement(tmp_path):
    from spacepilot.drivers.kokoro_driver import KokoroDriver
    from spacepilot import runtimes as rt

    driver = KokoroDriver(python_bin=rt.interpreter())
    ready, _ = driver.runtime_ready()
    if not ready:
        pytest.skip("kokoro-onnx is not installed in the active runtime interpreter")

    model, voices = _kokoro_assets_here()
    recorded = {}

    def recorder(**fields):
        recorded.update(fields)
        return tmp_path / "measurement.yaml"

    service = _speech_service(
        tmp_path,
        driver=KokoroDriver(model_path=model, voices_path=voices, python_bin=rt.interpreter()),
        recorder=recorder,
    )
    plan = service.plan("speech")
    assert plan.selected is not None
    output = tmp_path / "real.wav"
    result = service.execute(plan, SpeechRequest("speech", "A short real test.", "af_heart", output))
    assert result.status == "completed"
    assert audio_duration_seconds(output) == pytest.approx(result.audio_seconds, rel=0.05)
    assert recorded["variant_id"] == "kokoro-82m-onnx"
    assert recorded["value"] > 0
    assert recorded["resolved_revision"] is None

