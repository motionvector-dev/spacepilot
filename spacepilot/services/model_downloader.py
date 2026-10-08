"""Model weight downloader service supporting stage filters and concurrency.

Provides `download_weights` for downloading models (such as MiniMax-H3)
with support for stage-based pattern filtering, concurrency limits,
registry variant resolution, and pluggable/mockable download engines.
"""

from __future__ import annotations

import logging
from fnmatch import fnmatch
from pathlib import Path
from typing import Callable, List, Optional, Protocol, Union

from spacepilot.model_registry import Variant, registry

logger = logging.getLogger(__name__)

STAGE_PATTERNS = {
    "stage1": [
        "FL2VA/**",
        "FL2VA/*",
        "*.json",
        "*.txt",
        "tokenizer*",
        "config.json",
        "configuration*",
    ],
    "stage2": [
        "Ref2VA/**",
        "Ref2VA/*",
        "*.json",
        "*.txt",
        "tokenizer*",
        "config.json",
        "configuration*",
    ],
    "all": ["*"],
}


class DownloadEngine(Protocol):
    """Protocol for snapshot download engine."""

    def __call__(
        self,
        repo_id: str,
        dest_dir: Path,
        allow_patterns: Optional[List[str]] = None,
        revision: Optional[str] = None,
        max_workers: int = 16,
    ) -> Path: ...


def default_huggingface_download_engine(
    repo_id: str,
    dest_dir: Path,
    allow_patterns: Optional[List[str]] = None,
    revision: Optional[str] = None,
    max_workers: int = 16,
) -> Path:
    """Default download engine using huggingface_hub.snapshot_download."""
    from huggingface_hub import snapshot_download

    dest_dir.mkdir(parents=True, exist_ok=True)
    out_path = snapshot_download(
        repo_id=repo_id,
        local_dir=str(dest_dir),
        allow_patterns=allow_patterns,
        revision=revision,
        max_workers=max_workers,
    )
    return Path(out_path)


def resolve_model_repo_and_revision(
    variant: Union[str, Variant],
) -> tuple[str, Optional[str], Optional[List[str]]]:
    """Resolve repo_id, revision, and files list from variant or variant_id/repo string."""
    if isinstance(variant, Variant):
        return variant.repo, variant.revision, variant.files

    if isinstance(variant, str):
        # 1. Check if it matches a variant id in registry
        reg = registry()
        v = reg.variant(variant)
        if v is not None:
            return v.repo, v.revision, v.files

        # 2. Check if it matches a model id in registry
        m = reg.model(variant)
        if m is not None and m.variants:
            first = m.variants[0]
            return first.repo, first.revision, first.files

        # 3. Direct repo string (e.g. "MiniMaxAI/MiniMax-H3")
        return variant, None, None

    raise ValueError(f"Unsupported variant type: {type(variant)}")


def get_stage_patterns(stage: str) -> Optional[List[str]]:
    """Return allow_patterns for the specified stage."""
    stage_key = stage.lower().strip()
    if stage_key == "all":
        return None
    if stage_key in STAGE_PATTERNS:
        return list(STAGE_PATTERNS[stage_key])
    raise ValueError(f"Unknown stage '{stage}'. Supported stages: 'all', 'stage1', 'stage2'.")


def download_weights(
    variant: Union[str, Variant],
    dest_dir: Path,
    stage: str = "all",
    concurrency: int = 16,
    download_engine: Optional[DownloadEngine] = None,
) -> Path:
    """Download model weights with stage filters, concurrency, and idempotent execution.

    Args:
        variant: Variant instance, variant ID (e.g. 'minimax-h3-fl2va-fp8'),
                 model ID, or repo ID (e.g. 'MiniMaxAI/MiniMax-H3').
        dest_dir: Target destination directory for downloaded files.
        stage: Download stage filter ('stage1', 'stage2', or 'all').
        concurrency: Max concurrent download workers.
        download_engine: Optional callable implementing DownloadEngine protocol for testing.

    Returns:
        Path to the downloaded model directory.
    """
    if not 1 <= concurrency <= 16:
        raise ValueError("concurrency must be 1..16")
    dest_dir = Path(dest_dir).expanduser().resolve()

    repo_id, revision, variant_files = resolve_model_repo_and_revision(variant)
    if not revision:
        raise ValueError("Download requires a registered model with a pinned revision")
    if stage == "stage2" and variant_files and "FL2VA/**" in variant_files:
        raise ValueError("Selected stage has no files for this FL2VA variant")
    stage_patterns = get_stage_patterns(stage)

    # Combine variant allowed files and stage patterns if both exist
    allow_patterns: Optional[List[str]] = None
    if stage_patterns is not None and variant_files is not None:
        # Match variant files against stage patterns
        allow_patterns = [
            f for f in variant_files
            if any(fnmatch(f, pat) for pat in stage_patterns)
        ]
    elif stage_patterns is not None:
        allow_patterns = stage_patterns
    elif variant_files is not None:
        allow_patterns = list(variant_files)

    if allow_patterns == []:
        raise ValueError("Selected stage has no files for this variant")
    dest_dir.mkdir(parents=True, exist_ok=True)
    engine = download_engine or default_huggingface_download_engine

    logger.info(
        "Downloading weights for %s (revision=%s, stage=%s, concurrency=%d) to %s",
        repo_id, revision, stage, concurrency, dest_dir,
    )

    result_path = engine(
        repo_id=repo_id,
        dest_dir=dest_dir,
        allow_patterns=allow_patterns,
        revision=revision,
        max_workers=concurrency,
    )

    return Path(result_path)
