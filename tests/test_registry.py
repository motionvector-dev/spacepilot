"""The registry is the one description of a model. These guard its promises."""

import pytest

from src.pluto.registry import (
    SOURCES, Registry, RegistryError, load_registry, parse_model, registry,
)


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
    from src.pluto.services.model_catalog import catalog_manager
    assert set(catalog_manager.recipes) == {v.id for v in registry().variants}
