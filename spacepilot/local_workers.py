#!/usr/bin/env python3
"""Local Worker Manager for Pluto / SpacePilot In-Process Inference.

Coordinates in-process local driver instances, tracks resident memory / VRAM
headroom, performs LRU model eviction under memory pressure, and dispatches tasks.
"""

import threading
import logging
from typing import Dict, Any, List, Optional, Type

from spacepilot.device_probe import (
    ACCELERATED_BACKENDS,
    DeviceProfile,
    probe_local_device,
    usable_memory_bytes,
)
from spacepilot.drivers.base import InferenceDriver, DriverSpec
from spacepilot.drivers.kokoro_driver import KokoroDriver
from spacepilot.drivers.gguf_driver import GGUFDriver

logger = logging.getLogger("pluto.local_workers")

GIB = 1024 ** 3


def _accelerator_budget_gb(profile: DeviceProfile) -> Optional[float]:
    """How much accelerator memory drivers may share, or None if unknown.

    None is not zero. A machine whose accelerator memory nobody could measure
    imposes no VRAM budget — it also offers no accelerator, so the drivers that
    need one are refused by `requires_accelerator` instead. Treating unknown as
    a 0.00 GB budget is what made a CPU-only Linux runner reject kokoro, an
    ONNX model that had already been measured on that laptop at 0.89x realtime.

    A card with no compute runtime is the same situation from the other side:
    the memory is real, nothing can reach it, so it is no one's budget.
    """
    if profile.backend not in ACCELERATED_BACKENDS:
        return None
    usable = usable_memory_bytes(profile)
    return None if usable is None else round(usable / GIB, 2)


