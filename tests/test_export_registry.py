"""The public registry must carry what was measured, not only what was cited.

A variant could hold a real timing in `registry/measurements/` and still export
as having no speed data at all, because the exporter read only the curated
`speed:` block in the model YAML. That is how every FLUX.2 Klein variant
published as unmeasured while two runs sat on disk beside it.
"""
import importlib.util
import os
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]


def _exporter():
    spec = importlib.util.spec_from_file_location(
        "export_registry", ROOT / "tools" / "export_registry.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["export_registry"] = module
    spec.loader.exec_module(module)
    return module


def _record(tmp_path, **fields):
    base = {
        "schema": 1,
        "system_id": "test-box",
        "model_id": "kokoro-82m",
        "variant_id": "kokoro-82m",
        "metric": "seconds_per_image",
        "value": 10.0,
        "contention": "solo",
        "measured_on": "2026-08-23T00:00:00+00:00",
    }
    base.update(fields)
    d = tmp_path / base["system_id"] / base["variant_id"]
    d.mkdir(parents=True, exist_ok=True)
    name = f"{base['metric']}-{base['contention']}-{base['value']}.yaml"
    (d / name).write_text(yaml.safe_dump(base))


@pytest.fixture
def store(tmp_path, monkeypatch):
    """Point the measurement store at a temp dir, so the test never depends on
    which runs happen to be recorded in the repo."""
    root = tmp_path / "measurements"
    root.mkdir()
    import spacepilot.measurements as ms
    # Both roots: readers merge the shipped corpus with this machine's own,
    # so pointing only the writable one at tmp still let the repo's records in.
    monkeypatch.setattr(ms, "MEASUREMENTS_DIR", root)
    monkeypatch.setattr(ms, "SHIPPED_MEASUREMENTS_DIR", root)
    return root


def test_measured_runs_reach_the_published_variant(store):
    _record(store, contention="solo", value=8.0)
    _record(store, contention="loaded", value=12.0)

    module = _exporter()
    models = [{"id": "kokoro", "variants": [{"id": "kokoro-82m"}, {"id": "other"}]}]
    attached = module.attach_measurements(models)

    assert attached == 1, "only the variant with records should gain measurements"
    assert "measurements" not in models[0]["variants"][1]

    got = models[0]["variants"][0]["measurements"]
    assert len(got) == 1, "one summary per (system, metric) pair"
    assert got[0]["system_id"] == "test-box"
    assert got[0]["metric"] == "seconds_per_image"


def test_the_two_streams_stay_separate(store):
    """Solo is what the machine can do; observed includes the busy runs. A
    single median hides exactly the contention the scheduler needs to see."""
    _record(store, contention="solo", value=8.0)
    _record(store, contention="loaded", value=12.0)
    _record(store, contention="loaded", value=16.0)

    module = _exporter()
    models = [{"id": "kokoro", "variants": [{"id": "kokoro-82m"}]}]
    module.attach_measurements(models)
    summary = models[0]["variants"][0]["measurements"][0]

    assert summary["solo_median"] == 8.0
    assert summary["solo_samples"] == 1
    assert summary["observed_samples"] == 3
    assert summary["observed_median"] == 12.0


def test_a_variant_measured_only_under_load_publishes_no_solo_number(store):
    """The honest case today: every FLUX run so far met a busy box, so the
    page must be able to say 'no solo sample' rather than quoting a loaded
    figure as if it were the ceiling."""
    _record(store, contention="loaded", value=32.985)

    module = _exporter()
    models = [{"id": "kokoro", "variants": [{"id": "kokoro-82m"}]}]
    module.attach_measurements(models)
    summary = models[0]["variants"][0]["measurements"][0]

    assert summary["solo_median"] is None
    assert summary["solo_samples"] == 0
    assert summary["observed_median"] == 32.985


def test_an_empty_store_changes_nothing(store):
    module = _exporter()
    models = [{"id": "kokoro", "variants": [{"id": "kokoro-82m"}]}]
    assert module.attach_measurements(models) == 0
    assert "measurements" not in models[0]["variants"][0]


def test_variant_id_remains_the_join_key_when_model_id_is_a_legacy_family_name(store):
    """New records can retain a family ``model_id`` while naming the exact variant.

    The exporter must not re-filter those rows by the old field after it has
    already correctly grouped them under ``variant_id``.
    """
    _record(store, model_id="kokoro", variant_id="kokoro-82m")
    module = _exporter()
    models = [{"id": "kokoro", "variants": [{"id": "kokoro-82m"}]}]

    assert module.attach_measurements(models) == 1
    summary = models[0]["variants"][0]["measurements"][0]
    assert summary["solo_median"] == 10.0


# --- The hook that stops spacepilot/web/registry.json rotting ----------------------------
#
# The staleness assertion in test_registry.py is a gate, not a cure: it catches
# the drift on a PR, after the author has moved on. `.githooks/pre-commit`
# regenerates the file at commit time instead. These guard the parts of that
# hook that break silently — a lost +x bit, a renamed flag — and would
# otherwise be noticed only by the CI failure it was meant to prevent.

HOOK = ROOT / ".githooks" / "pre-commit"
INSTALLER = ROOT / "tools" / "install_hooks.sh"


@pytest.mark.parametrize("script", [HOOK, INSTALLER], ids=["hook", "installer"])
def test_shipped_scripts_are_executable(script):
    """A hook without the execute bit is a hook git ignores, quietly."""
    assert script.is_file(), f"{script.relative_to(ROOT)} is missing"
    assert os.access(script, os.X_OK), (
        f"{script.relative_to(ROOT)} lost its execute bit — "
        f"git chmod +x {script.relative_to(ROOT)}"
    )


def test_the_hook_only_calls_flags_the_exporter_has():
    """The hook and the exporter are edited apart; this fails when they drift."""
    import subprocess

    hook = HOOK.read_text()
    assert "export_registry.py --sync" in hook, (
        "the hook no longer calls the exporter — "
        "if that is deliberate, this test should go with it"
    )
    help_text = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "export_registry.py"), "--help"],
        capture_output=True, text=True, check=True,
    ).stdout
    assert "--sync" in help_text and "--check" in help_text


