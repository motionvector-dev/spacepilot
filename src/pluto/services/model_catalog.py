import asyncio
import uuid
from dataclasses import dataclass
from typing import Dict, List, Optional
from src.device_probe import probe_local_device

@dataclass
class ModelRecipeSpec:
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

@dataclass
class DownloadJob:
    job_id: str
    recipe_id: str
    status: str  # pending, downloading, completed, failed
    progress_percent: float
    speed_mb_s: float

class ModelCatalogManager:
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

    async def _mock_download_task(self, job_id: str):
        job = self.jobs[job_id]
        job.status = "downloading"
        job.speed_mb_s = 50.0
        
        for i in range(10):
            await asyncio.sleep(1)
            job.progress_percent = (i + 1) * 10
            
        job.status = "completed"
        job.speed_mb_s = 0.0
        job.progress_percent = 100.0

    def download_recipe(self, recipe_id: str) -> str:
        if recipe_id not in self.recipes:
            raise ValueError(f"Recipe not found: {recipe_id}")
            
        job_id = recipe_id
        job = DownloadJob(
            job_id=job_id,
            recipe_id=recipe_id,
            status="pending",
            progress_percent=0.0,
            speed_mb_s=0.0
        )
        self.jobs[job_id] = job
        asyncio.create_task(self._mock_download_task(job_id))
        return job_id

    def get_download_progress(self, job_id: str) -> Optional[DownloadJob]:
        return self.jobs.get(job_id)

catalog_manager = ModelCatalogManager()