class LocalWorkerManager:
    """Singleton coordinator for in-process local inference drivers."""

    _instance: Optional["LocalWorkerManager"] = None
    _lock = threading.Lock()

    def __new__(cls, *args: Any, **kwargs: Any) -> "LocalWorkerManager":
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(LocalWorkerManager, cls).__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self, max_vram_gb: Optional[float] = None) -> None:
        if getattr(self, "_initialized", False):
            if max_vram_gb is not None:
                self._max_vram_gb = max_vram_gb
            return

        self._manager_lock = threading.RLock()
        self._device_profile: DeviceProfile = probe_local_device()
        self._max_vram_gb: Optional[float] = (
            max_vram_gb if max_vram_gb is not None
            else _accelerator_budget_gb(self._device_profile)
        )

        # Registry of driver classes and instantiated drivers
        self._driver_registry: Dict[str, Type[InferenceDriver]] = {
            "kokoro-82m-onnx": KokoroDriver,
            "kokoro": KokoroDriver,
            "qwen2.5-3b-instruct-gguf": GGUFDriver,
            "deepseek-r1-distill-qwen-7b-gguf": GGUFDriver,
            "gguf": GGUFDriver,
        }

        # Task mapping to default driver_id
        self._task_driver_map: Dict[str, str] = {
            "voiceover": "kokoro-82m-onnx",
            "tts": "kokoro-82m-onnx",
            "storyboard": "qwen2.5-3b-instruct-gguf",
            "narrative": "qwen2.5-3b-instruct-gguf",
            "script": "qwen2.5-3b-instruct-gguf",
        }

        self._active_drivers: Dict[str, InferenceDriver] = {}
        self._access_order: List[str] = []
        self._initialized = True
        limit = (
            "unknown — no VRAM budget enforced" if self._max_vram_gb is None
            else f"{self._max_vram_gb:.1f} GB"
        )
        logger.info(f"LocalWorkerManager initialized with max VRAM limit: {limit}")

    @classmethod
    def get_instance(cls, max_vram_gb: Optional[float] = None) -> "LocalWorkerManager":
        """Return singleton instance of LocalWorkerManager."""
        return cls(max_vram_gb=max_vram_gb)

    @classmethod
    def reset_instance(cls) -> None:
        """Reset singleton instance (primarily for testing)."""
        with cls._lock:
            if cls._instance is not None:
                cls._instance.unload_all()
                cls._instance = None

    @property
    def max_vram_gb(self) -> Optional[float]:
        """Maximum allowable resident VRAM in GB, or None when unmeasured.

        None means no budget is known, so none is enforced. It never means zero.
        """
        return self._max_vram_gb

    @max_vram_gb.setter
    def max_vram_gb(self, val: Optional[float]) -> None:
        with self._manager_lock:
            self._max_vram_gb = None if val is None else max(0.0, float(val))

    @property
    def has_accelerator(self) -> bool:
        """Whether a GPU compute runtime on this machine can actually be reached."""
        return self._device_profile.backend in ACCELERATED_BACKENDS

    @property
    def resident_vram_gb(self) -> float:
        """Total resident VRAM currently consumed by loaded drivers."""
        with self._manager_lock:
            return round(sum(d.resident_vram_gb for d in self._active_drivers.values() if d.is_loaded), 2)

    def register_driver_class(self, driver_id: str, driver_cls: Type[InferenceDriver]) -> None:
        """Register a custom driver class."""
        with self._manager_lock:
            self._driver_registry[driver_id] = driver_cls

    def _resolve_driver_id(self, identifier: str) -> str:
        """Resolve a task name or alias to a canonical driver ID."""
        ident_lower = identifier.lower().strip()
        if ident_lower in self._task_driver_map:
            return self._task_driver_map[ident_lower]
        if ident_lower in self._driver_registry:
            return ident_lower
        # Fallback search
        for key in self._driver_registry:
            if ident_lower in key:
                return key
        return identifier

    def _instantiate_driver(self, driver_id: str) -> InferenceDriver:
        """Create a driver instance if registered."""
        canon_id = self._resolve_driver_id(driver_id)
        if canon_id not in self._driver_registry:
            # Check for generic task
            if canon_id.startswith("kokoro"):
                return KokoroDriver(driver_id=canon_id)
            elif "gguf" in canon_id or "qwen" in canon_id or "deepseek" in canon_id:
                return GGUFDriver(driver_id=canon_id)
            raise ValueError(f"Driver ID '{driver_id}' is not registered.")

        driver_cls = self._driver_registry[canon_id]
        return driver_cls(driver_id=canon_id)

    def _evict_for_headroom(self, required_gb: float) -> None:
        """Evict loaded drivers (LRU) until sufficient VRAM headroom is available.

        No known budget means nothing to make room inside, so nothing is evicted.
        """
        if self._max_vram_gb is None:
            return
        while (self.resident_vram_gb + required_gb > self._max_vram_gb) and self._access_order:
            lru_id = self._access_order.pop(0)
            if lru_id in self._active_drivers:
                driver = self._active_drivers[lru_id]
                logger.info(f"Evicting driver {lru_id} ({driver.resident_vram_gb:.2f} GB) to satisfy memory headroom")
                driver.unload()
                del self._active_drivers[lru_id]

    def load_driver(self, driver_id: str) -> InferenceDriver:
        """Load a driver into memory, evicting other drivers if necessary."""
        with self._manager_lock:
            canon_id = self._resolve_driver_id(driver_id)
            
            if canon_id in self._active_drivers and self._active_drivers[canon_id].is_loaded:
                # Update LRU order
                if canon_id in self._access_order:
                    self._access_order.remove(canon_id)
                self._access_order.append(canon_id)
                return self._active_drivers[canon_id]

            # Create driver if not yet instantiated
            if canon_id not in self._active_drivers:
                self._active_drivers[canon_id] = self._instantiate_driver(canon_id)

            driver = self._active_drivers[canon_id]
            req_vram = driver.resident_vram_gb

            # Two different refusals, kept apart. "This needs a GPU and there
            # isn't one" is a real failure. "Nobody measured the accelerator
            # memory" is not — a CPU-capable driver runs regardless, since it
            # was never going to touch the accelerator.
            if driver.requires_accelerator and not self.has_accelerator:
                raise MemoryError(
                    f"Driver '{canon_id}' needs a GPU compute runtime and this "
                    f"machine has no accelerator "
                    f"(backend: {self._device_profile.backend or 'unknown'})."
                )

            if self._max_vram_gb is not None and req_vram > self._max_vram_gb:
                raise MemoryError(
                    f"Driver '{canon_id}' requires {req_vram:.2f} GB VRAM, which exceeds "
                    f"total usable capacity of {self._max_vram_gb:.2f} GB."
                )

            # Evict if needed
            self._evict_for_headroom(req_vram)

            # Load driver
            success = driver.load()
            if not success:
                raise RuntimeError(f"Failed to load driver '{canon_id}'")

            if canon_id in self._access_order:
                self._access_order.remove(canon_id)
            self._access_order.append(canon_id)
            return driver

    def unload_driver(self, driver_id: str) -> bool:
        """Unload a specific driver from memory."""
        with self._manager_lock:
            canon_id = self._resolve_driver_id(driver_id)
            if canon_id in self._active_drivers:
                driver = self._active_drivers[canon_id]
                driver.unload()
                if canon_id in self._access_order:
                    self._access_order.remove(canon_id)
                del self._active_drivers[canon_id]
                return True
            return False

    def unload_all(self) -> None:
        """Unload all active drivers and free all allocated VRAM."""
        with self._manager_lock:
            for driver in list(self._active_drivers.values()):
                driver.unload()
            self._active_drivers.clear()
            self._access_order.clear()

    def get_driver(self, driver_id_or_task: str) -> InferenceDriver:
        """Get an existing or freshly loaded driver for a task or ID."""
        return self.load_driver(driver_id_or_task)

    def dispatch(self, task: str, **kwargs: Any) -> Any:
        """Convenience dispatch: loads driver matching task and runs inference."""
        driver = self.get_driver(task)
        return driver.infer(**kwargs)

    def get_status(self) -> Dict[str, Any]:
        """Return live telemetry snapshot of local workers and memory."""
        with self._manager_lock:
            loaded = [
                d.spec.to_dict()
                for d in self._active_drivers.values()
                if d.is_loaded
            ]
            return {
                "status": "online",
                "device": self._device_profile.to_dict(),
                "resident_vram_gb": self.resident_vram_gb,
                "usable_vram_gb": self._max_vram_gb,
                "vram_utilization_pct": (
                    None if self._max_vram_gb is None
                    else round((self.resident_vram_gb / max(0.1, self._max_vram_gb)) * 100, 1)
                ),
                "has_accelerator": self.has_accelerator,
                "loaded_drivers_count": len(loaded),
                "loaded_drivers": loaded,
                "available_driver_catalog": list(self._driver_registry.keys()),
                "task_routes": self._task_driver_map,
            }


# Module-level singleton instance
local_worker_manager = LocalWorkerManager.get_instance()
