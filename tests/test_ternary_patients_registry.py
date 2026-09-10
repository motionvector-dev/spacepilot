"""On-paper registration for the ternary/1.58-bit patients added 2026-09-10.

Microsoft's BitNet b1.58 2B4T (packed safetensors + official GGUF) and Prism
ML's Ternary Bonsai 8B (unpacked safetensors + GGUF Q2_0), both pinned to a
real, resolvable commit SHA from the Hugging Face Hub API. Neither has been
downloaded or run -- "unflown" means what it means everywhere else in this
registry: no `speed` entries with source "measured", and no `working_set`
fact with source "measured". See spacepilot/model_registry.py's SOURCES and
Fact.is_measured. No new schema field was needed for that meaning; the new
`joules_per_token` / `joules_per_second_of_audio` / `joules_per_item` speed
metrics (tools/fly.py's power sampler) are tested separately in test_fly.py.
"""

from spacepilot.model_registry import MOVING_REFS, load_registry

BITNET_ID = "bitnet-b1-58-2b4t"
BONSAI_ID = "ternary-bonsai-8b"
TERNARY_IDS = {BITNET_ID, BONSAI_ID}


def test_both_ternary_patients_are_registered():
    reg = load_registry()
    missing = TERNARY_IDS - set(reg.models)
    assert not missing, f"expected ternary patient models missing from the registry: {missing}"


def test_every_ternary_variant_is_pinned_to_a_real_sha():
    reg = load_registry()
    for v in reg.variants:
        if v.model_id in TERNARY_IDS:
            assert v.is_pinned, f"{v.id}: unpinned -- needs a revision SHA"
            assert v.revision.lower() not in MOVING_REFS, (
                f"{v.id}: revision looks like a moving ref, not a pin"
            )
            assert len(v.revision) == 40, f"{v.id}: revision is not a full 40-char SHA"


def test_every_ternary_variant_is_unflown():
    reg = load_registry()
    for v in reg.variants:
        if v.model_id in TERNARY_IDS:
            assert v.speed == [] or all(s.source != "measured" for s in v.speed), (
                f"{v.id}: carries a measured speed entry but nothing has run"
            )
            assert v.working_set.source != "measured", (
                f"{v.id}: working_set claims 'measured' but nothing has run"
            )
            assert v.download.source != "measured", (
                f"{v.id}: download claims 'measured' but nothing has run"
            )


def test_bitnet_is_mit_and_bonsai_is_apache():
    reg = load_registry()
    bitnet = reg.model(BITNET_ID)
    bonsai = reg.model(BONSAI_ID)
    assert bitnet.license.id == "mit"
    assert bitnet.license.open_source is True
    assert bonsai.license.id == "apache-2.0"
    assert bonsai.license.open_source is True


def test_bitnet_has_packed_and_gguf_variants():
    reg = load_registry()
    ids = {v.id for v in reg.model(BITNET_ID).variants}
    assert ids == {"bitnet-b1-58-2b4t-packed", "bitnet-b1-58-2b4t-gguf-i2s"}


def test_bonsai_has_unpacked_and_gguf_variants():
    reg = load_registry()
    ids = {v.id for v in reg.model(BONSAI_ID).variants}
    assert ids == {"ternary-bonsai-8b-unpacked", "ternary-bonsai-8b-gguf-q2-0"}


def test_bonsai_gguf_declared_speed_is_marked_declared_not_measured():
    """The 76 tok/s figure is the publisher's own README table, not a run on
    SpacePilot's fleet -- it must carry source: declared, never 'measured',
    so it is never mistaken for a real flight."""
    reg = load_registry()
    v = reg.variant("ternary-bonsai-8b-gguf-q2-0")
    assert v.speed, "expected the publisher's declared throughput entry"
    for s in v.speed:
        assert s.source == "declared"


def test_runtime_recipe_is_registered_not_pending():
    """A later pass (2026-09-10) registered both real runtime recipes --
    spacepilot/registry/runtimes/{bitnet-cpp,llama-cpp-prism}.yaml -- so the
    manifest notes must point at the actual recipe file now, not carry the
    earlier "recipe pending" placeholder from before those existed."""
    reg = load_registry()
    for mid in TERNARY_IDS:
        for v in reg.model(mid).variants:
            assert "recipe pending" not in v.notes, (
                f"{v.id}: still says recipe pending after both recipes were registered"
            )
            assert "registry/runtimes/bitnet-cpp.yaml" in v.notes or                 "registry/runtimes/llama-cpp-prism.yaml" in v.notes, (
                    f"{v.id}: notes should point at the real runtime recipe file"
                )


def test_catalog_is_a_view_over_the_registry_including_ternary_patients():
    """No second copy of the model list -- every ternary variant must surface
    through spacepilot.services.model_catalog without any extra wiring."""
    from spacepilot.services.model_catalog import catalog_manager
    from spacepilot.model_registry import registry

    all_variant_ids = {v.id for v in registry().variants}
    assert all_variant_ids <= set(catalog_manager.recipes)
    for mid in TERNARY_IDS:
        matching = [rid for rid in catalog_manager.recipes if rid.startswith(mid)]
        assert matching, f"{mid}: no recipe surfaced through the catalog"


def test_exported_json_includes_ternary_patients():
    """web/registry.json must be regenerated, not just the YAML."""
    import json
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    shipped = root / "web" / "registry.json"
    data = json.loads(shipped.read_text())
    ids = {m["id"] for m in data["models"]}
    missing = TERNARY_IDS - ids
    assert not missing, (
        f"web/registry.json is missing {missing} -- run: python tools/export_registry.py"
    )
