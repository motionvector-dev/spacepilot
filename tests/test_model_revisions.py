"""A model reference has to name weights, not a branch.

The registry's whole thesis is that a number carries its provenance: a bare
figure with no `source` is rejected because nobody can tell an estimate from a
measurement. An unpinned `repo:` is the same failure one level down. The repo
id resolves to whatever the author last pushed, so a record saying
"flux2-klein-4b-4bit took 23.4s" can describe weights that no longer exist
while still reading as a measurement.

These guard the three links in that chain: the registry can pin, the download
uses the pin, and the measurement writes down which pin it ran against.
"""

import pytest

from spacepilot.pluto.registry import (
    RegistryError, load_registry, parse_model, registry,
)


def _model(**variant_overrides):
    """A minimal valid model, so each test varies exactly one thing."""
    variant = {
        "id": "x-1", "name": "X 1", "repo": "a/b", "backends": ["cpu"],
        "download": {"value": 1, "source": "huggingface-api", "checked": "2026-08-23"},
        "working_set": {"value": 1, "source": "estimated", "note": "n"},
    }
    variant.update(variant_overrides)
    return {
        "schema": 1, "id": "x", "name": "X", "family": "f", "kind": "video",
        "license": {"id": "mit", "open_source": True},
        "variants": [variant],
    }


# ------------------------------------------------------- the schema can pin

def test_a_variant_can_pin_the_commit_it_describes():
    sha = "e7b7dc27f91deacad38e78976d1f2b499d76a294"
    m = parse_model(_model(revision=sha), "x.yaml")
    assert m.variants[0].revision == sha
    assert m.variants[0].is_pinned


def test_an_unpinned_variant_says_so_rather_than_reading_as_pinned():
    """Optional is fine. Silently optional is not — the whole point of the
    field is that a reader can tell the two apart without checking the Hub."""
    v = parse_model(_model(), "x.yaml").variants[0]
    assert v.revision is None
    assert v.is_pinned is False
    assert v.to_dict()["is_pinned"] is False
    assert v.to_dict()["revision"] is None


@pytest.mark.parametrize("ref", ["main", "MAIN", "master", "HEAD", "latest",
                                 "refs/heads/release"])
def test_a_moving_ref_is_rejected_because_it_only_looks_like_a_pin(ref):
    """`revision: main` is worse than no revision at all: the file reads as
    pinned, `is_pinned` says true, and the weights still move on the next push."""
    with pytest.raises(RegistryError, match="moving ref"):
        parse_model(_model(revision=ref), "x.yaml")


def test_an_empty_revision_is_rejected_rather_than_treated_as_absent():
    with pytest.raises(RegistryError, match="omit the field entirely"):
        parse_model(_model(revision="   "), "x.yaml")


def test_a_forty_character_non_sha_is_rejected():
    with pytest.raises(RegistryError, match="not a hex SHA"):
        parse_model(_model(revision="z" * 40), "x.yaml")


def test_registry_can_name_every_unpinned_variant():
    reg = load_registry()
    named = {v.id for v in reg.unpinned()}
    assert named == {v.id for v in reg.variants if not v.is_pinned}


def test_every_shipped_variant_is_pinned():
    """The registry as it actually stands. If a variant is added unpinned this
    fails, which is the point — an unpinned row must be a decision somebody
    made on purpose, not something that slipped in unnoticed."""
    unpinned = load_registry().unpinned()
    assert not unpinned, (
        "unpinned variants: " + ", ".join(f"{v.id} ({v.repo})" for v in unpinned))


# ------------------------------------------------- the download uses the pin

def test_the_recipe_carries_the_registry_revision():
    from spacepilot.pluto.services.model_catalog import catalog_manager
    for v in registry().variants:
        assert catalog_manager.recipes[v.id].revision == v.revision


def test_snapshot_download_is_given_the_revision(monkeypatch, tmp_path):
    """The B615 finding, but the reason is reproducibility rather than the
    lint id: a download with no revision cannot be repeated."""
    from spacepilot.pluto.services import model_catalog as mc

    seen = {}
    sha = "a" * 40

    def fake_snapshot_download(**kwargs):
        seen.update(kwargs)
        snapshot = tmp_path / "models--a--b" / "snapshots" / sha
        snapshot.mkdir(parents=True, exist_ok=True)
        (snapshot / "weights.safetensors").write_bytes(b"weights")
        return str(snapshot)

    import huggingface_hub
    monkeypatch.setattr(huggingface_hub, "snapshot_download",
                        fake_snapshot_download, raising=False)

    mgr = mc.ModelCatalogManager()
    mgr.MODELS_DIR = tmp_path
    job_id = "j"
    mgr.jobs[job_id] = mc.DownloadJob(
        job_id=job_id, recipe_id="r", status="pending",
        progress_percent=0.0, speed_mb_s=0.0, requested_revision=sha,
    )
    mgr._run_download(job_id, "a/b", ["*.safetensors"], sha)

    assert seen["revision"] == sha, "snapshot_download was called without a revision"