def test_check_and_sync_agree_with_the_shipped_file(tmp_path):
    """--check must call the shipped file current exactly when it is.

    Both modes and the staleness test compare through one function, so this
    proves they cannot disagree about what stale means.
    """
    import json
    import subprocess

    exporter = _exporter()
    fresh, _ = exporter.build()

    shipped = json.loads((ROOT / "spacepilot" / "web" / "registry.json").read_text())
    current = exporter.data_of(shipped) == exporter.data_of(fresh)

    result = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "export_registry.py"), "--check"],
        cwd=ROOT, capture_output=True, text=True,
    )
    assert (result.returncode == 0) is current, (
        f"--check said {result.returncode == 0}, the data says {current}: "
        f"{result.stdout}{result.stderr}"
    )


def test_sync_leaves_a_current_file_alone(tmp_path):
    """A daily rewrite of a generated file is a diff nobody reads.

    `generated` moves on its own, so --sync must ignore it — otherwise the hook
    stages spacepilot/web/registry.json on the first commit of every new day.
    """
    import json
    import subprocess

    exporter = _exporter()
    payload, _ = exporter.build()
    out = tmp_path / "registry.json"

    payload["generated"] = "1999-01-01"
    out.write_text(exporter.render(payload))
    stamp = out.stat().st_mtime_ns

    subprocess.run(
        [sys.executable, str(ROOT / "tools" / "export_registry.py"),
         "--sync", "--out", str(out)],
        cwd=ROOT, capture_output=True, text=True, check=True,
    )
    assert out.stat().st_mtime_ns == stamp, "--sync rewrote a file whose data had not moved"
    assert json.loads(out.read_text())["generated"] == "1999-01-01"


def test_sync_rewrites_a_file_whose_data_moved(tmp_path):
    """The other half: real drift must actually be repaired."""
    import json
    import subprocess

    exporter = _exporter()
    payload, _ = exporter.build()
    out = tmp_path / "registry.json"

    payload["models"] = payload["models"][:-1]        # a model went missing
    out.write_text(exporter.render(payload))
    stale_count = len(payload["models"])

    subprocess.run(
        [sys.executable, str(ROOT / "tools" / "export_registry.py"),
         "--sync", "--out", str(out)],
        cwd=ROOT, capture_output=True, text=True, check=True,
    )
    assert len(json.loads(out.read_text())["models"]) == stale_count + 1
