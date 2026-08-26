"""The overnight sweep runner: spec parsing, resume, disk guard, yielding.

Generation is always faked here — see CLAUDE.md's rule that mflux only ever
runs as a real subprocess, never imported, and this repo's separate rule that
a test suite must not spend real GPU time. `_FakeDriver` stands in for
`MfluxDriver`.
"""

import subprocess
import sys
from pathlib import Path

import pytest

from spacepilot.pluto import measurements as ms
from spacepilot.pluto.sweep import (
    Job,
    RunRecord,
    SweepSpec,
    SweepSpecError,
    expand_jobs,
    load_spec,
    run_sweep,
)

ROOT = Path(__file__).resolve().parents[1]
SPECS_DIR = ROOT / "spacepilot" / "registry" / "sweeps"


class _FakeDriver:
    """Scripted stand-in for MfluxDriver.infer — never touches a real
    subprocess. `fail_on` is a set of (width, height, quantize, steps) tuples
    that raise instead of returning a result, simulating an OOM."""

    def __init__(self, fail_on=None):
        self.fail_on = set(fail_on or ())
        self.calls = []

    def infer(self, **kwargs):
        self.calls.append(kwargs)
        key = (kwargs["width"], kwargs["height"], kwargs["quantize"], kwargs["steps"])
        if key in self.fail_on:
            raise RuntimeError("mflux exited 1: out of memory")
        return {
            "status": "completed", "wall_seconds": 1.2,
            "load_seconds": 0.5, "generate_seconds": 0.7,
        }


class _ScriptedSample:
    """A `sample_fn` that returns a fixed sequence, then repeats the last
    value forever — so a test can script exactly when the machine goes busy
    without depending on anything about the real box it runs on."""

    def __init__(self, sequence):
        self.sequence = list(sequence)
        self.calls = 0

    def __call__(self):
        self.calls += 1
        if self.sequence:
            return self.sequence.pop(0) if len(self.sequence) > 1 else self.sequence[0]
        return "solo"


def _spec(tmp_path=None, **overrides):
    base = dict(
        id="test-sweep", model_id="flux-schnell-4bit", runtime_id="mflux",
        model_alias="schnell", metric="seconds_per_image",
        prompt="a test prompt", seed=1,
        resolutions=[(512, 512), (768, 768)], quantisations=[4], steps=[4],
        max_jobs=40, max_wall_seconds=3600, idle_wait_timeout_minutes=1,
        idle_poll_seconds=0.0, disk_free_floor_gb=1.0,
    )
    base.update(overrides)
    return SweepSpec(**base)


class _Profile:
    os_name = "macOS"
    os_version = "15.6"
    chip = "Apple M1 Max"
    machine_model = "MacBookPro18,4"
    backend = "metal"
    cpu_cores = 10
    gpu_cores = 32
    memory_total_bytes = 34359738368
    memory_free_bytes = 8 * 1024 ** 3
    memory_limit_bytes = 26800603136
    memory_limit_source = "metal"
    memory_unified = True
    vram_total_bytes = None
    unknown = {}


# --------------------------------------------------------------- spec parsing

def test_load_spec_parses_both_seeded_specs():
    """The two real specs this task ships must actually parse — a sweep spec
    reviewed before a night, that then fails to load, defeats the point."""
    klein = load_spec(SPECS_DIR / "flux2-klein-4b-4bit.yaml")
    assert klein.model_alias == "flux2-klein-4b"
    assert klein.quantisations == [4, 8]
    assert len(expand_jobs(klein)) == 3 * 2 * 3

    schnell = load_spec(SPECS_DIR / "flux-schnell-4bit.yaml")
    assert schnell.model_alias == "schnell"
    # schnell is timestep-distilled for 1-4 steps; must not be swept past 4.
    assert schnell.steps == [4]
    assert max(schnell.steps) <= 4
    assert len(expand_jobs(schnell)) == 3 * 2 * 1


