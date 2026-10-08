"""Unit tests for spacepilot/services/model_downloader.py."""

from pathlib import Path
from typing import List, Optional
import pytest

from spacepilot.model_registry import Variant, Fact, License
from spacepilot.services.model_downloader import (
    STAGE_PATTERNS,
    download_weights,
    get_stage_patterns,
    resolve_model_repo_and_revision,
)


class MockEngine:
    def __init__(self):
        self.calls = []

    def __call__(
        self,
        repo_id: str,
        dest_dir: Path,
        allow_patterns: Optional[List[str]] = None,
        revision: Optional[str] = None,
        max_workers: int = 16,
    ) -> Path:
        self.calls.append({
            "repo_id": repo_id,
            "dest_dir": dest_dir,
            "allow_patterns": allow_patterns,
            "revision": revision,
            "max_workers": max_workers,
        })
        dest_dir.mkdir(parents=True, exist_ok=True)
        # Simulate creating downloaded files
        if allow_patterns:
            for pat in allow_patterns:
                clean_name = pat.replace("/**", "").replace("/*", "").replace("*", "")
                if clean_name:
                    file_path = dest_dir / clean_name / "weights.bin"
                    file_path.parent.mkdir(parents=True, exist_ok=True)
                    file_path.write_text("weights")
        else:
            (dest_dir / "full_model.bin").write_text("weights")
        return dest_dir


def test_resolve_model_repo_from_registry():
    """Resolves repo and revision from a registered variant id."""
    repo, revision, files = resolve_model_repo_and_revision("minimax-h3-fl2va-fp8")
    assert repo == "MiniMaxAI/MiniMax-H3"
    assert revision == "42ed227ee7df40d41602854ae760620d6eb651fe"
    assert "FL2VA/**" in files


def test_resolve_model_repo_from_direct_string():
    """Resolves repo from direct huggingface repo string."""
    repo, revision, files = resolve_model_repo_and_revision("some-org/custom-model")
    assert repo == "some-org/custom-model"
    assert revision is None
    assert files is None


def test_resolve_model_repo_from_variant_object():
    """Resolves directly from Variant instance."""
    v = Variant(
        id="test-var",
        model_id="test-mod",
        name="Test Var",
        kind="video",
        family="test",
        license=License(id="mit", open_source=True),
        repo="test/repo",
        files=["a.bin", "b.bin"],
        backends=["cuda"],
        download=Fact(100.0, "measured", "2026-10-06"),
        working_set=Fact(100.0, "measured", "2026-10-06"),
        revision="1234567890abcdef1234567890abcdef12345678",
    )
    repo, revision, files = resolve_model_repo_and_revision(v)
    assert repo == "test/repo"
    assert revision == "1234567890abcdef1234567890abcdef12345678"
    assert files == ["a.bin", "b.bin"]


def test_stage_patterns_resolution():
    """Verifies stage pattern mapping for stage1, stage2, and all."""
    s1 = get_stage_patterns("stage1")
    assert any("FL2VA" in p for p in s1)

    s2 = get_stage_patterns("stage2")
    assert any("Ref2VA" in p for p in s2)

    assert get_stage_patterns("all") is None

    with pytest.raises(ValueError, match="Unknown stage"):
        get_stage_patterns("unknown-stage")


def test_download_weights_stage1(tmp_path):
    """Downloads with stage1 filter matching FL2VA."""
    engine = MockEngine()
    out = download_weights(
        variant="minimax-h3-fl2va-fp8",
        dest_dir=tmp_path / "models",
        stage="stage1",
        concurrency=8,
        download_engine=engine,
    )
    assert out == (tmp_path / "models").resolve()
    assert len(engine.calls) == 1
    call = engine.calls[0]
    assert call["repo_id"] == "MiniMaxAI/MiniMax-H3"
    assert call["revision"] == "42ed227ee7df40d41602854ae760620d6eb651fe"
    assert call["max_workers"] == 8
    assert any("FL2VA/**" in pat for pat in call["allow_patterns"])
    assert not any("Ref2VA/**" in pat for pat in call["allow_patterns"])


def test_download_weights_stage2_refuses_wrong_variant(tmp_path):
    engine = MockEngine()
    with pytest.raises(ValueError, match="stage"):
        download_weights("minimax-h3-fl2va-fp8", tmp_path / "models", stage="stage2", download_engine=engine)
    assert engine.calls == []


def test_download_weights_all_keeps_registry_files_and_pin(tmp_path):
    engine = MockEngine()
    download_weights("minimax-h3", tmp_path / "models", stage="all", concurrency=16, download_engine=engine)
    call = engine.calls[0]
    assert call["revision"] == "42ed227ee7df40d41602854ae760620d6eb651fe"
    assert "FL2VA/**" in call["allow_patterns"]
    assert call["max_workers"] == 16


@pytest.mark.parametrize("concurrency", [0, 17, 32])
def test_download_rejects_unbounded_concurrency(tmp_path, concurrency):
    engine = MockEngine()
    with pytest.raises(ValueError, match="concurrency"):
        download_weights("minimax-h3", tmp_path / "models", concurrency=concurrency, download_engine=engine)
    assert engine.calls == []


def test_download_refuses_unpinned_repo(tmp_path):
    engine = MockEngine()
    with pytest.raises(ValueError, match="pinned"):
        download_weights("arbitrary/repo", tmp_path / "models", download_engine=engine)
    assert engine.calls == []


def test_download_weights_idempotence(tmp_path):
    """Repeated calls with same parameters return same destination without error."""
    engine = MockEngine()
    dest = tmp_path / "models"
    out1 = download_weights(
        variant="minimax-h3-fl2va-fp8",
        dest_dir=dest,
        stage="stage1",
        download_engine=engine,
    )
    out2 = download_weights(
        variant="minimax-h3-fl2va-fp8",
        dest_dir=dest,
        stage="stage1",
        download_engine=engine,
    )
    assert out1 == out2
    assert len(engine.calls) == 2
