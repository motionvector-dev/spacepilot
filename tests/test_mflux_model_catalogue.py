"""The non-FLUX models mflux 0.19.0 can already run.

mflux resolves 34 built-in aliases to specific Hugging Face repos. The FLUX.1
variants belong to a separate, parallel workstream (registry/models/flux.yaml,
src/drivers/mflux_driver.py); this file only guards the other nine families —
Qwen-Image, Z-Image, FIBO, ERNIE-Image, Ideogram 4, SeedVR2, Boogu, Lens, and
FLUX.2 Klein — plus the runtime file that lists what mflux can run.
"""

from pathlib import Path

import pytest

from src.pluto.registry import load_registry, registry
from src.pluto.runtimes import load_runtimes

NEW_FAMILY_FILES = [
    "qwen-image.yaml",
    "z-image.yaml",
    "fibo.yaml",
    "ernie-image.yaml",
    "ideogram.yaml",
    "seedvr2.yaml",
    "boogu.yaml",
    "lens.yaml",
    "flux2-klein.yaml",
]

NEW_VARIANT_IDS = {
    "qwen-image", "qwen-image-edit",
    "z-image", "z-image-turbo", "z-image-turbo-controlnet-union-2.1",
    "fibo", "fibo-lite", "fibo-edit", "fibo-edit-rmbg",
    "ernie-image", "ernie-image-turbo",
    "ideogram-4-fp8",
    "seedvr2-3b", "seedvr2-7b",
    "boogu-image-turbo",
    "lens-turbo",
    "flux2-klein-4b", "flux2-klein-9b", "flux2-klein-9b-kv",
    "flux2-klein-base-4b", "flux2-klein-base-9b",
}


def test_registry_files_exist_one_per_family():
    models_dir = Path(__file__).resolve().parent.parent / "registry" / "models"
    for fname in NEW_FAMILY_FILES:
        assert (models_dir / fname).is_file(), f"missing {fname}"
    # And no FLUX.1 file — that belongs to the other agent's workstream.
    # This file deliberately does NOT assert flux.yaml is absent. That was a
    # coordination rule between two agents working in parallel on the same
    # afternoon, not a property of the registry — and it froze into a test that
    # failed the moment both branches merged. Ownership boundaries belong in the
    # brief, not in an assertion that outlives the reason for it.


def test_full_registry_still_loads_with_the_new_files():
    reg = load_registry()
    assert reg.models, "registry failed to load"
    ids = [v.id for v in reg.variants]
    assert len(ids) == len(set(ids)), "variant ids collided across files"


def test_every_advertised_variant_is_present():
    ids = {v.id for v in registry().variants}
    missing = NEW_VARIANT_IDS - ids
    assert not missing, f"mflux advertises these but the registry is missing them: {missing}"


def test_no_new_variant_claims_a_measured_number():
    """This is a catalogue, not a benchmark. Nobody ran generation for this task."""
    for v in registry().variants:
        if v.id not in NEW_VARIANT_IDS:
            continue
        assert v.download.source != "measured", f"{v.id}: download must not claim measured"
        assert v.working_set.source != "measured", f"{v.id}: working_set must not claim measured"
        # working_set for a catalogue entry should be an estimate, with its
        # derivation on record — never asserted as fact.
        assert v.working_set.source == "estimated", (
            f"{v.id}: working_set should be estimated, not {v.working_set.source}"
        )
        assert v.working_set.note, f"{v.id}: working_set estimate has no derivation note"


def test_every_new_variant_carries_a_licence_with_open_source_set():
    for v in registry().variants:
        if v.id not in NEW_VARIANT_IDS:
            continue
        assert v.license.id, f"{v.id}: no license id"
        assert isinstance(v.license.open_source, bool), f"{v.id}: open_source not set"
        if not v.license.open_source:
            assert v.license.restrictions, f"{v.id}: restrictive licence with no restrictions listed"


@pytest.mark.parametrize("variant_id", ["fibo", "fibo-lite", "fibo-edit", "fibo-edit-rmbg", "ideogram-4-fp8"])
def test_known_non_commercial_models_are_marked_non_commercial(variant_id):
    """These four are gated and non-commercial on the Hub — getting this wrong is
    worse than leaving the model out, so pin it down explicitly."""
    v = registry().variant(variant_id)
    assert v is not None, variant_id
    assert v.license.open_source is False, f"{variant_id}: should be marked non-commercial"


@pytest.mark.parametrize("variant_id", ["flux2-klein-9b", "flux2-klein-9b-kv", "flux2-klein-base-9b"])
def test_flux2_klein_9b_checkpoints_are_non_commercial(variant_id):
    v = registry().variant(variant_id)
    assert v is not None, variant_id
    assert v.license.open_source is False


@pytest.mark.parametrize("variant_id", ["flux2-klein-4b", "flux2-klein-base-4b"])
def test_flux2_klein_4b_checkpoints_are_apache(variant_id):
    v = registry().variant(variant_id)
    assert v is not None, variant_id
    assert v.license.open_source is True
    assert v.license.id == "apache-2.0"


def test_seedvr2_is_not_classified_as_text_to_image():
    """SeedVR2 is a restoration/upscaling model; defaulting it to 'image' text-to-image
    kind would be wrong even though it lives in the image registry directory."""
    v = registry().variant("seedvr2-3b")
    assert v is not None
    assert v.kind == "video"


def test_shared_seedvr2_repo_narrows_by_file():
    """seedvr2-3b and seedvr2-7b share numz/SeedVR2_comfyUI — each must name its
    own files or a download would fetch every precision of both sizes."""
    for vid in ("seedvr2-3b", "seedvr2-7b"):
        v = registry().variant(vid)
        assert v.files, f"{vid}: shares a repo but names no files"


def test_mflux_runtime_lists_every_new_family():
    runtimes = load_runtimes()
    mflux = runtimes["mflux"]
    for family in ("flux", "qwen-image", "z-image", "fibo", "ernie-image",
                   "ideogram", "seedvr2", "boogu", "lens", "flux2-klein"):
        assert family in mflux.runs, f"mflux runtime should list '{family}'"


def test_mflux_runtime_serves_video_now_that_it_runs_seedvr2():
    runtimes = load_runtimes()
    assert "video" in runtimes["mflux"].serves
    assert "image" in runtimes["mflux"].serves


def test_catalog_manager_picks_up_the_new_variants_without_a_second_copy():
    from src.pluto.services.model_catalog import catalog_manager
    ids = {v.id for v in registry().variants}
    assert set(catalog_manager.recipes) == ids
    for variant_id in NEW_VARIANT_IDS:
        assert variant_id in catalog_manager.recipes
