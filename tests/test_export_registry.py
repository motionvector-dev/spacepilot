"""The public registry must carry what was measured, not only what was cited.

A variant could hold a real timing in `registry/measurements/` and still export
as having no speed data at all, because the exporter read only the curated
`speed:` block in the model YAML. That is how every FLUX.2 Klein variant
published as unmeasured while two runs sat on disk beside it.
"""
import importlib.util
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]


def _exporter():
    spec = importlib.util.spec_from_file_location(
        "export_registry", ROOT / "tools" / "export_registry.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["export_registry"] = module
    spec.loader.exec_module(module)
    return module


def _record(tmp_path, **fields):
    base = {
        "schema": 1,
        "system_id": "test-box",
        "model_id": "kokoro-82m",
        "variant_id": "kokoro-82m",
        "metric": "seconds_per_image",
        "value": 10.0,
        "contention": "solo",
        "measured_on": "2026-08-23T00:00:00+00:00",
    }
    base.update(fields)
    d = tmp_path / base["system_id"] / base["variant_id"]
    d.mkdir(parents=True, exist_ok=True)
    name = f"{base['metric']}-{base['contention']}-{base['value']}.yaml"
    (d / name).write_text(yaml.safe_dump(base))


@pytest.fixture
def store(tmp_path, monkeypatch):
    """Point the measurement store at a temp dir, so the test never depends on
    which runs happen to be recorded in the repo."""
    root = tmp_path / "measurements"
    root.mkdir()
    import src.pluto.measurements as ms
    monkeypatch.setattr(ms, "MEASUREMENTS_DIR", root)
    return root


def test_measured_runs_reach_the_published_variant(store):
    _record(store, contention="solo", value=8.0)
    _record(store, contention="loaded", value=12.0)

    module = _exporter()
    models = [{"id": "kokoro", "variants": [{"id": "kokoro-82m"}, {"id": "other"}]}]
    attached = module.attach_measurements(models)

    assert attached == 1, "only the variant with records should gain measurements"
    assert "measurements" not in models[0]["variants"][1]

    got = models[0]["variants"][0]["measurements"]
    assert len(got) == 1, "one summary per (system, metric) pair"
    assert got[0]["system_id"] == "test-box"
    assert got[0]["metric"] == "seconds_per_image"


def test_the_two_streams_stay_separate(store):
    """Solo is what the machine can do; observed includes the busy runs. A
    single median hides exactly the contention the scheduler needs to see."""
    _record(store, contention="solo", value=8.0)
    _record(store, contention="loaded", value=12.0)
    _record(store, contention="loaded", value=16.0)

    module = _exporter()
    models = [{"id": "kokoro", "variants": [{"id": "kokoro-82m"}]}]
    module.attach_measurements(models)
    summary = models[0]["variants"][0]["measurements"][0]

    assert summary["solo_median"] == 8.0
    assert summary["solo_samples"] == 1
    assert summary["observed_samples"] == 3
    assert summary["observed_median"] == 12.0


def test_a_variant_measured_only_under_load_publishes_no_solo_number(store):
    """The honest case today: every FLUX run so far met a busy box, so the
    page must be able to say 'no solo sample' rather than quoting a loaded
    figure as if it were the ceiling."""
    _record(store, contention="loaded", value=32.985)

    module = _exporter()
    models = [{"id": "kokoro", "variants": [{"id": "kokoro-82m"}]}]
    module.attach_measurements(models)
    summary = models[0]["variants"][0]["measurements"][0]

    assert summary["solo_median"] is None
    assert summary["solo_samples"] == 0
    assert summary["observed_median"] == 32.985


def test_an_empty_store_changes_nothing(store):
    module = _exporter()
    models = [{"id": "kokoro", "variants": [{"id": "kokoro-82m"}]}]
    assert module.attach_measurements(models) == 0
    assert "measurements" not in models[0]["variants"][0]
