import asyncio
import os
import time
from pathlib import Path
import uuid
from pydantic import BaseModel
from typing import Dict, List, Optional
import logging

# Direct import from src.device_probe because it's an external utility not part of the pluto module structure
from src.device_probe import probe_local_device

logger = logging.getLogger(__name__)

class ModelRecipeSpec(BaseModel):
    recipe_id: str
    name: str
    family: str
    size_gb: float
    min_vram_gb: float
    quantization: str
    hf_repo: str
    download_url: str
    recommended_gpu: str
    is_local_runnable: bool = False

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

class ModelCatalogManager:
    """Manages the available model recipes and handles background downloads."""
    
    def __init__(self):
        self.recipes: Dict[str, ModelRecipeSpec] = {
            "wan-2.1-1.3b-fp8": ModelRecipeSpec(
                recipe_id="wan-2.1-1.3b-fp8",
                name="Wan 2.1 1.3B FP8",
                family="wan",
                size_gb=1.5,
                min_vram_gb=8.0,
                quantization="fp8",
                hf_repo="wan-ai/wan-2.1-1.3b-fp8",
                download_url="https://huggingface.co/wan-ai/wan-2.1-1.3b-fp8/resolve/main/model.safetensors",
                recommended_gpu="RTX 4060"
            ),
            "wan-2.1-14b-fp8": ModelRecipeSpec(
                recipe_id="wan-2.1-14b-fp8",
                name="Wan 2.1 14B FP8",
                family="wan",
                size_gb=15.0,
                min_vram_gb=16.0,
                quantization="fp8",
                hf_repo="wan-ai/wan-2.1-14b-fp8",
                download_url="https://huggingface.co/wan-ai/wan-2.1-14b-fp8/resolve/main/model.safetensors",
                recommended_gpu="RTX 4080"
            ),
            "hunyuan-video-gguf-q4": ModelRecipeSpec(
                recipe_id="hunyuan-video-gguf-q4",
                name="Hunyuan Video GGUF Q4",
                family="hunyuan",
                size_gb=10.0,
                min_vram_gb=12.0,
                quantization="gguf-q4",
                hf_repo="tencent/hunyuan-video-gguf-q4",
                download_url="https://huggingface.co/tencent/hunyuan-video-gguf-q4/resolve/main/model.gguf",
                recommended_gpu="RTX 4070 Ti"
            ),
            "deepseek-r1-distill-qwen-8b-gguf": ModelRecipeSpec(
                recipe_id="deepseek-r1-distill-qwen-8b-gguf",
                name="DeepSeek R1 Distill Qwen 8B GGUF",
                family="deepseek",
                size_gb=6.0,
                min_vram_gb=8.0,
                quantization="gguf",
                hf_repo="deepseek-ai/deepseek-r1-distill-qwen-8b-gguf",
                download_url="https://huggingface.co/deepseek-ai/deepseek-r1-distill-qwen-8b-gguf/resolve/main/model.gguf",
                recommended_gpu="RTX 4060"
            ),
            "qwen2.5-vl-7b-int4": ModelRecipeSpec(
                recipe_id="qwen2.5-vl-7b-int4",
                name="Qwen2.5 VL 7B INT4",
                family="qwen",
                size_gb=4.5,
                min_vram_gb=6.0,
                quantization="int4",
                hf_repo="qwen/qwen2.5-vl-7b-int4",
                download_url="https://huggingface.co/qwen/qwen2.5-vl-7b-int4/resolve/main/model.safetensors",
                recommended_gpu="RTX 4060"
            ),
            "ltx-video-2.5-fp8": ModelRecipeSpec(
                recipe_id="ltx-video-2.5-fp8",
                name="LTX Video 2.5 FP8",
                family="ltx",
                size_gb=14.0,
                min_vram_gb=16.0,
                quantization="fp8",
                hf_repo="lightricks/ltx-video-2.5-fp8",
                download_url="https://huggingface.co/lightricks/ltx-video-2.5-fp8/resolve/main/model.safetensors",
                recommended_gpu="RTX 4080"
            ),
        }
        self.jobs: Dict[str, DownloadJob] = {}

    def get_all_recipes(self) -> List[ModelRecipeSpec]:
        """Get all model recipes with updated local compatibility."""
        device_info = probe_local_device()
        vram_gb = device_info.vram_usable_gb
        
        results = []
        for r in self.recipes.values():
            # Create a copy so we can mutate is_local_runnable based on current device
            spec = ModelRecipeSpec(
                recipe_id=r.recipe_id,
                name=r.name,
                family=r.family,
                size_gb=r.size_gb,
                min_vram_gb=r.min_vram_gb,
                quantization=r.quantization,
                hf_repo=r.hf_repo,
                download_url=r.download_url,
                recommended_gpu=r.recommended_gpu,
                is_local_runnable=vram_gb >= r.min_vram_gb
            )
            results.append(spec)
        return results

    def get_recipe(self, recipe_id: str) -> Optional[ModelRecipeSpec]:
        """Get a specific model recipe by ID with updated local compatibility."""
        recipe = self.recipes.get(recipe_id)
        if not recipe:
            return None
            
        device_info = probe_local_device()
        vram_gb = device_info.vram_usable_gb
        
        spec = ModelRecipeSpec(
            recipe_id=recipe.recipe_id,
            name=recipe.name,
            family=recipe.family,
            size_gb=recipe.size_gb,
            min_vram_gb=recipe.min_vram_gb,
            quantization=recipe.quantization,
            hf_repo=recipe.hf_repo,
            download_url=recipe.download_url,
            recommended_gpu=recipe.recommended_gpu,
            is_local_runnable=vram_gb >= recipe.min_vram_gb
        )
        return spec

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

    def _run_download(self, job_id: str, repo_id: str) -> None:
        """Download a repo. Runs on a worker thread."""
        from huggingface_hub import snapshot_download

        job = self.jobs[job_id]
        self.MODELS_DIR.mkdir(parents=True, exist_ok=True)
        job.local_path = snapshot_download(repo_id=repo_id, cache_dir=str(self.MODELS_DIR))

    async def _download_task(self, job_id: str, repo_id: str):
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
                    lambda: HfApi().model_info(repo_id, files_metadata=True)
                )
                total = sum(f.size or 0 for f in (info.siblings or []))
                if total:
                    job.total_bytes = total
            except Exception as e:
                logger.warning("could not size %s up front: %s", repo_id, e)

            started = time.monotonic()
            task = asyncio.create_task(asyncio.to_thread(self._run_download, job_id, repo_id))
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
            logger.info("downloaded %s to %s (%d bytes)", repo_id, job.local_path, job.downloaded_bytes)
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
            total_bytes=int((recipe.size_gb or 0) * 1_073_741_824) or None,
        )
        self.jobs[job_id] = job
        asyncio.create_task(self._download_task(job_id, recipe.hf_repo))
        return job_id

    def get_download_progress(self, job_id: str) -> Optional[DownloadJob]:
        """Get the progress of a specific download job."""
        return self.jobs.get(job_id)

catalog_manager = ModelCatalogManager()
