from pathlib import Path
from types import SimpleNamespace

import pytest

from spacepilot import paths
from spacepilot.drivers.gguf_driver import GGUFDriver
from spacepilot.drivers.kokoro_driver import KokoroDriver


def _resolved(tmp_path: Path, names: list[str], revision: str = "a" * 40):
    snapshot = tmp_path / "models--a--b" / "snapshots" / revision
    snapshot.mkdir(parents=True)
    files = []
    for name in names:
        path = snapshot / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"weights")
        files.append(path)
    return paths.ResolvedWeights(tuple(files), revision, snapshot, tmp_path)


def test_kokoro_uses_registry_resolver_as_one_asset_pair(tmp_path, monkeypatch):
    resolved = _resolved(tmp_path, ["kokoro-v1.0.onnx", "voices-v1.0.bin"])
    seen = {}

    def fake_resolve(repo, revision, patterns):
        seen.update(repo=repo, revision=revision, patterns=patterns)
        return resolved

    monkeypatch.delenv("SPACEPILOT_KOKORO_MODEL", raising=False)
    monkeypatch.delenv("SPACEPILOT_KOKORO_VOICES", raising=False)
    monkeypatch.delenv("PLUTO_KOKORO_MODEL", raising=False)
    monkeypatch.delenv("PLUTO_KOKORO_VOICES", raising=False)
    monkeypatch.setattr(paths, "resolve", fake_resolve)

    driver = KokoroDriver()
    model, voices = driver.asset_paths()
    assert (Path(model).name, Path(voices).name) == (
        "kokoro-v1.0.onnx", "voices-v1.0.bin")
    assert driver.resolved_revision == "a" * 40
    assert seen == {
        "repo": "fastrtc/kokoro-onnx",
        "revision": "8d07950c9b6c87ce6809e9bba7bd494336217c2a",
        "patterns": ["kokoro-v1.0.onnx", "voices-v1.0.bin"],
    }


def test_kokoro_refuses_partial_explicit_override(tmp_path):
    model = tmp_path / "model.onnx"
    model.write_bytes(b"weights")
    with pytest.raises(ValueError, match="both model_path and voices_path"):
        KokoroDriver(model_path=str(model)).asset_paths()


def test_kokoro_missing_weights_do_not_load_a_fallback(monkeypatch):
    monkeypatch.delenv("SPACEPILOT_KOKORO_MODEL", raising=False)
    monkeypatch.delenv("SPACEPILOT_KOKORO_VOICES", raising=False)
    monkeypatch.delenv("PLUTO_KOKORO_MODEL", raising=False)
    monkeypatch.delenv("PLUTO_KOKORO_VOICES", raising=False)
    monkeypatch.setattr(paths, "resolve", lambda *args, **kwargs: None)
    driver = KokoroDriver()
    assert driver.load() is False
    assert driver.is_loaded is False
    assert driver._session is None
    with pytest.raises(RuntimeError, match="real model weights"):
        driver.infer(text="This must not become a generated tone.")


def test_gguf_resolves_the_registered_concrete_file(tmp_path, monkeypatch):
    resolved = _resolved(tmp_path, ["model-q4.gguf"], revision="b" * 40)
    variant = SimpleNamespace(repo="org/gguf", revision="tag-v1", files=["model-q4.gguf"])
    fake_registry = SimpleNamespace(variant=lambda variant_id: variant)

    import spacepilot.model_registry as registry_module

    monkeypatch.delenv("SPACEPILOT_GGUF_MODEL", raising=False)
    monkeypatch.delenv("PLUTO_GGUF_MODEL", raising=False)
    monkeypatch.setattr(registry_module, "registry", lambda: fake_registry)
    monkeypatch.setattr(paths, "resolve", lambda *args, **kwargs: resolved)

    driver = GGUFDriver(driver_id="text-gguf-q4")
    assert Path(driver._discover_model_path()).name == "model-q4.gguf"
    assert driver.resolved_revision == "b" * 40


def test_drivers_never_restore_machine_specific_weight_guesses():
    root = Path(__file__).resolve().parents[1] / "spacepilot" / "drivers"
    forbidden = (".cache/pluto", "katana", "hyperframes")
    offenders = []
    for path in root.glob("*.py"):
        text = path.read_text().lower()
        for token in forbidden:
            if token in text:
                offenders.append(f"{path.name}: {token}")
    assert not offenders, "; ".join(offenders)


def test_measurement_prefers_resolved_bytes_over_registry_pin(system, tmp_path):
    from spacepilot import measurements as ms

    resolved = "c" * 40
    path = ms.record(
        system=system,
        model_id="kokoro-82m-onnx",
        metric="realtime_factor",
        value=1.0,
        contention="solo",
        root=tmp_path,
        resolved_revision=resolved,
    )
    raw = __import__("yaml").safe_load(path.read_text())
    assert raw["model_revision"] == resolved


@pytest.fixture
def system():
    from spacepilot.measurements import System

    return System(id="resolver-test", backend="cpu", os_name="linux")
