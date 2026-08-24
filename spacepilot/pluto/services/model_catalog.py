import asyncio
import fnmatch
import os
import time
from pathlib import Path
import uuid
from pydantic import BaseModel
from typing import Dict, List, Optional
import logging

# Direct import from spacepilot.device_probe because it's an external utility not part of the pluto module structure
from spacepilot.device_probe import probe_local_device
from spacepilot.pluto.services.compatibility import assess, assess_all, recommend
from spacepilot.pluto.registry import Variant, registry

logger = logging.getLogger(__name__)

GIB = 1024 ** 3


class ModelRecipeSpec(BaseModel):
    recipe_id: str
    name: str
    family: str
    kind: str = "video"            # video | tts | llm | vlm
    params: Optional[str] = None
    quantization: str

    hf_repo: str
    # The exact commit these bytes come from. None means the download follows
    # whatever the repo's default branch points at on the day it runs, so two
    # people asking for the same recipe can get different weights and neither
    # can tell. The registry says which variants are in that state.
    revision: Optional[str] = None
    # Repos hold many alternative checkpoints. LTX-Video is 236 GB whole; the
    # one file we want is 15. Never fetch a repo without narrowing it.
    allow_patterns: Optional[List[str]] = None
    download_bytes: Optional[int] = None

    # Peak memory while generating, which is weights plus activations, not the
    # download size. Confidence says whether anyone has actually measured it.
    working_set_bytes: Optional[int] = None
    working_set_confidence: str = "estimated"   # measured | estimated | unknown

    backends: List[str] = ["metal", "cuda"]
    license: str = "unknown"
    license_note: Optional[str] = None

    speed: List[Dict[str, object]] = []

    download_url: str = ""
    recommended_gpu: str = "any"
    is_local_runnable: bool = False

    @property
    def is_pinned(self) -> bool:
        return bool(self.revision)

    @property
    def size_gb(self) -> float:
        return round((self.download_bytes or 0) / GIB, 2)

    @property
    def min_vram_gb(self) -> float:
        return round((self.working_set_bytes or 0) / GIB, 2)


class DownloadJob(BaseModel):
    job_id: str
    recipe_id: str
    status: str  # pending, downloading, completed, failed
    progress_percent: float
    speed_mb_s: float
    downloaded_bytes: int = 0
    total_bytes: Optional[int] = None   # from the recipe; None when unknown
    local_path: Optional[str] = None    # set on success, so callers can find the weights
    error: Optional[str] = None         # set on failure, so a caller can tell

    # What was asked for, and what the Hub actually handed back. They differ
    # whenever `requested_revision` is None: the resolved SHA is then the only
    # record of which weights these bytes are, and it is knowable only after
    # the fact. Anything that later reports a number about this download —
    # a measurement, above all — should carry `resolved_revision`, not the
    # repo id, because the repo id will point somewhere else eventually.
    requested_revision: Optional[str] = None
    resolved_revision: Optional[str] = None


def _spec_from_variant(v: Variant) -> "ModelRecipeSpec":
    """Flatten one registry variant into the shape the API and CLI already speak."""
    return ModelRecipeSpec(
        recipe_id=v.id,
        name=v.name,
        family=v.family,
        kind=v.kind,
        params=v.params,
        quantization=v.precision or "unknown",
        hf_repo=v.repo,
        revision=v.revision,
        allow_patterns=list(v.files) if v.files else None,
        download_bytes=int(v.download.value),
        working_set_bytes=int(v.working_set.value),
        working_set_confidence=v.working_set.source,
        backends=list(v.backends),
        license=v.license.id,
        license_note="; ".join(v.license.restrictions) or None,
        speed=[s.to_dict() for s in v.speed],
    )


