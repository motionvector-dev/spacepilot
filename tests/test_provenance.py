"""The CLI's provenance vocabulary must not turn estimates into measurements."""

from spacepilot.pluto.measurements import Measurement, summarise
from spacepilot.pluto.registry import Fact
from spacepilot.pluto.services.provenance import (
    fact_provenance,
    format_fact,
    format_local_speed,
    local_speeds,
    primary_speed,
)


def _measurement(**changes):
    data = {
        "schema": 1,
        "system_id": "this-box",
        "model_id": "legacy-family-id",
        "variant_id": "demo-variant",
        "metric": "seconds_per_image",
        "value": 10.0,
        "contention": "solo",
        "measured_on": "2026-08-24T10:00:00+00:00",
    }
    data.update(changes)
    return Measurement(**data)


def test_fact_sources_map_to_the_product_vocabulary_without_leaking_estimates():
    measured = fact_provenance(Fact(1.0, "measured", "2026-08-24"))
    hub = fact_provenance(Fact(2.0, "huggingface-api", "2026-08-23"))
    declared = fact_provenance(Fact(3.0, "declared", "2026-08-22"))
    estimate = fact_provenance(Fact(99.0, "estimated", note="derived"))

    assert (measured.state, measured.value) == ("flown", 1.0)
    assert (hub.state, hub.value) == ("on paper", 2.0)
    assert (declared.state, declared.value) == ("on paper", 3.0)
    assert (estimate.state, estimate.value) == ("unflown", None)
    assert "99" not in format_fact(Fact(99.0, "estimated", note="derived"), "99 GB")


def test_local_join_prefers_solo_and_keeps_the_latest_date_for_that_stream():
    rows = [
        _measurement(value=10.0, measured_on="2026-08-22T10:00:00+00:00"),
        _measurement(value=14.0, measured_on="2026-08-24T10:00:00+00:00"),
        _measurement(value=30.0, contention="loaded", measured_on="2026-08-25T10:00:00+00:00"),
    ]
    speed = primary_speed(local_speeds(rows, system_id="this-box", variant_id="demo-variant"))

    assert speed is not None
    assert speed.value == 12.0
    assert speed.stream == "solo"
    assert speed.latest_on == "2026-08-24T10:00:00+00:00"
    assert "flown 12.0 s/image · solo" in format_local_speed(speed)


def test_loaded_only_measurement_is_flown_observed_not_a_solo_ceiling():
    speed = primary_speed(local_speeds(
        [_measurement(value=30.0, contention="loaded")],
        system_id="this-box", variant_id="demo-variant",
    ))
    assert speed is not None
    assert speed.stream == "observed"
    assert "flown 30.0 s/image · observed" in format_local_speed(speed)


def test_other_system_and_failed_records_do_not_create_a_local_speed():
    rows = [
        _measurement(system_id="other-box"),
        _measurement(status="failed", value=1.0),
    ]
    assert local_speeds(rows, system_id="this-box", variant_id="demo-variant") == []


def test_variant_id_is_the_canonical_measurement_subject_for_every_summary():
    row = _measurement(model_id="old-family-id", variant_id="demo-variant")
    summary = summarise([row], "this-box", "demo-variant", "seconds_per_image")
    assert summary.solo_median == 10.0
