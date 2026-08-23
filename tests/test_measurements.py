"""The measurement store keeps the two streams apart and rejects vague records."""

import datetime as dt
import os
from pathlib import Path

import pytest
import yaml

from src.pluto.measurements import (
    Measurement,
    MeasurementError,
    System,
    load_measurements,
    load_systems,
    parse_measurement,
    record,
    sample_contention,
    summarise,
    system_from_profile,
    system_id_for,
    write_system,
)


class _Profile:
    """Minimal stand-in for DeviceProfile; the store only reads attributes."""
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


@pytest.fixture
def system():
    return system_from_profile(_Profile())


def test_system_id_describes_a_configuration_not_a_machine(system):
    """Two identical boxes must land on one id, or samples cannot be pooled."""
    assert system.id == "apple-m1-max-32gb"
    assert system_id_for(_Profile()) == system.id


def test_fingerprint_does_not_leak_the_hostname(system):
    import platform
    host = platform.node()
    assert system.host_fingerprint
    assert len(system.host_fingerprint) == 12
    if host:
        assert host not in system.host_fingerprint
        assert host.split(".")[0].lower() not in system.host_fingerprint.lower()


def test_a_record_without_contention_is_refused(tmp_path):
    """The whole point of the store is that a sample says whether the box was busy."""
    raw = {
        "schema": 1, "system_id": "apple-m1-max-32gb", "model_id": "flux",
        "metric": "seconds_per_image", "value": 12.0,
        "measured_on": "2026-08-23T00:00:00+00:00",
    }
    with pytest.raises(MeasurementError, match="missing 'contention'"):
        parse_measurement(raw, "inline")

    raw["contention"] = "probably fine"
    with pytest.raises(MeasurementError, match="never merged"):
        parse_measurement(raw, "inline")


def test_an_unknown_metric_is_refused():
    with pytest.raises(MeasurementError, match="not one of"):
        record(system=System(id="x"), model_id="flux",
               metric="vibes_per_second", value=1.0)


def test_a_loaded_sample_never_moves_the_solo_ceiling(system, tmp_path):
    """Darkbloom keeps two streams because an averaged ceiling collapses under load."""
    for value, state in [(10.0, "solo"), (12.0, "solo"), (40.0, "loaded")]:
        record(system=system, model_id="flux", metric="seconds_per_image",
               value=value, contention=state, root=tmp_path, runtime_id="mflux")

    rows = load_measurements(tmp_path)
    assert len(rows) == 3

    s = summarise(rows, system.id, "flux", "seconds_per_image")
    assert s.solo_median == 11.0 and s.solo_samples == 2
    assert s.observed_median == 12.0 and s.observed_samples == 3


def test_unknown_contention_is_excluded_from_the_solo_stream(system, tmp_path):
    """A sample that could not be classified must not be assumed idle."""
    record(system=system, model_id="flux", metric="seconds_per_image",
           value=9.0, contention="unknown", root=tmp_path)
    s = summarise(load_measurements(tmp_path), system.id, "flux", "seconds_per_image")
    assert s.solo_samples == 0
    assert s.observed_samples == 1


def test_records_land_under_system_and_model(system, tmp_path):
    path = record(system=system, model_id="Kokoro-82M", metric="realtime_factor",
                  value=4.6, contention="solo", root=tmp_path, runtime_id="kokoro-onnx")
    assert path.parent == tmp_path / system.id / "kokoro-82m"
    written = yaml.safe_load(path.read_text())
    assert written["runtime_id"] == "kokoro-onnx"
    assert written["backend"] == "metal"          # inherited from the system
    assert "note" not in written                  # empty fields are not written


def test_knobs_survive_the_round_trip(system, tmp_path):
    """Steps and resolution decide the number; a record without them is unusable."""
    knobs = {"steps": 4, "resolution": [1024, 1024], "seed": 42}
    record(system=system, model_id="flux", metric="seconds_per_image", value=12.5,
           contention="solo", root=tmp_path, knobs=knobs, quantisation="4bit")
    got = load_measurements(tmp_path)[0]
    assert got.knobs == knobs
    assert got.quantisation == "4bit"


def test_system_records_round_trip(system, tmp_path):
    write_system(system, root=tmp_path)
    loaded = load_systems(tmp_path)
    assert loaded[system.id].memory_limit_source == "metal"
    assert loaded[system.id].memory_limit_bytes == 26800603136


def test_contention_is_sampled_not_declared():
    assert sample_contention() in {"solo", "loaded", "unknown"}