class ModelCatalogManager:
    """Manages the available model recipes and handles background downloads."""
    
    def __init__(self):
        # Recipes are a view over the registry, not a second copy of it.
        # registry/models/*.yaml is the one place a model is described.
        self.recipes: Dict[str, ModelRecipeSpec] = {
            v.id: _spec_from_variant(v) for v in registry().variants
        }
        self.jobs: Dict[str, DownloadJob] = {}

    def get_all_recipes(self) -> List[ModelRecipeSpec]:
        """Every recipe, with is_local_runnable answered against this machine."""
        profile = probe_local_device()
        results = []
        for r in self.recipes.values():
            spec = r.model_copy()
            spec.is_local_runnable = assess(r, profile).verdict in ("fits", "tight")
            results.append(spec)
        return results

    def get_recipe(self, recipe_id: str) -> Optional[ModelRecipeSpec]:
        recipe = self.recipes.get(recipe_id)
        if not recipe:
            return None
        spec = recipe.model_copy()
        spec.is_local_runnable = assess(recipe, probe_local_device()).verdict in ("fits", "tight")
        return spec

    def compatibility_report(self) -> Dict[str, object]:
        """The device, every model's verdict against it, and what to lead with."""
        profile = probe_local_device()
        recipes = list(self.recipes.values())
        verdicts = {v.recipe_id: v.to_dict() for v in assess_all(recipes, profile)}
        return {
            "device": profile.to_dict(),
            "models": [r.model_dump() for r in recipes],
            "verdicts": verdicts,
            "recommended": recommend(recipes, profile),
            "installed": sorted(self.installed_repos()),
        }

    def installed_repos(self) -> List[str]:
        """Repo ids already in the local cache, read from the hub layout."""
        hub = self.MODELS_DIR / "hub"
        if not hub.exists():
            return []
        out = []
        for d in hub.iterdir():
            if d.is_dir() and d.name.startswith("models--"):
                out.append(d.name[len("models--"):].replace("--", "/"))
        return out

    # Models live in one cache under ~/.spacepilot/models, the layout
    # huggingface_hub uses natively (hub/ + locks/). One directory to inspect,
    # one to delete when reclaiming disk.
    MODELS_DIR = Path(os.environ.get("SPACEPILOT_MODELS_DIR", Path.home() / ".spacepilot" / "models"))

    @staticmethod
    def _dir_bytes(path: Path) -> int:
        # Count blobs/ only. The hub stores each file's content once under blobs/
        # and materialises it again under snapshots/ — on a filesystem where that
        # is a copy rather than a symlink, walking everything double-counts and
        # reports twice the bytes that crossed the network.
        total = 0
        for f in path.rglob("*"):
            try:
                if f.is_file() and not f.is_symlink() and "snapshots" not in f.parts:
                    total += f.stat().st_size
            except OSError:
                pass  # file vanished mid-walk; hub writes then renames
        return total  # includes small refs/ and lock metadata, so it reads a
                      # couple of KB above the Hub's payload total. That is real
                      # disk used, which is the number a user cares about.

    @staticmethod
    def _revision_from_path(local_path: Optional[str]) -> Optional[str]:
        """Read the resolved commit out of the hub cache path.

        snapshot_download returns `<cache>/models--org--name/snapshots/<sha>`.
        That last component is the commit the download actually landed on, and
        it is the only place the answer exists when no revision was requested.
        """
        if not local_path:
            return None
        parts = Path(local_path).parts
        if "snapshots" in parts:
            idx = len(parts) - 1 - parts[::-1].index("snapshots")
            if idx + 1 < len(parts):
                return parts[idx + 1]
        return None

    def _run_download(self, job_id: str, repo_id: str, allow_patterns=None,
                      revision: Optional[str] = None) -> None:
        """Download a repo at a named revision. Runs on a worker thread."""
        from huggingface_hub import snapshot_download

        job = self.jobs[job_id]
        self.MODELS_DIR.mkdir(parents=True, exist_ok=True)
        job.local_path = snapshot_download(
            repo_id=repo_id,
            cache_dir=str(self.MODELS_DIR),
            allow_patterns=allow_patterns,
            revision=revision,
        )
        # Resolve even when a revision was requested: a tag is a pin only
        # until somebody moves it, and the SHA says which commit it meant.
        job.resolved_revision = self._revision_from_path(job.local_path) or revision

    async def _download_task(self, job_id: str, repo_id: str, allow_patterns=None,
                             revision: Optional[str] = None):
        """Run the download, reporting bytes actually on disk.

        Progress is measured by walking the cache directory rather than by hooking
        huggingface_hub's progress bars: in hub 1.x, tqdm_class only wraps the outer
        'Fetching N files' counter, so anything derived from it reports file counts
        as though they were bytes. Disk is the ground truth and does not move
        between library versions.
        """
        from huggingface_hub import HfApi

        job = self.jobs[job_id]
        before = self._dir_bytes(self.MODELS_DIR) if self.MODELS_DIR.exists() else 0
        try:
            job.status = "downloading"

            # Exact total from the Hub, not the recipe's size_gb estimate.
            try:
                info = await asyncio.to_thread(
                    lambda: HfApi().model_info(
                        repo_id, revision=revision, files_metadata=True)
                )
                siblings = info.siblings or []
                if allow_patterns:
                    siblings = [
                        f for f in siblings
                        if any(fnmatch.fnmatch(f.rfilename, pat) for pat in allow_patterns)
                    ]
                total = sum(f.size or 0 for f in siblings)
                if total:
                    job.total_bytes = total
            except Exception as e:
                logger.warning("could not size %s up front: %s", repo_id, e)

            started = time.monotonic()
            task = asyncio.create_task(
                asyncio.to_thread(self._run_download, job_id, repo_id,
                                  allow_patterns, revision)
            )
            while not task.done():
                await asyncio.sleep(0.5)
                got = max(0, self._dir_bytes(self.MODELS_DIR) - before)
                job.downloaded_bytes = got
                elapsed = time.monotonic() - started
                if elapsed > 0:
                    job.speed_mb_s = round(got / elapsed / 1_048_576, 2)
                if job.total_bytes:
                    job.progress_percent = round(min(99.9, got / job.total_bytes * 100.0), 1)
            await task  # re-raises whatever the download raised

            job.downloaded_bytes = max(0, self._dir_bytes(self.MODELS_DIR) - before)
            job.status = "completed"
            job.progress_percent = 100.0
            job.speed_mb_s = 0.0
            logger.info("downloaded %s@%s to %s (%d bytes)", repo_id,
                        job.resolved_revision or "unpinned", job.local_path,
                        job.downloaded_bytes)
            if not job.requested_revision:
                logger.warning(
                    "%s was downloaded unpinned; it resolved to %s today, but "
                    "the registry does not pin it, so this is not reproducible",
                    repo_id, job.resolved_revision or "an unknown commit")
        except Exception as e:
            # A failed download must read as failed. The previous implementation
            # slept ten seconds and reported success regardless.
            job.status = "failed"
            job.error = str(e)
            job.speed_mb_s = 0.0
            logger.error("download failed for %s: %s", repo_id, e, exc_info=True)

    def download_recipe(self, recipe_id: str) -> str:
        """Start a background download job for a recipe."""
        if recipe_id not in self.recipes:
            raise ValueError(f"Recipe not found: {recipe_id}")
            
        recipe = self.recipes[recipe_id]
        if not recipe.hf_repo:
            raise ValueError(f"Recipe {recipe_id} has no hf_repo to download from")

        job_id = recipe_id
        job = DownloadJob(
            job_id=job_id,
            recipe_id=recipe_id,
            status="pending",
            progress_percent=0.0,
            speed_mb_s=0.0,
            total_bytes=recipe.download_bytes,
            requested_revision=recipe.revision,
        )
        self.jobs[job_id] = job
        asyncio.create_task(
            self._download_task(job_id, recipe.hf_repo, recipe.allow_patterns,
                                recipe.revision)
        )
        return job_id

    def download_recipe_blocking(self, recipe_id: str) -> DownloadJob:
        """Synchronous download for the CLI, which has no running event loop.

        Builds the same job download_recipe does and runs _download_task to
        completion in a private loop. Poll get_download_progress(recipe_id)
        from another thread for live progress while this runs.
        """
        if recipe_id not in self.recipes:
            raise ValueError(f"Recipe not found: {recipe_id}")
        recipe = self.recipes[recipe_id]
        if not recipe.hf_repo:
            raise ValueError(f"Recipe {recipe_id} has no hf_repo to download from")
        self.jobs[recipe_id] = DownloadJob(
            job_id=recipe_id,
            recipe_id=recipe_id,
            status="pending",
            progress_percent=0.0,
            speed_mb_s=0.0,
            total_bytes=recipe.download_bytes,
            requested_revision=recipe.revision,
        )
        asyncio.run(self._download_task(
            recipe_id, recipe.hf_repo, recipe.allow_patterns, recipe.revision))
        return self.jobs[recipe_id]

    def get_download_progress(self, job_id: str) -> Optional[DownloadJob]:
        """Get the progress of a specific download job."""
        return self.jobs.get(job_id)

catalog_manager = ModelCatalogManager()
