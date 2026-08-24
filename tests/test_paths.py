"""Where records go, decided in one place so it can be tested in one place."""

import sys
from pathlib import Path

import pytest

from spacepilot import paths


def test_the_env_override_wins_over_everything(tmp_path, monkeypatch):
    """This is what lets the suite redirect writes, exactly as
    $PLUTO_OUTPUTS_DIR already does for generated files. It has to beat the
    checkout rule too, or the tests would write into the repo they run in."""
    monkeypatch.setenv("SPACEPILOT_DATA_DIR", str(tmp_path))
    assert paths.user_data_dir() == tmp_path.resolve()
    assert paths.writable_registry_root() == tmp_path.resolve() / "registry"


def test_spacepilot_env_names_are_canonical_with_pluto_fallback(monkeypatch):
    monkeypatch.setenv("PLUTO_DATA_DIR", "/tmp/legacy-spacepilot-data")
    monkeypatch.setenv("SPACEPILOT_DATA_DIR", "/tmp/canonical-spacepilot-data")
    assert paths.env_value("SPACEPILOT_DATA_DIR", "PLUTO_DATA_DIR") == "/tmp/canonical-spacepilot-data"
    assert paths.user_data_dir() == Path("/tmp/canonical-spacepilot-data").resolve()

    monkeypatch.delenv("SPACEPILOT_DATA_DIR")
    assert paths.env_value("SPACEPILOT_DATA_DIR", "PLUTO_DATA_DIR") == "/tmp/legacy-spacepilot-data"
    assert paths.user_data_dir() == Path("/tmp/legacy-spacepilot-data").resolve()


def test_settings_accepts_spacepilot_names_and_preserves_pluto_fallback(tmp_path, monkeypatch):
    from spacepilot.pluto.core.config import Settings

    monkeypatch.setenv("SPACEPILOT_OUTPUTS_DIR", str(tmp_path / "canonical-output"))
    monkeypatch.setenv("PLUTO_OUTPUTS_DIR", str(tmp_path / "legacy-output"))
    monkeypatch.setenv("SPACEPILOT_STUDIO_HOST", "127.0.0.9")
    monkeypatch.setenv("SPACEPILOT_STUDIO_PORT", "9090")
    monkeypatch.setenv("SPACEPILOT_ALLOW_REMOTE", "1")
    monkeypatch.setenv("SPACEPILOT_KOKORO_MODEL", "/models/kokoro.onnx")
    monkeypatch.setenv("SPACEPILOT_KOKORO_VOICES", "/models/voices.bin")

    settings = Settings()
    assert settings.outputs_dir == (tmp_path / "canonical-output").resolve()
    assert settings.host == "127.0.0.9"
    assert settings.port == 9090
    assert settings.local_only is False
    assert settings.kokoro_model_path == "/models/kokoro.onnx"
    assert settings.kokoro_voices_path == "/models/voices.bin"


def test_the_platform_directory_is_used_when_nothing_is_set(tmp_path, monkeypatch):
    monkeypatch.delenv("SPACEPILOT_DATA_DIR", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    got = paths.user_data_dir()
    assert tmp_path.resolve() in got.parents
    expected = ("Library/Application Support/spacepilot" if sys.platform == "darwin"
                else ".local/share/spacepilot")
    assert str(got).endswith(expected)


def test_xdg_data_home_is_honoured_off_macos(tmp_path, monkeypatch):
    if sys.platform == "darwin":
        pytest.skip("XDG is not the macOS convention")
    monkeypatch.delenv("SPACEPILOT_DATA_DIR", raising=False)
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    assert paths.user_data_dir() == tmp_path.resolve() / "spacepilot"


def test_a_checkout_writes_to_the_repo(monkeypatch):
    """A contributor's `pluto measure` has to produce something they can commit,
    or the corpus stops growing."""
    monkeypatch.delenv("SPACEPILOT_DATA_DIR", raising=False)
    root = paths.checkout_root()
    assert root is not None, "the test suite runs from a checkout"
    assert root == Path(__file__).resolve().parents[1]
    assert paths.writable_registry_root() == root / "spacepilot" / "registry"


def test_the_shipped_catalogue_is_found_through_the_package():
    """Not by walking up from __file__ — that is what pointed at site-packages
    on an installed copy and made `spacepilot models` exit 1."""
    root = paths.shipped_registry_root()
    assert (root / "models").is_dir()
    assert (root / "runtimes").is_dir()
    assert root.parent.name == "spacepilot"


def test_reads_never_visit_the_same_directory_twice(monkeypatch):
    """In a checkout the shipped and writable roots are one directory, and
    reading it twice would double every record."""
    monkeypatch.delenv("SPACEPILOT_DATA_DIR", raising=False)
    roots = paths.read_roots("measurements")
    assert len(roots) == len(set(roots)) == 1


def test_reads_merge_shipped_and_user_records(tmp_path, monkeypatch):
    monkeypatch.setenv("SPACEPILOT_DATA_DIR", str(tmp_path))
    roots = paths.read_roots("measurements")
    assert len(roots) == 2
    assert roots[0] == paths.shipped_registry_root().resolve() / "measurements"
    assert roots[1] == tmp_path.resolve() / "registry" / "measurements"


def test_a_record_written_under_the_override_is_read_back(tmp_path, monkeypatch):
    """End to end through the measurement store, not just the path helpers."""
    import spacepilot.pluto.measurements as ms

    store = tmp_path / "measurements"
    monkeypatch.setattr(ms, "MEASUREMENTS_DIR", store)
    monkeypatch.setattr(ms, "SHIPPED_MEASUREMENTS_DIR", tmp_path / "shipped")

    system = ms.System(id="test-box", backend="cpu", os_name="linux")
    path = ms.record(system=system, model_id="kokoro-82m",
                     metric="seconds_per_image", value=1.0, contention="solo")

    assert store in path.parents
    assert [m.model_id for m in ms.load_measurements()] == ["kokoro-82m"]