class _FakeProc:
    """Enough of psutil.Process to drive `_external_cpu_percent`: a pid and a
    fixed cpu_percent() reading, independent of real wall-clock timing or
    real machine load — so this test is not at the mercy of whatever else
    happens to be running on the box it executes on."""

    def __init__(self, pid: int, cpu_percent: float):
        self.pid = pid
        self._cpu = cpu_percent

    def cpu_percent(self, interval=None):
        return self._cpu


def _own_and_external(own_cpu: float, external_cpu: float):
    """A fixed roster: one heavy process at pid 1 (`own tree`), one process at
    pid 99 standing in for a genuine competitor. Which one counts as "ours" is
    controlled per-test via `own_pids`, isolating that as the only variable —
    the same variable the real fix turns on."""
    return [_FakeProc(1, own_cpu), _FakeProc(99, external_cpu)]


def test_our_own_heavy_work_can_record_solo(monkeypatch):
    """The bug this test was written against: `sample_contention` used to be
    `os.getloadavg()[0] / cpu_count <= 0.4`, which counts every process on the
    box, ours included. Any measurement heavy enough to be worth taking (an
    mflux subprocess saturating every core) pushed the load average over the
    threshold by the time it finished — so `solo` was unreachable by
    construction, proven empirically today: load 3.63 before a generation run,
    5.76 after, recorded `loaded`, on a machine nothing else was using.

    Confirmed by hand that this fails against the pre-fix implementation: run
    `sample_contention()` from a process saturating every core with its own
    children (standing in for the mflux subprocess a real measurement spawns)
    and the old load-average-only code returns "loaded" every time — the pid
    doing the work is invisible to `os.getloadavg()`, which only sees the
    aggregate. `git stash` the pre-fix `measurements.py` and this same
    scenario, run with real subprocesses instead of the fakes below,
    reproduces the failure (`assert 'loaded' == 'solo'`).

    The fakes below (rather than real spawned processes) are what make this
    version of the test reliable to run on this box: this is a shared dev
    machine and other real sessions are, right now, genuinely saturating
    several cores — a real-process version of this test is correctly flaky
    under that actual contention, which is not a bug, it is the fix working.
    Faking `psutil.process_iter` removes that dependency on the box's real
    state and isolates the one thing under test: CPU attributed to our own
    tree (pid 1 here) must not count as contention, no matter how heavy.
    """
    import src.pluto.measurements as ms

    monkeypatch.setattr(ms.psutil, "process_iter",
                         lambda *a, **k: _own_and_external(own_cpu=800.0, external_cpu=2.0))
    state = sample_contention(own_pids={1}, interval=0.0)
    assert state == "solo", (
        "CPU attributed to our own process tree was counted as contention — "
        "this is the exact bug: a measurement of our own work can never record solo"
    )


def test_a_genuine_competitor_mid_run_still_reads_loaded(monkeypatch):
    """Redefining contention must not just disable the check — the same
    roster as above, but this time the heavy pid is NOT in `own_pids`, i.e.
    exactly what production sees when a process it never spawned is eating a
    core: it must still read `loaded`. Isolates the one variable that
    matters — whether a busy pid is counted as "ours" — the same way the
    solo case above does.
    """
    import src.pluto.measurements as ms

    monkeypatch.setattr(ms.psutil, "process_iter",
                         lambda *a, **k: _own_and_external(own_cpu=800.0, external_cpu=2.0))
    # pid 1 (the heavy one) is deliberately absent from own_pids here.
    state = sample_contention(own_pids={os.getpid()}, interval=0.0)
    assert state == "loaded"


def test_a_failed_measurement_is_excluded_from_the_speed_summary(system, tmp_path):
    """An OOM at a given resolution/quantisation is real information — it says
    where this machine stops — but its `value` is not a speed number and must
    never move a median a caller reads as "how fast is this"."""
    record(system=system, model_id="flux", metric="seconds_per_image", value=11.0,
           contention="solo", root=tmp_path, status="ok")
    record(system=system, model_id="flux", metric="seconds_per_image", value=0.4,
           contention="solo", root=tmp_path, status="failed",
           error="mflux exited 1: out of memory", knobs={"resolution": [1024, 1024]})

    rows = load_measurements(tmp_path)
    assert len(rows) == 2
    s = summarise(rows, system.id, "flux", "seconds_per_image")
    assert s.solo_samples == 1 and s.solo_median == 11.0
    assert s.observed_samples == 1
    assert s.failed_samples == 1


def test_an_unknown_status_is_refused():
    with pytest.raises(MeasurementError, match="not one of"):
        record(system=System(id="x"), model_id="flux", metric="seconds_per_image",
               value=1.0, status="crashed")