def test_load_spec_rejects_a_missing_required_field(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("schema: 1\nid: x\nmodel_id: y\n")  # no model_alias, metric, fixed
    with pytest.raises(SweepSpecError, match="model_alias"):
        load_spec(bad)


def test_load_spec_rejects_an_unknown_metric(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text(
        "schema: 1\nid: x\nmodel_id: y\nmodel_alias: z\nmetric: vibes_per_second\n"
        "fixed:\n  prompt: hi\n  seed: 1\naxes:\n  resolution: [[512, 512]]\n  steps: [4]\n"
    )
    with pytest.raises(SweepSpecError, match="not one of"):
        load_spec(bad)


def test_load_spec_rejects_a_rate_metric(tmp_path):
    """A sweep times jobs and counts no units, so it can only ever produce
    seconds. Under a rate name those seconds are the reciprocal of the number."""
    bad = tmp_path / "bad.yaml"
    bad.write_text(
        "schema: 1\nid: x\nmodel_id: y\nmodel_alias: z\nmetric: realtime_factor\n"
        "fixed:\n  prompt: hi\n  seed: 1\naxes:\n  resolution: [[512, 512]]\n  steps: [4]\n"
    )
    with pytest.raises(SweepSpecError, match="rate"):
        load_spec(bad)


def test_load_spec_rejects_a_bad_schema_version(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("schema: 99\nid: x\n")
    with pytest.raises(SweepSpecError, match="schema"):
        load_spec(bad)


def test_expand_jobs_is_the_full_grid():
    spec = _spec(resolutions=[(512, 512), (1024, 1024)], quantisations=[4, 8], steps=[4, 8])
    jobs = expand_jobs(spec)
    assert len(jobs) == 8
    assert {j.slug for j in jobs} == {
        "512x512-q4-s4", "512x512-q4-s8", "512x512-q8-s4", "512x512-q8-s8",
        "1024x1024-q4-s4", "1024x1024-q4-s8", "1024x1024-q8-s4", "1024x1024-q8-s8",
    }


# ------------------------------------------------------------------- resume

def test_resume_skips_already_recorded_jobs(tmp_path):
    meas_root = tmp_path / "measurements"
    sys_root = tmp_path / "systems"
    outputs = tmp_path / "outputs"
    spec = _spec()

    system = ms.system_from_profile(_Profile())
    ms.write_system(system, root=sys_root)
    # Pre-record the 512x512 job as already done, matching what run_sweep
    # itself would have written for it.
    ms.record(system=system, model_id=spec.model_id, metric=spec.metric, value=0.9,
              contention="solo", root=meas_root, runtime_id="mflux",
              knobs={"width": 512, "height": 512, "quantisation": 4, "steps": 4,
                     "seed": 1, "model_alias": "schnell"})

    driver = _FakeDriver()
    record = run_sweep(
        spec, outputs_dir=outputs, measurements_root=meas_root, systems_root=sys_root,
        runs_dir=tmp_path / "runs", driver=driver,
        sample_fn=_ScriptedSample(["solo"]), sleep_fn=lambda s: None, caffeinate=False,
        profile=_Profile(),
    )

    assert record.jobs_total == 2
    assert record.jobs_skipped == 1
    assert record.jobs_run == 1
    assert len(driver.calls) == 1
    assert driver.calls[0]["width"] == 768   # the one NOT already recorded


def test_a_second_run_with_nothing_left_reports_completed(tmp_path):
    """Every job already on file: the runner should not treat 'nothing to
    do' as an error, and it should not have started caffeinate for zero jobs."""
    meas_root = tmp_path / "measurements"
    sys_root = tmp_path / "systems"
    spec = _spec(resolutions=[(512, 512)], quantisations=[4], steps=[4])

    system = ms.system_from_profile(_Profile())
    ms.write_system(system, root=sys_root)
    ms.record(system=system, model_id=spec.model_id, metric=spec.metric, value=0.9,
              contention="solo", root=meas_root,
              knobs={"width": 512, "height": 512, "quantisation": 4, "steps": 4,
                     "seed": 1, "model_alias": "schnell"})

    driver = _FakeDriver()
    record = run_sweep(
        spec, outputs_dir=tmp_path / "outputs", measurements_root=meas_root,
        systems_root=sys_root, runs_dir=tmp_path / "runs", driver=driver,
        sample_fn=_ScriptedSample(["solo"]), sleep_fn=lambda s: None, caffeinate=False,
        profile=_Profile(),
    )
    assert record.jobs_run == 0
    assert record.stopped_reason == "completed"
    assert driver.calls == []


# --------------------------------------------------------------- failures

def test_a_failed_job_is_recorded_and_excluded_from_the_speed_summary(tmp_path):
    meas_root = tmp_path / "measurements"
    sys_root = tmp_path / "systems"
    spec = _spec(resolutions=[(512, 512), (1024, 1024)], quantisations=[4], steps=[4])

    driver = _FakeDriver(fail_on={(1024, 1024, 4, 4)})
    record = run_sweep(
        spec, outputs_dir=tmp_path / "outputs", measurements_root=meas_root,
        systems_root=sys_root, runs_dir=tmp_path / "runs", driver=driver,
        sample_fn=_ScriptedSample(["solo"]), sleep_fn=lambda s: None, caffeinate=False,
        profile=_Profile(),
    )

    # A failure does not abort the sweep — it is a recorded fact, and the
    # runner moves on to try the rest of the grid.
    assert record.jobs_run == 2
    assert record.jobs_succeeded == 1
    assert record.jobs_failed == 1

    rows = ms.load_measurements(meas_root)
    failed = [m for m in rows if m.status == "failed"]
    assert len(failed) == 1
    assert failed[0].knobs["width"] == 1024
    assert "out of memory" in failed[0].error

    summary = ms.summarise(rows, rows[0].system_id, spec.model_id, spec.metric)
    assert summary.observed_samples == 1       # only the ok one
    assert summary.failed_samples == 1
    assert summary.solo_median == pytest.approx(0.7)   # generate_seconds of the ok job


# ------------------------------------------------------------------ disk guard

def test_disk_guard_refuses_to_start(tmp_path, monkeypatch):
    import spacepilot.pluto.sweep as sweep_mod
    monkeypatch.setattr(sweep_mod, "disk_free_gb", lambda path: 1.0)

    spec = _spec(disk_free_floor_gb=999.0)
    driver = _FakeDriver()
    record = run_sweep(
        spec, outputs_dir=tmp_path / "outputs", measurements_root=tmp_path / "measurements",
        systems_root=tmp_path / "systems", runs_dir=tmp_path / "runs", driver=driver,
        sample_fn=_ScriptedSample(["solo"]), sleep_fn=lambda s: None, caffeinate=False,
        profile=_Profile(),
    )
    assert record.stopped_reason == "disk_floor_before_start"
    assert record.jobs_run == 0
    assert driver.calls == []


def test_disk_guard_aborts_mid_sweep(tmp_path, monkeypatch):
    """Free space measured fresh, and low, before the second job — the guard
    must catch a disk that filled up mid-run, not only an already-full one."""
    import spacepilot.pluto.sweep as sweep_mod
    readings = iter([500.0, 500.0, 0.5, 0.5, 0.5])  # plenty, then it drops
    monkeypatch.setattr(sweep_mod, "disk_free_gb", lambda path: next(readings, 0.5))

    spec = _spec(resolutions=[(512, 512), (768, 768)], disk_free_floor_gb=10.0)
    driver = _FakeDriver()
    record = run_sweep(
        spec, outputs_dir=tmp_path / "outputs", measurements_root=tmp_path / "measurements",
        systems_root=tmp_path / "systems", runs_dir=tmp_path / "runs", driver=driver,
        sample_fn=_ScriptedSample(["solo"]), sleep_fn=lambda s: None, caffeinate=False,
        profile=_Profile(),
    )
    assert record.stopped_reason == "disk_floor_mid_sweep"
    assert record.jobs_run == 1


# --------------------------------------------------------------------- yield

def test_runner_yields_when_the_machine_stops_being_idle(tmp_path):
    """Idleness is re-checked before every job. Scripted so the machine reads
    solo for the idle-wait and the first job, then loaded before the second —
    the runner must stop cleanly there rather than running the second job."""
    spec = _spec(resolutions=[(512, 512), (768, 768), (1024, 1024)])
    driver = _FakeDriver()
    sample = _ScriptedSample(["solo", "solo", "loaded"])

    record = run_sweep(
        spec, outputs_dir=tmp_path / "outputs", measurements_root=tmp_path / "measurements",
        systems_root=tmp_path / "systems", runs_dir=tmp_path / "runs", driver=driver,
        sample_fn=sample, sleep_fn=lambda s: None, caffeinate=False,
        profile=_Profile(),
    )
    assert record.stopped_reason == "human_returned"
    assert record.jobs_run == 1
    assert len(driver.calls) == 1


def test_wait_for_idle_gives_up_and_exits_cleanly(tmp_path):
    """The machine never goes idle within the window: no job ever runs, and
    caffeinate — which only matters once jobs are about to run — is never
    started (checked via the driver never being called and no caffeinate
    subprocess having a chance to leak)."""
    spec = _spec(idle_wait_timeout_minutes=0.001, idle_poll_seconds=0.0)
    driver = _FakeDriver()
    clock = {"t": 0.0}

    def clock_fn():
        clock["t"] += 10  # advances past any timeout on the very first check
        return clock["t"]

    record = run_sweep(
        spec, outputs_dir=tmp_path / "outputs", measurements_root=tmp_path / "measurements",
        systems_root=tmp_path / "systems", runs_dir=tmp_path / "runs", driver=driver,
        sample_fn=_ScriptedSample(["loaded"]), sleep_fn=lambda s: None,
        clock_fn=clock_fn, caffeinate=False, profile=_Profile(),
    )
    assert record.stopped_reason == "never_idle"
    assert record.jobs_run == 0
    assert driver.calls == []


# --------------------------------------------------------------- caffeinate

def test_caffeinate_is_started_and_released(tmp_path, monkeypatch):
    calls = {"popen": 0, "terminate": 0}

    class _FakeProc:
        def terminate(self):
            calls["terminate"] += 1

        def wait(self, timeout=None):
            return 0

    def fake_popen(*a, **k):
        calls["popen"] += 1
        return _FakeProc()

    monkeypatch.setattr("spacepilot.pluto.sweep.subprocess.Popen", fake_popen)
    monkeypatch.setattr("spacepilot.pluto.sweep.sys.platform", "darwin")

    spec = _spec(resolutions=[(512, 512)])
    driver = _FakeDriver()
    run_sweep(
        spec, outputs_dir=tmp_path / "outputs", measurements_root=tmp_path / "measurements",
        systems_root=tmp_path / "systems", runs_dir=tmp_path / "runs", driver=driver,
        sample_fn=_ScriptedSample(["solo"]), sleep_fn=lambda s: None,
        caffeinate=True, profile=_Profile(),
    )
    assert calls["popen"] == 1
    assert calls["terminate"] == 1


def test_caffeinate_is_released_even_when_a_job_raises_unexpectedly(tmp_path, monkeypatch):
    """Not an mflux failure (those are caught and recorded) — an unexpected
    exception from inside the loop must still release caffeinate rather than
    leaving the Mac unable to sleep."""
    calls = {"terminate": 0}

    class _FakeProc:
        def terminate(self):
            calls["terminate"] += 1

        def wait(self, timeout=None):
            return 0

    monkeypatch.setattr("spacepilot.pluto.sweep.subprocess.Popen", lambda *a, **k: _FakeProc())
    monkeypatch.setattr("spacepilot.pluto.sweep.sys.platform", "darwin")

    class _ExplodingSample:
        def __init__(self):
            self.n = 0

        def __call__(self):
            self.n += 1
            if self.n <= 1:
                return "solo"
            raise RuntimeError("boom")

    spec = _spec(resolutions=[(512, 512), (768, 768)])
    with pytest.raises(RuntimeError, match="boom"):
        run_sweep(
            spec, outputs_dir=tmp_path / "outputs", measurements_root=tmp_path / "measurements",
            systems_root=tmp_path / "systems", runs_dir=tmp_path / "runs",
            driver=_FakeDriver(), sample_fn=_ExplodingSample(), sleep_fn=lambda s: None,
            caffeinate=True, profile=_Profile(),
        )
    assert calls["terminate"] == 1


# ------------------------------------------------------------------------ CLI

def test_sweep_dry_run_lists_the_grid_without_generating_anything():
    proc = subprocess.run(
        [sys.executable, "-m", "spacepilot.cli", "sweep", "run",
         str(SPECS_DIR / "flux-schnell-4bit.yaml"), "--dry-run"],
        cwd=ROOT, capture_output=True, text=True, timeout=60,
    )
    assert proc.returncode == 0, proc.stderr[-2000:]
    assert "6 jobs in the grid" in proc.stdout
    assert "512x512-q4-s4" in proc.stdout


def test_sweep_run_reports_a_bad_spec_without_a_traceback(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("schema: 1\nid: x\n")
    proc = subprocess.run(
        [sys.executable, "-m", "spacepilot.cli", "sweep", "run", str(bad)],
        cwd=ROOT, capture_output=True, text=True, timeout=60,
    )
    assert proc.returncode == 1
    assert "Bad sweep spec" in proc.stdout
    assert "Traceback" not in proc.stderr
