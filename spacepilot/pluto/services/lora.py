import json
import logging
import random
import time
import uuid
import asyncio
import tempfile
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, List

logger = logging.getLogger(__name__)

@dataclass
class LoRAAdapterSpec:
    """Specification for a LoRA adapter."""
    adapter_id: str
    name: str
    base_model: str
    rank: int
    alpha: float
    trigger_word: str
    checkpoint_path: str
    size_mb: float
    is_active: bool

class LoRAManager:
    """Manages LoRA adapters and training jobs."""
    
    def __init__(self):
        self._adapters: dict[str, LoRAAdapterSpec] = {}
        self._jobs: dict[str, dict] = {}

    def list_adapters(self, base_model: Optional[str] = None) -> List[LoRAAdapterSpec]:
        """
        List available LoRA adapters, optionally filtered by base model.
        
        Args:
            base_model: Optional base model to filter adapters by.
            
        Returns:
            List of LoRAAdapterSpec instances.
        """
        adapters = list(self._adapters.values())
        if base_model:
            adapters = [a for a in adapters if a.base_model == base_model]
        return adapters

    def create_training_job(self, name: str, base_model: str, image_paths: List[str], trigger_word: str, rank: int = 16, steps: int = 500, lr: float = 1e-4, alpha: float = 16.0, target_modules: Optional[List[str]] = None) -> dict:
        """
        Create a new LoRA training job.
        
        Args:
            name: The name of the adapter.
            base_model: The base model ID.
            image_paths: List of image paths for training.
            trigger_word: Trigger word for the adapter.
            rank: The rank for the LoRA adapter.
            steps: The number of training steps.
            lr: The learning rate.
            alpha: The alpha parameter for the LoRA adapter.
            target_modules: The target modules to train.
            
        Returns:
            A dictionary containing the job details.
        """
        # GATED 2026-08-24: _advance_training only SIMULATES training — it ticks
        # a fake progress bar, invents a loss curve with random noise, and
        # registers an adapter whose .safetensors is never written. Returning
        # that as a real job is the same fake-success lie as the gated mocks.
        # Real LoRA training (an mflux/diffusers run producing a real
        # checkpoint) is a separate, unbuilt feature. Until it exists this
        # raises rather than pretend.
        raise NotImplementedError(
            "LoRA training is not implemented; the previous job was a "
            "simulation (fake loss curve, no real checkpoint). Gated 2026-08-24."
        )
        job_id = f"job-{uuid.uuid4().hex[:8]}"
        self._jobs[job_id] = {
            "job_id": job_id,
            "name": name,
            "base_model": base_model,
            "image_paths": image_paths,
            "trigger_word": trigger_word,
            "rank": rank,
            "alpha": alpha,
            "target_modules": target_modules or [],
            "steps": steps,
            "lr": lr,
            "status": "training",
            "current_step": 0,
            "loss_curve": []
        }
        
        # Start background worker to advance training reliably across ASGI, sync CLI, MCP, and tests
        import threading
        threading.Thread(target=lambda: asyncio.run(self._advance_training(job_id)), daemon=True).start()
        
        return self._jobs[job_id]

    async def _advance_training(self, job_id: str) -> None:
        """
        Background worker to simulate training progression.
        
        Args:
            job_id: The ID of the job to advance.
        """
        job = self._jobs.get(job_id)
        if not job:
            return

        while job["status"] == "training" and job["current_step"] < job["steps"]:
            await asyncio.sleep(0.05)
            
            job["current_step"] = min(job["steps"], job["current_step"] + max(1, job["steps"] // 5))
            loss = max(0.1, 1.0 - (job["current_step"] / job["steps"]) + random.uniform(-0.05, 0.05))
            job["loss_curve"].append({"step": job["current_step"], "loss": loss})
            
            try:
                temp_dir = Path(tempfile.gettempdir())
                loss_path = temp_dir / f"loss_{job_id}.json"
                with open(loss_path, "w") as f:
                    json.dump(job["loss_curve"], f)
            except Exception as e:
                logger.error(f"Failed to write loss curve for job {job_id}: {e}", exc_info=True)
            
            if job["current_step"] >= job["steps"]:
                job["status"] = "completed"
                # Register the adapter
                adapter_id = f"lora-{uuid.uuid4().hex[:8]}"
                self._adapters[adapter_id] = LoRAAdapterSpec(
                    adapter_id=adapter_id,
                    name=job["name"],
                    base_model=job["base_model"],
                    rank=job["rank"],
                    alpha=float(job.get("alpha", job["rank"])),
                    trigger_word=job["trigger_word"],
                    checkpoint_path=f"/adapters/{adapter_id}.safetensors",
                    size_mb=float(job["rank"] * 4),
                    is_active=True
                )
                job["adapter_id"] = adapter_id

    def get_training_job(self, job_id: str) -> Optional[dict]:
        """
        Get the current status of a training job.
        
        Args:
            job_id: The ID of the training job.
            
        Returns:
            The job details or None if not found.
        """
        return self._jobs.get(job_id)

    def get_adapter(self, adapter_id: str) -> Optional[LoRAAdapterSpec]:
        """
        Get a specific adapter by ID.
        
        Args:
            adapter_id: The ID of the adapter.
            
        Returns:
            The adapter specification or None if not found.
        """
        return self._adapters.get(adapter_id)

    def delete_adapter(self, adapter_id: str) -> bool:
        """
        Delete a specific adapter by ID.
        
        Args:
            adapter_id: The ID of the adapter to delete.
            
        Returns:
            True if deleted, False otherwise.
        """
        if adapter_id in self._adapters:
            del self._adapters[adapter_id]
            return True
        return False

lora_manager = LoRAManager()
