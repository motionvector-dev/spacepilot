"""Conservative local text generation through one exact MLX-LM route."""

import json
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from spacepilot import cli
from spacepilot.device_probe import DeviceProfile, GIB


def _profile():
    return DeviceProfile(
        chip="Apple M1 Max",
        backend="metal",
        memory_total_bytes=32 * GIB,
        memory_free_bytes=30 * GIB,
        memory_unified=True,
        memory_limit_bytes=26_800_603_136,
        memory_limit_source="metal",
        disk_free_bytes=100 * GIB,
    )


class _Driver:
    def __init__(self, *, ready=True, write=True, error=None):
        self.ready = ready
        self.write = write
        self.error = error
        self.calls = []

    def route_status(self, variant_id):
        if not self.ready:
            return False, f"no route — weights for {variant_id} are not cached"
        return True, "ready — pinned cache via mlx-lm"

    def infer(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        if self.write:
            Path(kwargs["out_path"]).write_text("A real generated response.\n")
        return {
            "status": "completed",
            "model_revision": "3e6447f082e89cc7f0bc6e5441afd38dfce760ff",
            "wall_seconds": 12.0,
            "load_seconds": 8.0,
            "prompt_tokens": 12,
            "prompt_tps": 40.0,
            "generation_tokens": 24,
            "generation_tps": 6.5,
            "peak_memory_gb": 18.25,
        }


def _service(tmp_path, driver=None, recorder=None):
    from spacepilot.services.text_execution import TextExecutionService

    return TextExecutionService(
        driver=driver or _Driver(),
        profile_probe=_profile,
        measurement_loader=lambda: [],
        measurement_recorder=recorder or (lambda **kw: tmp_path / "measurement.yaml"),
        system_writer=lambda *a, **kw: tmp_path / "system.yaml",
        contention_sampler=lambda: "solo",
    )


def test_registry_has_exact_pinned_qwen_route():
    from spacepilot.model_registry import registry
    from spacepilot.runtimes import load_runtimes

    variant = registry().variant("qwen3-8-27b-4bit")
    assert variant is not None
    assert variant.repo == "mlx-community/Qwen3.8-27B-4bit"
    assert variant.revision == "3e6447f082e89cc7f0bc6e5441afd38dfce760ff"
    assert variant.download.source == "huggingface-api"
    assert variant.download.value == 16_081_486_965
    assert variant.working_set.source == "estimated"
    assert len(variant.files) == 10
    runtime = load_runtimes()["mlx-lm"]
    # mlx-lm now carries the embedding route too — same runtime, same install,
    # a second modality. The text half of the pin is what this test guards.
    assert runtime.serves == ["text", "embedding"]
    assert runtime.runs == ["qwen3-8", "qwen3-embedding"]


def test_uncached_weights_are_no_route_and_never_load(tmp_path):
    service = _service(tmp_path, driver=_Driver(ready=False))
    plan = service.plan("text")
    assert plan.selected is None
    assert "not cached" in plan.candidates[0].route_detail


def test_execute_is_bounded_and_records_real_generation_speed(tmp_path):
    recorded = {}
    driver = _Driver()
    service = _service(
        tmp_path, driver=driver,
        recorder=lambda **fields: recorded.update(fields) or tmp_path / "measurement.yaml",
    )
    from spacepilot.services.text_execution import TextRequest

    plan = service.plan("text")
    output = tmp_path / "answer.txt"
    result = service.execute(plan, TextRequest(
        workload="text", prompt="What is unified memory?", output=output,
        max_tokens=128, max_kv_size=2048, temperature=0.0,
    ))
    assert output.read_text().startswith("A real")
    assert result.generation_tps == pytest.approx(6.5)
    assert recorded["variant_id"] == "qwen3-8-27b-4bit"
    assert recorded["runtime_id"] == "mlx-lm"
    assert recorded["metric"] == "tokens_per_second"
    assert recorded["knobs"]["max_tokens"] == 128
    assert recorded["knobs"]["max_kv_size"] == 2048
    assert driver.calls[0]["max_kv_size"] == 2048


@pytest.mark.parametrize("field,value", [
    ("max_tokens", 0), ("max_tokens", 257),
    ("max_kv_size", 0), ("max_kv_size", 4097),
    ("temperature", -0.1), ("temperature", 2.1),
])
def test_safe_route_rejects_unbounded_knobs(tmp_path, field, value):
    from spacepilot.services.execution import LocalExecutionError
    from spacepilot.services.text_execution import TextRequest

    values = dict(max_tokens=128, max_kv_size=2048, temperature=0.0)
    values[field] = value
    service = _service(tmp_path)
    with pytest.raises(LocalExecutionError):
        service.execute(service.plan("text"), TextRequest(
            workload="text", prompt="hello", output=tmp_path / "x.txt", **values,
        ))


def test_driver_uses_local_snapshot_offline_and_no_sysctl(tmp_path, monkeypatch):
    from spacepilot.drivers.mlx_lm_driver import MlxLmDriver

    snapshot = tmp_path / "snapshot"
    snapshot.mkdir()
    output = tmp_path / "answer.txt"
    metadata = {
        "status": "completed", "wall_seconds": 3.0, "load_seconds": 2.0,
        "prompt_tokens": 2, "prompt_tps": 3.0, "generation_tokens": 4,
        "generation_tps": 5.0, "peak_memory_gb": 6.0,
    }
    seen = {}

    def fake_run(argv, **kwargs):
        seen.update(argv=argv, kwargs=kwargs)
        output.write_text("response\n")
        return type("Proc", (), {
            "returncode": 0, "stdout": "SPACEPILOT_RESULT " + json.dumps(metadata),
            "stderr": "",
        })()

    monkeypatch.setattr("spacepilot.drivers.mlx_lm_driver.subprocess.run", fake_run)
    driver = MlxLmDriver(python_bin="/fake/python")
    monkeypatch.setattr(driver, "asset_dir", lambda variant_id=None: (str(snapshot), "abc"))
    result = driver.infer(
        prompt="hello", out_path=str(output), max_tokens=64,
        max_kv_size=1024, temperature=0.0,
    )
    argv = seen["argv"]
    assert argv[:3] == ["/fake/python", "-m", "spacepilot.drivers.mlx_lm_runner"]
    assert str(snapshot) in argv
    assert "hello" not in argv
    assert seen["kwargs"]["input"] == "hello"
    assert "sysctl" not in " ".join(argv)
    assert seen["kwargs"]["env"]["HF_HUB_OFFLINE"] == "1"
    assert seen["kwargs"]["env"]["TRANSFORMERS_OFFLINE"] == "1"
    assert result["generation_tps"] == 5.0


def test_cli_text_uses_the_configured_runtime_interpreter(tmp_path):
    from spacepilot.drivers.mlx_lm_driver import MlxLmDriver

    service = _service(tmp_path, driver=_Driver(ready=False))
    args = type("Args", (), {
        "run_workload": "text", "prompt": "hello", "output": str(tmp_path / "x.txt"),
        "max_tokens": 64, "max_kv_size": 1024, "temperature": 0.0, "yes": False,
    })()
    with patch("spacepilot.services.text_execution.TextExecutionService",
               return_value=service) as service_cls, \
         patch("spacepilot.drivers.mlx_lm_driver.MlxLmDriver",
               wraps=MlxLmDriver) as driver_cls:
        assert cli.cmd_run(args, {"python_bin": "/configured/python"}) == 1
    assert driver_cls.call_args.kwargs["python_bin"] == "/configured/python"
    selected_driver = service_cls.call_args.kwargs["driver"]
    assert isinstance(selected_driver, MlxLmDriver)
    assert selected_driver.python_bin == "/configured/python"


def test_cli_parser_accepts_safe_text_defaults(tmp_path):
    with patch("spacepilot.cli.cmd_run", return_value=0) as handler:
        assert cli.main([
            "run", "text", "--prompt", "hello", "--output",
            str(tmp_path / "answer.txt"), "--yes",
        ]) == 0
    args = handler.call_args.args[0]
    assert args.run_workload == "text"
    assert args.max_tokens == 256
    assert args.max_kv_size == 4096
    assert args.temperature == 0.0


def test_cli_text_non_tty_never_executes_without_yes(tmp_path, capsys):
    service = _service(tmp_path)
    service.execute = MagicMock()
    args = type("Args", (), {
        "run_workload": "text", "prompt": "hello", "output": str(tmp_path / "x.txt"),
        "max_tokens": 64, "max_kv_size": 1024, "temperature": 0.0, "yes": False,
    })()
    with patch("spacepilot.services.text_execution.TextExecutionService",
               return_value=service), patch.object(cli.sys, "stdin", StringIO("y\n")):
        assert cli.cmd_run(args, {}) == 1
    service.execute.assert_not_called()
    assert "Re-run with --yes" in capsys.readouterr().out
