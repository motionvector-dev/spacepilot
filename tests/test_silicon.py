"""The silicon registry refuses what it cannot weigh.

Every test here has been watched fail. The point of this registry is not that it
holds numbers — a markdown table holds numbers. The point is that a number
without a source, or a claim without a date, does not load at all.
"""

import pytest
import yaml

from spacepilot.paths import shipped_dir
from spacepilot.pluto.silicon import (
    AVAILABILITY,
    COMPUTE_PATHS,
    KINDS,
    MEMORY_MODELS,
    SOURCES,
    SiliconError,
    load_silicon,
    parse_part,
)


def _a_part(**overrides):
    """A minimal valid part. Tests override one field to break one rule."""
    raw = {
        "schema": 1,
        "id": "test-part",
        "name": "Test Part",
        "vendor": "Nobody",
        "kind": "box",
        "availability": "shipping",
        "summary": "A part that exists only in this test.",
        "compute_paths": ["cpu"],
        "memory_model": "unified",
        "memory_bytes": {
            "value": 1000,
            "source": "declared",
            "checked": "2026-08-25",
            "url": "https://example.com/specs",
        },
    }
    raw.update(overrides)
    return raw


# ── the shipped registry loads ───────────────────────────────────────────────

def test_the_shipped_registry_loads_and_is_not_empty():
    parts = load_silicon(shipped_dir("silicon"))
    # An extractor that can return nothing must prove it returned something,
    # or every assertion below passes against an empty directory.
    assert len(parts) >= 4, f"only {len(parts)} parts loaded; the registry looks empty"


def test_every_shipped_claim_carries_a_date_and_a_link():
    for part in load_silicon(shipped_dir("silicon")).values():
        for field in ("memory_bytes", "bandwidth_bytes_per_sec",
                      "npu_tops", "power_watts", "price_usd"):
            claim = getattr(part, field)
            if claim is None:
                continue
            assert claim.checked, f"{part.id}.{field} has no checked date"
            assert claim.url.startswith("https://"), f"{part.id}.{field} has no source link"


def test_prototypes_are_not_reported_as_buyable():
    """`is_buyable` gates anything a scheduler might try to route to."""
    parts = load_silicon(shipped_dir("silicon"))
    prototypes = [p for p in parts.values() if p.availability == "prototype"]
    assert prototypes, "expected at least one prototype; the test proves nothing without one"
    for part in prototypes:
        assert not part.is_buyable, f"{part.id} is a prototype and must not read as buyable"


# ── the refusals ─────────────────────────────────────────────────────────────

def test_a_bare_number_will_not_load():
    """The rule the whole registry exists for."""
    with pytest.raises(SiliconError, match="bare int"):
        parse_part(_a_part(memory_bytes=137438953472), "test.yaml")


def test_a_claim_without_a_date_will_not_load():
    bad = {"value": 1000, "source": "declared", "url": "https://example.com"}
    with pytest.raises(SiliconError, match="checked"):
        parse_part(_a_part(memory_bytes=bad), "test.yaml")


def test_a_claim_without_a_source_link_will_not_load():
    bad = {"value": 1000, "source": "declared", "checked": "2026-08-25"}
    with pytest.raises(SiliconError, match="url"):
        parse_part(_a_part(memory_bytes=bad), "test.yaml")


def test_a_non_https_source_will_not_load():
    bad = {"value": 1000, "source": "declared", "checked": "2026-08-25",
           "url": "http://example.com"}
    with pytest.raises(SiliconError, match="https"):
        parse_part(_a_part(memory_bytes=bad), "test.yaml")


def test_a_loose_date_will_not_load():
    """'August 2026' is not a date you can compare two claims with."""
    bad = {"value": 1000, "source": "declared", "checked": "August 2026",
           "url": "https://example.com"}
    with pytest.raises(SiliconError, match="ISO date"):
        parse_part(_a_part(memory_bytes=bad), "test.yaml")


def test_measured_is_not_an_accepted_source():
    """A measurement belongs in the corpus with the machine that produced it."""
    assert "measured" not in SOURCES
    bad = {"value": 1000, "source": "measured", "checked": "2026-08-25",
           "url": "https://example.com"}
    with pytest.raises(SiliconError, match="unknown source"):
        parse_part(_a_part(memory_bytes=bad), "test.yaml")


def test_an_unknown_compute_path_will_not_load():
    with pytest.raises(SiliconError, match="unknown compute paths"):
        parse_part(_a_part(compute_paths=["cuda", "telepathy"]), "test.yaml")


def test_an_unknown_memory_model_will_not_load():
    with pytest.raises(SiliconError, match="unknown memory_model"):
        parse_part(_a_part(memory_model="lots"), "test.yaml")


def test_an_unknown_availability_will_not_load():
    with pytest.raises(SiliconError, match="unknown availability"):
        parse_part(_a_part(availability="soon"), "test.yaml")


def test_an_empty_directory_raises_rather_than_returning_nothing(tmp_path):
    """A registry that loads to zero entries has failed, not succeeded."""
    with pytest.raises(SiliconError, match="cannot be empty"):
        load_silicon(tmp_path)


def test_a_duplicate_id_will_not_load(tmp_path):
    for name in ("a.yaml", "b.yaml"):
        (tmp_path / name).write_text(yaml.safe_dump(_a_part()))
    with pytest.raises(SiliconError, match="duplicate part id"):
        load_silicon(tmp_path)


def test_broken_yaml_names_the_file(tmp_path):
    (tmp_path / "broken.yaml").write_text("kind: [unclosed\n")
    with pytest.raises(SiliconError, match="broken.yaml"):
        load_silicon(tmp_path)


# ── the vocabularies stay closed ─────────────────────────────────────────────

def test_compute_paths_cover_what_the_probe_cannot_yet_name():
    """This registry exists partly to name paths the device probe misses.

    Vulkan and NPU are the two that matter most today: a machine can run models
    through either, and a probe that only knows CUDA, Metal and ROCm reports such
    a machine as having no usable accelerator at all.
    """
    for path in ("vulkan", "npu", "webnn", "sycl", "openvino"):
        assert path in COMPUTE_PATHS


def test_kinds_and_availability_are_small_and_closed():
    assert KINDS == {"accelerator", "box", "memory", "client-soc"}
    assert AVAILABILITY == {"shipping", "sampling", "announced", "prototype", "roadmap"}
    assert MEMORY_MODELS >= {"unified", "partitionable", "discrete"}
