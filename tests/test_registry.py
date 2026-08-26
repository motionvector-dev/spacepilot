"""The registry is the one description of a model. These guard its promises."""

import pytest

from spacepilot.pluto.registry import (
    METRIC_DIRECTION, SOURCES, SPEED_METRICS, Registry, RegistryError,
    load_registry, metric_direction, parse_model, registry, value_from_wall,
)


# Written out longhand rather than read from METRIC_DIRECTION, so that adding a
# metric fails here until somebody says which way it points. `pluto measure`
# recorded 0.158 for a realtime_factor of 6.3 for as long as one division
# served every metric.
EXPECTED_DIRECTION = {
    "tokens_per_second": "rate",
    "seconds_per_image": "cost",
    "seconds_per_second_of_video": "cost",
    "realtime_factor": "rate",
    "load_seconds": "cost",
}


def test_every_speed_metric_declares_a_direction():
    assert set(METRIC_DIRECTION) == SPEED_METRICS
    assert METRIC_DIRECTION == EXPECTED_DIRECTION


@pytest.mark.parametrize("metric,direction", sorted(EXPECTED_DIRECTION.items()))
def test_direction_decides_which_way_wall_time_divides(metric, direction):
    value = value_from_wall(metric, wall_seconds=4.0, units=8.0)
    assert value == (2.0 if direction == "rate" else 0.5)
    assert metric_direction(metric) == direction


def test_realtime_factor_is_units_over_wall():
    """The registry's own kokoro entry is the fixed point: 12.5s of speech in
    2.7s of wall clock is 4.6, not 0.22."""
    assert value_from_wall("realtime_factor", 2.7, 12.5) == pytest.approx(4.63, abs=0.01)
    assert value_from_wall("seconds_per_second_of_video", 2.7, 12.5) == pytest.approx(0.216, abs=0.001)


def test_a_rate_cannot_be_computed_from_wall_time_alone():
    with pytest.raises(RegistryError, match="rate"):
        value_from_wall("realtime_factor", 30.0)
    assert value_from_wall("seconds_per_image", 30.0) == 30.0


def test_unknown_metric_and_impossible_units_are_refused():
    with pytest.raises(RegistryError, match="not one of"):
        value_from_wall("rt_factor", 1.0, 1.0)
    with pytest.raises(RegistryError, match="units must be positive"):
        value_from_wall("realtime_factor", 1.0, 0.0)
    with pytest.raises(RegistryError, match="wall_seconds must be positive"):
        value_from_wall("seconds_per_image", 0.0, 1.0)


def test_registry_loads_and_ids_are_unique():
    reg = load_registry()
    assert reg.models, "registry is empty"
    ids = [v.id for v in reg.variants]
    assert len(ids) == len(set(ids)), "variant ids must be unique across all files"


def test_every_number_declares_where_it_came_from():
    """An estimate must never be readable as a measurement."""
    for v in registry().variants:
        assert v.download.source in SOURCES
        assert v.working_set.source in SOURCES
        # Anything claiming to have been checked has to say when.
        for fact in (v.download, v.working_set):
            if fact.source in ("measured", "huggingface-api"):
                assert fact.checked, f"{v.id}: {fact.source} with no checked date"
            if fact.source == "estimated":
                assert fact.note, f"{v.id}: estimate with no derivation note"


def test_restricted_licences_spell_out_their_restrictions():
    """A licence people can trip over has to say how, not just name itself."""
    for m in registry().models.values():
        if not m.license.open_source:
            assert m.license.restrictions, f"{m.id}: non-open licence with no restrictions listed"
            assert not m.license.is_permissive


def test_multi_checkpoint_repos_narrow_their_download():
    """LTX-Video holds every checkpoint it ever shipped — 236 GB whole.

    A variant sharing a repo with another variant must name its files, or a
    download fetches the entire history instead of the one wanted checkpoint.
    """
    seen = {}
    for v in registry().variants:
        seen.setdefault(v.repo, []).append(v)
    for repo, variants in seen.items():
        if len(variants) > 1:
            for v in variants:
                assert v.files, f"{v.id}: shares {repo} with another variant but names no files"


def test_a_bare_number_is_rejected():
    """The whole point of the schema: a number with no source cannot be stored."""
    bad = {
        "schema": 1, "id": "x", "name": "X", "family": "f", "kind": "video",
        "license": {"id": "mit", "open_source": True},
        "variants": [{
            "id": "x-1", "name": "X 1", "repo": "a/b", "backends": ["cpu"],
            "download": 123,                       # <- bare number
            "working_set": {"value": 1, "source": "estimated", "note": "n"},
        }],
    }
    with pytest.raises(RegistryError, match="cannot be told apart from a guess"):
        parse_model(bad, "bad.yaml")


def test_an_estimate_without_its_derivation_is_rejected():
    bad = {
        "schema": 1, "id": "x", "name": "X", "family": "f", "kind": "video",
        "license": {"id": "mit", "open_source": True},
        "variants": [{
            "id": "x-1", "name": "X 1", "repo": "a/b", "backends": ["cpu"],
            "download": {"value": 1, "source": "huggingface-api", "checked": "2026-08-22"},
            "working_set": {"value": 1, "source": "estimated"},   # <- no note
        }],
    }
    with pytest.raises(RegistryError, match="how it was derived"):
        parse_model(bad, "bad.yaml")


def test_unknown_backend_is_rejected():
    bad = {
        "schema": 1, "id": "x", "name": "X", "family": "f", "kind": "video",
        "license": {"id": "mit", "open_source": True},
        "variants": [{
            "id": "x-1", "name": "X 1", "repo": "a/b", "backends": ["vulkan"],
            "download": {"value": 1, "source": "huggingface-api", "checked": "2026-08-22"},
            "working_set": {"value": 1, "source": "estimated", "note": "n"},
        }],
    }
    with pytest.raises(RegistryError, match="unknown backends"):
        parse_model(bad, "bad.yaml")


def test_catalog_is_a_view_over_the_registry():
    """No second copy of the model list anywhere in the codebase."""
    from spacepilot.pluto.services.model_catalog import catalog_manager
    assert set(catalog_manager.recipes) == {v.id for v in registry().variants}


def test_exported_json_matches_the_registry(tmp_path):
    """web/registry.json is what the public page reads.

    It is generated, so it can fall behind the YAML it came from — and the page
    has no server to correct it. This fails when someone edits a model and
    forgets to re-run tools/export_registry.py.
    """
    import json
    import subprocess
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    shipped = root / "web" / "registry.json"
    assert shipped.is_file(), "run: python tools/export_registry.py"

    fresh = tmp_path / "registry.json"
    subprocess.run(
        [sys.executable, str(root / "tools" / "export_registry.py"), "--out", str(fresh)],
        cwd=root, check=True, capture_output=True,
    )

    a = json.loads(shipped.read_text())
    b = json.loads(fresh.read_text())
    a.pop("generated", None)          # the date moves on its own; the data must not
    b.pop("generated", None)
    assert a == b, "web/registry.json is stale — re-run tools/export_registry.py"