def test_the_job_records_which_commit_it_actually_got(monkeypatch, tmp_path):
    """When nothing was requested, the resolved SHA is the only record of what
    these bytes are — and it exists only after the download has run."""
    from spacepilot.pluto.services import model_catalog as mc

    sha = "b" * 40

    def fake_snapshot_download(**kwargs):
        snapshot = tmp_path / "models--a--b" / "snapshots" / sha
        snapshot.mkdir(parents=True, exist_ok=True)
        (snapshot / "weights.bin").write_bytes(b"weights")
        return str(snapshot)

    import huggingface_hub
    monkeypatch.setattr(huggingface_hub, "snapshot_download",
                        fake_snapshot_download, raising=False)

    mgr = mc.ModelCatalogManager()
    mgr.MODELS_DIR = tmp_path
    mgr.jobs["j"] = mc.DownloadJob(
        job_id="j", recipe_id="r", status="pending",
        progress_percent=0.0, speed_mb_s=0.0,
    )
    mgr._run_download("j", "a/b", None, None)

    assert mgr.jobs["j"].resolved_revision == sha
    assert mgr.jobs["j"].resolved_files == [
        str(tmp_path / "models--a--b" / "snapshots" / sha / "weights.bin")]


# --------------------------------------- the measurement writes down the pin

def test_a_measurement_records_the_revision_it_ran_against(system, tmp_path):
    """Without this the record names a repo, and a repo is not a thing you can
    fetch twice. `runtime_version` already pins the software side; this is the
    same closure on the model side."""
    from spacepilot.pluto import measurements as ms

    pinned = registry().variants[0]
    path = ms.record(
        system=system, model_id=pinned.id, metric="seconds_per_image",
        value=1.0, contention="solo", root=tmp_path,
    )
    written = ms.parse_measurement(
        __import__("yaml").safe_load(path.read_text()), str(path))
    assert written.model_revision == pinned.revision


def test_an_explicit_revision_is_not_overwritten_by_the_registry(system, tmp_path):
    """A run against weights already on disk knows better than the registry
    does — the registry says what should be fetched, not what was."""
    from spacepilot.pluto import measurements as ms

    other = "c" * 40
    path = ms.record(
        system=system, model_id=registry().variants[0].id,
        metric="seconds_per_image", value=1.0, contention="solo",
        root=tmp_path, model_revision=other,
    )
    assert __import__("yaml").safe_load(path.read_text())["model_revision"] == other


def test_an_unknown_model_records_without_a_revision(system, tmp_path):
    """A missing pin is a fact about the model, never a reason to lose a real
    sample — the run already happened."""
    from spacepilot.pluto import measurements as ms

    path = ms.record(
        system=system, model_id="not-in-the-registry",
        metric="seconds_per_image", value=1.0, contention="solo", root=tmp_path,
    )
    raw = __import__("yaml").safe_load(path.read_text())
    assert "model_revision" not in raw


def test_records_written_before_this_field_existed_still_parse():
    from spacepilot.pluto.measurements import parse_measurement

    old = {
        "schema": 1, "system_id": "s", "model_id": "m",
        "metric": "seconds_per_image", "value": 1.0,
        "contention": "solo", "measured_on": "2026-08-01T00:00:00+00:00",
    }
    assert parse_measurement(old, "old.yaml").model_revision is None


@pytest.fixture
def system():
    from spacepilot.pluto.measurements import system_from_profile

    class _Profile:
        os_name = "macOS"
        os_version = "15.6"
        chip = "Apple M1 Max"
        machine_model = "MacBookPro18,4"
        backend = "metal"
        cpu_cores = 10
        gpu_cores = 32
        memory_total_bytes = 34359738368
        memory_free_bytes = 8 * 1024 ** 3
        memory_limit_bytes = 26800603136
        memory_limit_source = "metal"
        memory_unified = True
        vram_total_bytes = None
        unknown = {}

    return system_from_profile(_Profile())


# ------------------------------------------------------ no site left unpinned

def test_no_hugging_face_download_in_the_package_omits_a_revision():
    """A guard against the next one. Every from_pretrained / snapshot_download
    / hf_hub_download call site takes a revision, or somebody has to come back
    here and say why it does not."""
    import ast
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent / "spacepilot"
    targets = {"from_pretrained", "snapshot_download", "hf_hub_download"}
    offenders = []

    for path in sorted(root.rglob("*.py")):
        tree = ast.parse(path.read_text(), str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            fn = node.func
            name = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", None)
            if name not in targets:
                continue
            if any(kw.arg == "revision" for kw in node.keywords):
                continue
            if any(kw.arg is None for kw in node.keywords):
                continue  # **kwargs may carry it; the call sites here do not
            offenders.append(f"{path.relative_to(root.parent)}:{node.lineno} {name}()")

    assert not offenders, (
        "unpinned Hugging Face downloads: " + "; ".join(offenders))
