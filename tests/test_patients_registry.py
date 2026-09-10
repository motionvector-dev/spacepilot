"""On-paper registration for this week's on-device 'patient' models.

Edge0 (35B-A3B and 8B-A1B previews), the Qwen3.5-35B-A3B base Edge0 builds on,
and the 12 stable Desert Ant Labs specialist models. Every variant is pinned
to a real, resolvable commit SHA from the Hugging Face Hub API -- none of
these have been downloaded or run. "Unflown" here means what it means
everywhere else in this registry: no `speed` entries, and no `working_set`
fact with source "measured" -- see spacepilot/model_registry.py's SOURCES and
Fact.is_measured. No new schema field was needed for that.
"""

import pytest

from spacepilot.model_registry import MOVING_REFS, load_registry


EDGE0_IDS = {"edge0-35b-a3b-preview", "edge0-8b-a1b-preview"}
QWEN_BASE_ID = "qwen3-5-35b-a3b-base"
DESERT_ANT_IDS = {
    "desert-ant-voz", "desert-ant-align", "desert-ant-clear", "desert-ant-ear",
    "desert-ant-tongue", "desert-ant-redact", "desert-ant-clips",
    "desert-ant-emo", "desert-ant-gist", "desert-ant-shapes",
    "desert-ant-title", "desert-ant-uhm",
}
ALL_NEW_IDS = EDGE0_IDS | {QWEN_BASE_ID} | DESERT_ANT_IDS


def test_all_patients_are_registered():
    reg = load_registry()
    missing = ALL_NEW_IDS - set(reg.models)
    assert not missing, f"expected patient models missing from the registry: {missing}"


def test_every_patient_variant_is_pinned():
    """A patient registered 'on paper' still needs a real SHA -- an unpinned
    entry would describe weights that can silently move under it."""
    reg = load_registry()
    for v in reg.variants:
        if v.model_id in ALL_NEW_IDS:
            assert v.is_pinned, f"{v.id}: unpinned -- needs a revision SHA"
            assert v.revision.lower() not in MOVING_REFS, (
                f"{v.id}: revision looks like a moving ref, not a pin"
            )
            assert len(v.revision) == 40, f"{v.id}: revision is not a full 40-char SHA"


def test_every_patient_is_unflown():
    """These are on-paper registrations: no speed entries, no measured
    working_set. Registering a claimed number as 'measured' would be the
    exact failure this schema's provenance fields exist to prevent."""
    reg = load_registry()
    for v in reg.variants:
        if v.model_id in ALL_NEW_IDS:
            assert v.speed == [], f"{v.id}: has a speed entry but was never flown"
            assert v.working_set.source != "measured", (
                f"{v.id}: working_set claims 'measured' but nothing has run"
            )
            assert v.download.source != "measured", (
                f"{v.id}: download claims 'measured' but nothing has run"
            )


def test_desert_ant_licence_is_marked_non_open_and_restricted():
    """Desert Ant Labs ships a source-available licence, not OSI open source --
    the registry must say so and must spell out the restriction, matching the
    existing rule in test_registry.py for every non-open licence."""
    reg = load_registry()
    for mid in DESERT_ANT_IDS:
        model = reg.models[mid]
        assert model.license.open_source is False
        assert model.license.restrictions, f"{mid}: non-open licence with no restrictions listed"
        assert not model.license.is_permissive


def test_edge0_variants_share_the_ssd_streaming_notes():
    reg = load_registry()
    for mid in EDGE0_IDS:
        variant = reg.variant(f"{mid}-4bit")
        assert variant is not None, f"variant for {mid} not found"
        assert "SSD" in variant.notes
        assert "Recover-LoRA" in variant.notes
        assert "agentic tasks" in variant.notes  # the verbatim limitations note


def test_edge0_8b_base_is_not_qwen():
    """The 8B-A1B preview's base is Ling-3.0-tiny, not Qwen3.5-MoE -- the 8B
    model's own card corrects the assumption this task was framed under."""
    reg = load_registry()
    variant = reg.variant("edge0-8b-a1b-preview-4bit")
    assert "Ling-3.0-tiny" in variant.notes
    assert "not Qwen3.5-MoE" in variant.notes


def test_qwen_base_is_distinct_from_existing_qwen_entries():
    reg = load_registry()
    existing = {"qwen1-5-moe", "qwen3-6-27b"}
    assert QWEN_BASE_ID not in existing
    assert QWEN_BASE_ID in reg.models


def test_catalog_is_a_view_over_the_registry_including_patients():
    """No second copy of the model list -- every patient variant must surface
    through spacepilot.services.model_catalog without any extra wiring."""
    from spacepilot.services.model_catalog import catalog_manager
    from spacepilot.model_registry import registry

    all_variant_ids = {v.id for v in registry().variants}
    assert all_variant_ids <= set(catalog_manager.recipes)
    for mid in ALL_NEW_IDS:
        matching = [rid for rid in catalog_manager.recipes if rid.startswith(mid)]
        assert matching, f"{mid}: no recipe surfaced through the catalog"


def test_exported_json_includes_patients(tmp_path):
    """web/registry.json must be regenerated, not just the YAML."""
    import json
    import subprocess
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    shipped = root / "web" / "registry.json"
    data = json.loads(shipped.read_text())
    ids = {m["id"] for m in data["models"]}
    missing = ALL_NEW_IDS - ids
    assert not missing, (
        f"web/registry.json is missing {missing} -- run: python tools/export_registry.py"
    )
