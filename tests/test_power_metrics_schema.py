"""Energy-per-unit speed metrics and the power provenance fields on `Speed`.

Added 2026-09-10 alongside tools/fly.py's power sampler: joules per generated
token for executors, joules per second of audio for STT/audio roles, and
joules per classified item for text/classify roles. A `Speed` entry can now
also carry which power source produced the wattage behind that number
(`power_source`), the instantaneous reading itself (`power_watts`), and that
source's own limitations in plain text (`power_limits`) -- all optional, so
every speed entry written before this change still parses unchanged.
"""

import pytest

from spacepilot.model_registry import (
    RegistryError, SPEED_METRICS, parse_model,
)


BASE_MODEL = {
    "schema": 1,
    "id": "power-metrics-test-model",
    "name": "Power Metrics Test Model",
    "family": "test",
    "kind": "text",
    "license": {"id": "mit", "spdx": "MIT", "open_source": True},
    "variants": [
        {
            "id": "power-metrics-test-model-v1",
            "name": "v1",
            "repo": "test/power-metrics-test-model",
            "backends": ["cpu"],
            "download": {"value": 1024, "source": "declared"},
            "working_set": {"value": 2048, "source": "declared"},
        }
    ],
}


def _model(speed_entries):
    import copy
    raw = copy.deepcopy(BASE_MODEL)
    raw["variants"][0]["speed"] = speed_entries
    return parse_model(raw, "power-metrics-test-model.yaml")


def test_the_three_energy_metrics_are_registered():
    assert "joules_per_token" in SPEED_METRICS
    assert "joules_per_second_of_audio" in SPEED_METRICS
    assert "joules_per_item" in SPEED_METRICS


def test_a_joules_per_token_entry_parses_with_power_provenance():
    model = _model([{
        "device": "this Mac", "backend": "cpu", "metric": "joules_per_token",
        "value": 0.031, "source": "measured", "measured_on": "2026-09-10",
        "power_source": "ioreg-battery", "power_watts": 18.1,
        "power_limits": "instantaneous battery discharge only",
        "note": "bracketed sample",
    }])
    v = model.variants[0]
    assert v.speed[0].metric == "joules_per_token"
    assert v.speed[0].power_source == "ioreg-battery"
    assert v.speed[0].power_watts == pytest.approx(18.1)
    assert "instantaneous" in v.speed[0].power_limits


def test_power_fields_are_optional_and_default_to_none():
    """Every speed entry written before this change has none of these keys
    and must still parse, with the new fields simply absent."""
    model = _model([{
        "device": "M1 Max", "backend": "metal", "metric": "tokens_per_second",
        "value": 12.0, "source": "measured", "measured_on": "2026-08-01",
    }])
    s = model.variants[0].speed[0]
    assert s.power_source is None
    assert s.power_watts is None
    assert s.power_limits is None


def test_joules_per_second_of_audio_and_joules_per_item_also_parse():
    model = _model([
        {"device": "d", "backend": "cpu", "metric": "joules_per_second_of_audio",
         "value": 0.9, "source": "measured", "measured_on": "2026-09-10"},
        {"device": "d", "backend": "cpu", "metric": "joules_per_item",
         "value": 0.004, "source": "measured", "measured_on": "2026-09-10"},
    ])
    metrics = {s.metric for s in model.variants[0].speed}
    assert metrics == {"joules_per_second_of_audio", "joules_per_item"}


def test_unknown_speed_metric_is_still_rejected():
    with pytest.raises(RegistryError):
        _model([{
            "device": "d", "backend": "cpu", "metric": "joules_per_giraffe",
            "value": 1.0, "source": "declared",
        }])
