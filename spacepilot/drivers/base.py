#!/usr/bin/env python3
"""Base specifications and abstract interfaces for in-process local inference drivers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional


@dataclass
class DriverSpec:
    """Specification and telemetry state for an in-process local inference driver.
    
    Attributes:
        driver_id: Unique identifier for the driver (e.g., 'kokoro-82m-onnx', 'qwen2.5-3b-instruct-gguf').
        task: Primary workload category ('voiceover', 'storyboard', 'video_draft', 'super_resolution').
        backend: Runtime engine ('onnx', 'gguf', 'metal_mps', 'cuda', 'cpu').
        resident_vram_gb: Approximate resident VRAM/RAM footprint in GB when loaded.
        is_loaded: Whether the driver's weights and execution session are currently resident in memory.
        requires_accelerator: Whether the driver cannot run at all without a GPU
            compute runtime. False for anything that executes on CPU — ONNX and
            GGUF both do — so a machine with no accelerator, or with accelerator
            memory nobody could measure, still runs them.
    """
    driver_id: str
    task: str
    backend: str
    resident_vram_gb: float
    is_loaded: bool = False
    requires_accelerator: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Serialize specification to dictionary."""
        return asdict(self)


class InferenceDriver(ABC):
    """Abstract base class for all in-process local execution drivers."""

    def __init__(self, spec: DriverSpec) -> None:
        """Initialize driver with its specification.
        
        Args:
            spec: DriverSpec descriptor containing ID, task, backend, and memory profile.
        """
        self.spec = spec

    @property
    def driver_id(self) -> str:
        """Driver unique identifier."""
        return self.spec.driver_id

    @property
    def task(self) -> str:
        """Workload category."""
        return self.spec.task

    @property
    def backend(self) -> str:
        """Execution backend."""
        return self.spec.backend

    @property
    def resident_vram_gb(self) -> float:
        """Resident memory footprint in GB."""
        return self.spec.resident_vram_gb

    @property
    def requires_accelerator(self) -> bool:
        """Whether this driver needs a GPU compute runtime to run at all."""
        return self.spec.requires_accelerator

    @property
    def is_loaded(self) -> bool:
        """Whether the driver is currently loaded in memory."""
        return self.spec.is_loaded

    @abstractmethod
    def load(self) -> bool:
        """Load model weights and initialize the runtime execution session.
        
        Returns:
            bool: True if loaded successfully, False otherwise.
        """
        pass

    @abstractmethod
    def unload(self) -> bool:
        """Unload model weights and release runtime memory resources.
        
        Returns:
            bool: True if unloaded cleanly, False otherwise.
        """
        pass

    @abstractmethod
    def infer(self, **kwargs: Any) -> Any:
        """Execute in-process inference on the loaded driver.
        
        Args:
            **kwargs: Task-specific inference parameters.
            
        Returns:
            Any: Task-specific inference result.
        """
        pass

    def __repr__(self) -> str:
        return (
            f"<{self.__class__.__name__} id={self.driver_id!r} task={self.task!r} "
            f"backend={self.backend!r} loaded={self.is_loaded}>"
        )
