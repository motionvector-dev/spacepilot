"""registry/models/flux.yaml specifically: license correctness matters more
here than anywhere else in the registry, because FLUX.1-schnell and
FLUX.1-dev are NOT on the same terms — one is apache-2.0, one forbids
commercial use — and mixing them up is worse than leaving a variant out."""

from src.pluto.registry import registry


def _flux_variant(vid: str):
    v = registry().variant(vid)
    assert v is not None, f"{vid} not found in the registry"
    return v


def test_flux_file_holds_flux_1_only():
    """FLUX.2 Klein is its own family in its own file.

    A 4-bit Klein variant lived here briefly, for a scheduling reason rather than
    a modelling one: FLUX.1 was gated on HuggingFace and Klein was the only thing
    measurable. Two variants then shared one repo across two files, and neither
    narrowed its download, which the multi-checkpoint test caught on merge.
    """
    m = registry().model("flux")
    assert m is not None
    assert {v.id for v in m.variants} == {
        "flux-schnell-4bit", "flux-schnell-8bit", "flux-dev-bf16",
    }
    assert not any("klein" in v.id for v in m.variants)


def test_klein_family_owns_its_measured_variant():
    """The measurement is keyed to flux2-klein-4b-4bit, so the move had to keep
    that id intact or the recorded load_seconds would dangle."""
    k = registry().model("flux2-klein")
    assert k is not None
    ids = {v.id for v in k.variants}
    assert "flux2-klein-4b-4bit" in ids
    shared = [v for v in k.variants
              if v.repo == "black-forest-labs/FLUX.2-klein-4B"]
    assert len(shared) >= 2
    assert all(v.files for v in shared), "variants sharing a repo must narrow their download"


def test_schnell_is_apache_licensed_and_open():
    """FLUX.1-schnell's own model card declares apache-2.0 (HfApi card_data,
    verified 2026-08-22) — permissive, no restrictions, safe for commercial use."""
    for vid in ("flux-schnell-4bit", "flux-schnell-8bit"):
        v = _flux_variant(vid)
        assert v.license.id == "apache-2.0"
        assert v.license.open_source is True
        assert v.license.is_permissive is True
        assert v.license.restrictions == []


def test_dev_is_non_commercial_and_says_so():
    """FLUX.1-dev's model card declares license=other,
    license_name=flux-1-dev-non-commercial-license (HfApi card_data, verified
    2026-08-22) — this must NOT come through as open_source or permissive,
    and the restriction has to be spelled out, not just implied by the id."""
    v = _flux_variant("flux-dev-bf16")
    assert v.license.open_source is False
    assert v.license.is_permissive is False
    assert v.license.restrictions, "non-commercial license must list what it restricts"
    assert any("commercial" in r.lower() for r in v.license.restrictions)


def test_schnell_and_dev_are_not_on_the_same_license():
    """The one mistake this task explicitly warns is worse than leaving a
    variant out: treating schnell and dev as if they share license terms."""
    schnell = _flux_variant("flux-schnell-4bit")
    dev = _flux_variant("flux-dev-bf16")
    assert schnell.license.id != dev.license.id
    assert schnell.license.open_source != dev.license.open_source


def test_klein_4b_is_ungated_and_apache_licensed():
    """black-forest-labs/FLUX.2-klein-4B is NOT gated (HfApi model_info.gated
    is False, verified 2026-08-22) and ships its own LICENSE.md, which is the
    literal Apache-2.0 text (fetched and read, verified 2026-08-22) — this is
    the variant this task could actually download and run for real, since
    FLUX.1-schnell/dev sit behind an HF license gate this session had no way
    to accept."""
    v = _flux_variant("flux2-klein-4b-4bit")
    assert v.license.id == "apache-2.0"
    assert v.license.open_source is True


def test_every_flux_variant_names_its_download_files():
    """flux-schnell-4bit and flux-schnell-8bit share one HF repo; without
    `files` a download would fetch the 23.8 GB monolithic safetensors too,
    not just the subtree mflux actually needs."""
    for v in registry().model("flux").variants:
        assert v.files, f"{v.id}: must narrow its download to a file subset"


def test_quantized_variants_report_smaller_working_set_than_bf16():
    """The whole reason the 4-bit and 8-bit variants exist: they have to
    actually fit where bf16 does not."""
    q4 = _flux_variant("flux-schnell-4bit")
    q8 = _flux_variant("flux-schnell-8bit")
    bf16 = _flux_variant("flux-dev-bf16")
    assert q4.working_set.value < q8.working_set.value < bf16.working_set.value


def test_klein_4b_working_set_is_a_real_measurement():
    """This is the one Fact in the whole file with source=measured — everything
    else here is `estimated` from a documented formula. If this regresses to
    `estimated`, the task's "record real measurements" deliverable regressed
    with it."""
    v = _flux_variant("flux2-klein-4b-4bit")
    assert v.working_set.source == "measured"
    assert v.working_set.checked
