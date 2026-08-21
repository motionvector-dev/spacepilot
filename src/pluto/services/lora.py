import json
import logging
import random
import time
import uuid
from dataclasses import dataclass
from typing import Optional, List

logger = logging.getLogger(__name__)

@dataclass
class LoRAAdapterSpec:
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
    def __init__(self):
        self._adapters: dict[str, LoRAAdapterSpec] = {}
        self._jobs: dict[str, dict] = {}

    def list_adapters(self, base_model: Optional[str] = None) -> List[LoRAAdapterSpec]:
        adapters = list(self._adapters.values())
        if base_model:
            adapters = [a for a in adapters if a.base_model == base_model]
        return adapters

    def create_training_job(self, name: str, base_model: str, image_paths: List[str], trigger_word: str, rank: int = 16, steps: int = 500, lr: float = 1e-4) -> dict:
        job_id = f"job-{uuid.uuid4().hex[:8]}"
        self._jobs[job_id] = {
            "job_id": job_id,
            "name": name,
            "base_model": base_model,
            "image_paths": image_paths,
            "trigger_word": trigger_word,
            "rank": rank,
            "steps": steps,
            "lr": lr,
            "status": "training",
            "current_step": 0,
            "loss_curve": []
        }
        
        # Start background task or mock it for now
        # We will just write a mocked loss curve to loss.json progressively
        # For a true mock, this is sufficient to store in the dict and update on fetch
        return self._jobs[job_id]

    def get_training_job(self, job_id: str) -> Optional[dict]:
        job = self._jobs.get(job_id)
        if not job:
            return None
        
        if job["status"] == "training":
            # Mock progress
            job["current_step"] = min(job["steps"], job["current_step"] + max(1, job["steps"] // 10))
            loss = max(0.1, 1.0 - (job["current_step"] / job["steps"]) + random.uniform(-0.05, 0.05))
            job["loss_curve"].append({"step": job["current_step"], "loss": loss})
            
            with open("loss.json", "w") as f:
                json.dump(job["loss_curve"], f)
            
            if job["current_step"] >= job["steps"]:
                job["status"] = "completed"
                # Register the adapter
                adapter_id = f"lora-{uuid.uuid4().hex[:8]}"
                self._adapters[adapter_id] = LoRAAdapterSpec(
                    adapter_id=adapter_id,
                    name=job["name"],
                    base_model=job["base_model"],
                    rank=job["rank"],
                    alpha=float(job["rank"]),
                    trigger_word=job["trigger_word"],
                    checkpoint_path=f"/adapters/{adapter_id}.safetensors",
                    size_mb=float(job["rank"] * 4),
                    is_active=True
                )
                job["adapter_id"] = adapter_id
                
        return job

    def get_adapter(self, adapter_id: str) -> Optional[LoRAAdapterSpec]:
        return self._adapters.get(adapter_id)

    def delete_adapter(self, adapter_id: str) -> bool:
        if adapter_id in self._adapters:
            del self._adapters[adapter_id]
            return True
        return False

lora_manager = LoRAManager()
