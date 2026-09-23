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
    assert runtime.runs == [
        "qwen3-8", "qwen1-5-moe", "mimo-v2-6-distill-qwen-9b",
        "gemma4-26b-a4b", "maple-preview", "ternary-bonsai-2-27b",
        "lfm2-5-8b-a1b", "qwen3-embedding",
    ]


def test_uncached_weights_are_no_route_and_never_load(tmp_path):
    service = _service(tmp_path, driver=_Driver(ready=False))
    plan = service.plan("text")
    assert plan.selected is None
    assert "not cached" in plan.candidates[0].route_detail


def test_execute_is_bounded_and_records_real_generation_speed(tmp_path):
    calls = []
    driver = _Driver()
    service = _service(
        tmp_path, driver=driver,
        recorder=lambda **fields: calls.append(fields) or tmp_path / "measurement.yaml",
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
    # Two rows, same run: decode speed and prefill speed are different phases.
    decode, prefill = calls
    assert decode["variant_id"] == "qwen3-8-27b-4bit"
    assert decode["runtime_id"] == "mlx-lm"
    assert decode["metric"] == "tokens_per_second"
    assert decode["knobs"]["max_tokens"] == 128
    assert decode["knobs"]["thinking"] == "off"
    assert decode["knobs"]["max_kv_size"] == 2048
    assert prefill["metric"] == "prompt_tokens_per_second"
    assert prefill["run_id"] == decode["run_id"]
    assert driver.calls[0]["max_kv_size"] == 2048


def test_plan_serves_every_mlx_lm_text_variant_not_just_the_default(tmp_path):
    """The daemon now serves every text variant mlx-lm declares it runs."""
    recorded = {}
    driver = _Driver()
    service = _service(
        tmp_path, driver=driver,
        recorder=lambda **fields: recorded.update(fields) or tmp_path / "measurement.yaml",
    )
    from spacepilot.services.text_execution import TextRequest

    plan = service.plan("text", variant_id="qwen1-5-moe-a2-7b-chat-4bit")
    assert plan.selected is not None
    assert plan.selected.variant.id == "qwen1-5-moe-a2-7b-chat-4bit"
    result = service.execute(plan, TextRequest(
        workload="text", prompt="What is a mixture of experts?",
        output=tmp_path / "moe-answer.txt",
        max_tokens=64, max_kv_size=1024, temperature=0.0,
    ))
    assert result.variant_id == "qwen1-5-moe-a2-7b-chat-4bit"
    assert recorded["variant_id"] == "qwen1-5-moe-a2-7b-chat-4bit"
    assert recorded["model_id"] == "qwen1-5-moe-a2-7b-chat-4bit"
    assert driver.calls[0]["variant_id"] == "qwen1-5-moe-a2-7b-chat-4bit"


def test_plan_with_no_variant_id_still_defaults_to_the_first_served_variant(tmp_path):
    service = _service(tmp_path)
    plan = service.plan("text")
    assert plan.candidates[0].variant.id == "qwen3-8-27b-4bit"


def test_plan_rejects_a_variant_the_registry_does_not_know(tmp_path):
    from spacepilot.services.execution import LocalExecutionError

    service = _service(tmp_path)
    with pytest.raises(LocalExecutionError):
        service.plan("text", variant_id="not-a-real-variant")


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
    # The runner goes by file path, not `-m`: mlx-lm's isolated venv has
    # mlx_lm in it and no `spacepilot` package to import.
    assert argv[0] == "/fake/python"
    assert argv[1].endswith("mlx_lm_runner.py")
    assert str(snapshot) in argv
    assert "hello" not in argv
    assert seen["kwargs"]["input"] == "hello"
    assert "--thinking" in argv
    assert argv[argv.index("--thinking") + 1] == "off"
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
    assert args.thinking == "off"
    assert args.model is None


def test_cli_parser_accepts_a_model_flag(tmp_path):
    with patch("spacepilot.cli.cmd_run", return_value=0) as handler:
        assert cli.main([
            "run", "text", "--prompt", "hello", "--model",
            "qwen1-5-moe-a2-7b-chat-4bit", "--yes",
        ]) == 0
    assert handler.call_args.args[0].model == "qwen1-5-moe-a2-7b-chat-4bit"


def test_an_unclosed_think_block_is_recorded_and_is_not_success(tmp_path):
    from spacepilot.services.execution import LocalExecutionError
    from spacepilot.services.text_execution import TextRequest

    driver = _Driver(write=False)
    calls = []

    def infer(**kwargs):
        driver.calls.append(kwargs)
        Path(kwargs["out_path"]).write_text("<think>\nstill reasoning")
        return {
            "status": "completed",
            "model_revision": "abc",
            "wall_seconds": 2.0, "load_seconds": 1.0,
            "prompt_tokens": 8, "prompt_tps": 20.0,
            "generation_tokens": 64, "generation_tps": 30.0,
            "peak_memory_gb": 5.0,
        }

    driver.infer = infer
    service = _service(
        tmp_path, driver=driver,
        recorder=lambda **fields: calls.append(fields) or tmp_path / "m.yaml",
    )
    with pytest.raises(LocalExecutionError, match="unclosed"):
        service.execute(service.plan("text"), TextRequest(
            workload="text", prompt="2+2", output=tmp_path / "x.txt",
            max_tokens=64, max_kv_size=1024, temperature=0.0,
        ))
    assert (tmp_path / "x.txt").read_text().startswith("<think>")
    assert len(calls) == 1
    assert calls[0]["status"] == "failed"
    assert calls[0]["knobs"]["generation_tps"] == pytest.approx(30.0)
    assert "not an answer" in calls[0]["note"]


def test_a_closed_think_with_an_answer_still_succeeds(tmp_path):
    from spacepilot.services.text_execution import TextRequest

    driver = _Driver(write=False)

    def infer(**kwargs):
        driver.calls.append(kwargs)
        Path(kwargs["out_path"]).write_text("<think>\narithmetic\n</think>\n\n4")
        return {
            "status": "completed",
            "model_revision": "abc",
            "wall_seconds": 2.0, "load_seconds": 1.0,
            "prompt_tokens": 8, "prompt_tps": 20.0,
            "generation_tokens": 12, "generation_tps": 30.0,
            "peak_memory_gb": 5.0,
        }

    driver.infer = infer
    service = _service(tmp_path, driver=driver)
    result = service.execute(service.plan("text"), TextRequest(
        workload="text", prompt="2+2", output=tmp_path / "x.txt",
    ))
    assert result.status == "completed"


def test_apply_chat_passes_thinking_off_and_falls_back(tmp_path):
    from spacepilot.drivers.mlx_lm_runner import apply_chat

    class _Tok:
        def apply_chat_template(self, messages, **kwargs):
            self.kwargs = kwargs
            return "PROMPT"

    tok = _Tok()
    assert apply_chat(tok, [{"role": "user", "content": "hi"}], thinking=False) == "PROMPT"
    assert tok.kwargs["enable_thinking"] is False

    class _Old:
        def apply_chat_template(self, messages, tokenize=False, add_generation_prompt=False):
            return "PLAIN"

    assert apply_chat(_Old(), [{"role": "user", "content": "hi"}], thinking=True) == "PLAIN"


def test_architecture_ready_accepts_a_local_model_file_and_rejects_an_unknown_type(tmp_path):
    import sys
    from spacepilot.drivers.mlx_lm_driver import MlxLmDriver

    driver = MlxLmDriver(python_bin=sys.executable)
    maple = tmp_path / "maple"
    maple.mkdir()
    (maple / "maple.py").write_text("class Model: pass\n")
    (maple / "config.json").write_text('{"model_type": "maple", "model_file": "maple.py"}\n')
    ok, detail = driver.architecture_ready(str(maple))
    assert ok, detail

    bonsai = tmp_path / "bonsai"
    bonsai.mkdir()
    (bonsai / "config.json").write_text('{"model_type": "prism_hadamard_qwen35"}\n')
    ok, detail = driver.architecture_ready(str(bonsai))
    assert not ok
    assert "prism_hadamard_qwen35" in detail


def test_cli_run_text_model_flag_selects_the_requested_variant(tmp_path):
    service = _service(tmp_path, driver=_Driver(ready=False))
    plan_calls = []
    real_plan = service.plan
    service.plan = lambda workload, variant_id=None: (
        plan_calls.append(variant_id) or real_plan(workload, variant_id=variant_id))
    args = type("Args", (), {
        "run_workload": "text", "prompt": "hello", "output": str(tmp_path / "x.txt"),
        "model": "qwen1-5-moe-a2-7b-chat-4bit",
        "max_tokens": 64, "max_kv_size": 1024, "temperature": 0.0, "yes": False,
    })()
    with patch("spacepilot.services.text_execution.TextExecutionService",
               return_value=service):
        assert cli.cmd_run(args, {}) == 1
    assert plan_calls == ["qwen1-5-moe-a2-7b-chat-4bit"]


def test_cli_run_text_defaults_to_and_prints_the_first_served_variant(tmp_path, capsys):
    service = _service(tmp_path, driver=_Driver(ready=False))
    args = type("Args", (), {
        "run_workload": "text", "prompt": "hello", "output": str(tmp_path / "x.txt"),
        "max_tokens": 64, "max_kv_size": 1024, "temperature": 0.0, "yes": False,
    })()
    with patch("spacepilot.services.text_execution.TextExecutionService",
               return_value=service):
        assert cli.cmd_run(args, {}) == 1
    out = capsys.readouterr().out
    assert "qwen3-8-27b-4bit" in out
    assert "default" in out


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
