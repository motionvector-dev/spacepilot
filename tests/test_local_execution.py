"""Phase 2.5 local execution tests. No test starts mflux or downloads weights."""

from dataclasses import replace
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from spacepilot import cli
from spacepilot.device_probe import DeviceProfile, GIB
from spacepilot.drivers.mflux_driver import MfluxDriver, MfluxSubprocessError
from spacepilot.pluto.measurements import Measurement
from spacepilot.pluto.registry import Caveat
from spacepilot.pluto.services.execution import (
    IMAGE_ROUTES,
    LocalCandidate,
    LocalExecutionError,
    LocalExecutionService,
    RunPlan,
    RunRequest,
    RunResult,
)


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


def _measurement(variant_id, contention):
    return Measurement(
        schema=1,
        system_id="apple-m1-max-32gb",
        model_id=variant_id,
        variant_id=variant_id,
        metric="seconds_per_image",
        value=10.0,
        contention=contention,
        measured_on="2026-08-25T00:00:00+00:00",
    )


class _Driver:
    def __init__(self, bin_dir, *, write=True, timing=True, error=None):
        self.bin_dir = str(bin_dir)
        self.write = write
        self.timing = timing
        self.error = error
        self.calls = []

    def infer(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        if self.write:
            Path(kwargs["out_path"]).write_bytes(b"real image bytes")
        return {
            "status": "completed",
            "wall_seconds": 8.0,
            "generate_seconds": 5.0 if self.timing else None,
            "timing_source": "first-progress-line" if self.timing else "no-progress-line-observed",
        }


def _bin_dir(tmp_path, *names):
    directory = tmp_path / "bin"
    directory.mkdir()
    for name in names or ("mflux-generate", "mflux-generate-flux2"):
        executable = directory / name
        executable.write_text("#!/bin/sh\n")
        executable.chmod(0o755)
    return directory


def _service(tmp_path, *, rows=(), driver=None, profile=None, recorder=None,
             writer=None, sampler=None):
    return LocalExecutionService(
        driver=driver or _Driver(_bin_dir(tmp_path)),
        profile_probe=lambda: profile or _profile(),
        measurement_loader=lambda: list(rows),
        measurement_recorder=recorder or (lambda **kw: tmp_path / "measurement.yaml"),
        system_writer=writer or (lambda *a, **kw: tmp_path / "system.yaml"),
        contention_sampler=sampler or (lambda: "solo"),
    )


def test_routes_are_exact_and_narrow():
    assert [(r.variant_id, r.model_alias) for r in IMAGE_ROUTES] == [
        ("flux-schnell-4bit", "schnell"),
        ("flux2-klein-4b-4bit", "flux2-klein-4b"),
    ]


def test_only_exact_image_workload_is_supported(tmp_path):
    with pytest.raises(ValueError, match="supported: image"):
        _service(tmp_path).plan("images")


def test_rank_is_flown_solo_then_observed_then_unflown(tmp_path):
    rows = [
        _measurement("flux-schnell-4bit", "loaded"),
        _measurement("flux2-klein-4b-4bit", "solo"),
    ]
    plan = _service(tmp_path, rows=rows).plan("image")
    assert [c.variant.id for c in plan.candidates] == [
        "flux2-klein-4b-4bit", "flux-schnell-4bit",
    ]
    assert plan.selected.speed.stream == "solo"


def test_flown_observed_ranks_above_unflown(tmp_path):
    plan = _service(
        tmp_path, rows=[_measurement("flux2-klein-4b-4bit", "loaded")]
    ).plan("image")
    assert plan.selected.variant.id == "flux2-klein-4b-4bit"
    assert plan.selected.speed.stream == "observed"


def test_missing_executables_keep_no_route_rows_and_select_nothing(tmp_path):
    empty = tmp_path / "empty-bin"
    empty.mkdir()
    plan = _service(tmp_path, driver=_Driver(empty)).plan("image")
    assert plan.selected is None
    assert len(plan.candidates) == 2
    assert {c.route_state for c in plan.candidates} == {"no route"}
    assert {c.verdict.verdict for c in plan.candidates} <= {"fits", "tight"}


def test_blocked_rows_are_preserved_and_never_selected(tmp_path):
    plan = _service(tmp_path, profile=_profile(backend="cuda")).plan("image")
    assert plan.selected is None
    assert [c.verdict.verdict for c in plan.candidates] == ["blocked", "blocked"]


def test_file_without_execute_permission_is_no_route(tmp_path):
    directory = _bin_dir(tmp_path)
    (directory / "mflux-generate").chmod(0o644)
    plan = _service(tmp_path, driver=_Driver(directory)).plan("image")
    schnell = next(c for c in plan.candidates if c.route.model_alias == "schnell")
    assert schnell.route_state == "no route"


def test_execute_forces_offline_verifies_artifact_and_records_exact_subject(tmp_path):
    recorded = {}
    written = []

    def recorder(**fields):
        recorded.update(fields)
        return tmp_path / "measurement.yaml"

    driver = _Driver(_bin_dir(tmp_path))
    service = _service(
        tmp_path, driver=driver, recorder=recorder,
        writer=lambda system: written.append(system) or tmp_path / "system.yaml",
        sampler=iter(["solo", "solo"]).__next__,
    )
    plan = service.plan("image")
    output = tmp_path / "result.png"
    result = service.execute(plan, RunRequest("image", "a copper airship", output))

    assert result.status == "completed"
    assert result.output.read_bytes() == b"real image bytes"
    assert driver.calls[0]["env"] == {"HF_HUB_OFFLINE": "1"}
    assert recorded["model_id"] == recorded["variant_id"] == plan.selected.variant.id
    assert recorded["resolved_revision"] is None
    assert recorded["metric"] == "seconds_per_image"
    assert recorded["value"] == 5.0
    assert recorded["knobs"] == {
        "model_alias": plan.selected.route.model_alias,
        "quantisation": "int4", "steps": 4, "width": 512, "height": 512,
    }
    assert len(written) == 1


@pytest.mark.parametrize("preexisting", [False, True])
def test_completion_without_new_artifact_is_failure_and_records_nothing(tmp_path, preexisting):
    recorded = MagicMock()
    written = MagicMock()
    driver = _Driver(_bin_dir(tmp_path), write=False)
    service = _service(tmp_path, driver=driver, recorder=recorded, writer=written)
    plan = service.plan("image")
    output = tmp_path / "result.png"
    if preexisting:
        output.write_bytes(b"old artifact")
    with pytest.raises(LocalExecutionError, match="no new non-empty artifact"):
        service.execute(plan, RunRequest("image", "prompt", output))
    recorded.assert_not_called()
    written.assert_not_called()


def test_real_artifact_without_generation_boundary_succeeds_but_records_no_speed(tmp_path):
    recorded = MagicMock()
    driver = _Driver(_bin_dir(tmp_path), timing=False)
    service = _service(tmp_path, driver=driver, recorder=recorded)
    result = service.execute(
        service.plan("image"), RunRequest("image", "prompt", tmp_path / "result.png")
    )
    assert result.status == "completed"
    assert result.seconds_per_image is None
    assert result.measurement_path is None
    recorded.assert_not_called()


def test_driver_failure_never_records_or_creates_synthetic_output(tmp_path):
    recorded = MagicMock()
    output = tmp_path / "result.png"
    driver = _Driver(_bin_dir(tmp_path), error=MfluxSubprocessError("boom"))
    service = _service(tmp_path, driver=driver, recorder=recorded)
    with pytest.raises(MfluxSubprocessError, match="boom"):
        service.execute(service.plan("image"), RunRequest("image", "prompt", output))
    assert not output.exists()
    recorded.assert_not_called()


def test_confirmation_includes_fit_provenance_route_and_every_unsafe_caveat(tmp_path):
    plan = _service(
        tmp_path, rows=[_measurement("flux2-klein-4b-4bit", "loaded")]
    ).plan("image")
    first = plan.candidates[0]
    caveat = Caveat(
        capability="image.text-rendering", status="degraded",
        provenance="declared", method="weight-only int4", detail="Small text may be malformed.",
    )
    altered = replace(first, variant=replace(first.variant, caveats=[caveat]))
    plan = replace(plan, candidates=(altered, *plan.candidates[1:]))
    text = "\n".join(cli.run_confirmation_lines(plan, tmp_path / "out.png"))
    assert "FIT" in text and "PROVENANCE" in text and "ROUTE" in text
    assert "flown 10.0 s/image · observed" in text
    assert "image.text-rendering — degraded · declared · weight-only int4" in text
    assert "Small text may be malformed." in text
    assert text.index("capability caveats") < len(text)
    assert "network    disabled" in text
    assert "revision is unobserved" in text


def test_non_tty_never_executes_without_yes(tmp_path, capsys):
    service = _service(tmp_path)
    service.execute = MagicMock()
    args = type("Args", (), {
        "run_workload": "image", "prompt": "prompt", "output": str(tmp_path / "x.png"),
        "yes": False, "output_mode": "plain",
    })()
    with patch("spacepilot.pluto.services.execution.LocalExecutionService", return_value=service), \
         patch.object(cli.sys, "stdin", StringIO("y\n")):
        assert cli.cmd_run(args, {}) == 1
    service.execute.assert_not_called()
    assert "Re-run with --yes" in capsys.readouterr().out


def test_tty_eof_never_executes_without_yes(tmp_path, capsys):
    class TTY(StringIO):
        def isatty(self):
            return True

    service = _service(tmp_path)
    service.execute = MagicMock()
    args = type("Args", (), {
        "run_workload": "image", "prompt": "prompt", "output": str(tmp_path / "x.png"),
        "yes": False, "output_mode": "live",
    })()
    with patch("spacepilot.pluto.services.execution.LocalExecutionService", return_value=service), \
         patch.object(cli.sys, "stdin", TTY()), patch("builtins.input", side_effect=EOFError):
        assert cli.cmd_run(args, {}) == 1
    service.execute.assert_not_called()
    assert "Re-run with --yes" in capsys.readouterr().out


def test_yes_executes_without_reading_stdin(tmp_path, capsys):
    service = _service(tmp_path)
    result = RunResult(
        "completed", "flux-schnell-4bit", "schnell", tmp_path / "x.png",
        None, 8.0, 5.0, tmp_path / "measurement.yaml", "first-progress-line",
    )
    service.execute = MagicMock(return_value=result)
    args = type("Args", (), {
        "run_workload": "image", "prompt": "prompt", "output": str(tmp_path / "x.png"),
        "yes": True, "output_mode": "plain",
    })()
    with patch("spacepilot.pluto.services.execution.LocalExecutionService", return_value=service):
        assert cli.cmd_run(args, {}) == 0
    service.execute.assert_called_once()
    assert "completed   flux-schnell-4bit" in capsys.readouterr().out


def test_live_and_plain_confirmation_have_exact_fact_parity(tmp_path):
    plan = _service(tmp_path).plan("image")
    plain = cli.run_confirmation_lines(plan, tmp_path / "out.png")
    live = cli.run_confirmation_lines(plan, tmp_path / "out.png")
    assert plain == live


def test_cli_parser_accepts_only_the_narrow_run_contract(tmp_path):
    with patch("spacepilot.cli.cmd_run", return_value=0) as handler:
        assert cli.main([
            "run", "image", "--prompt", "a lighthouse", "--output", str(tmp_path / "x.png"),
            "--yes", "--plain",
        ]) == 0
    args = handler.call_args.args[0]
    assert args.run_workload == "image"
    assert args.prompt == "a lighthouse"
    assert args.yes is True
    with pytest.raises(SystemExit):
        cli.main(["run", "images", "--prompt", "fuzzy id"])


def test_mflux_refuses_non_executable_file(tmp_path):
    directory = _bin_dir(tmp_path)
    (directory / "mflux-generate").chmod(0o644)
    with pytest.raises(MfluxSubprocessError, match="not executable"):
        MfluxDriver(bin_dir=str(directory)).infer(prompt="prompt", model="schnell")
