"""The measurement store keeps the two streams apart and rejects vague records."""

import datetime as dt
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
