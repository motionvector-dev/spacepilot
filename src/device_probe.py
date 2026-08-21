#!/usr/bin/env python3
"""Zero-dependency hardware and device capability probe for Pluto / SpacePilot."""

import os
import platform
import subprocess
import sys
from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any

try:
    import psutil
except ImportError:
    psutil = None

try:
    import torch
except ImportError:
    torch = None


@dataclass
class DeviceProfile:
    os_type: str
    architecture: str
    device_name: str
    backend: str  # "metal_mps", "cuda", "cpu", "rocm"
    vram_total_gb: float
    vram_usable_gb: float
    ram_total_gb: float
    ram_free_gb: float
    cuda_capability: Optional[str] = None
    isa_flags: Optional[str] = None
    status: str = "optimal"
    is_local_capable: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _probe_ram() -> tuple[float, float]:
    """Get system RAM total and free in GB."""
    if psutil:
        vm = psutil.virtual_memory()
        return round(vm.total / (1024 ** 3), 2), round(vm.available / (1024 ** 3), 2)
    
    # Fallback to sysctl on macOS
    if platform.system().lower() == "darwin":
        try:
            res = subprocess.check_output(["sysctl", "-n", "hw.memsize"], stderr=subprocess.DEVNULL)
            total = int(res.strip()) / (1024 ** 3)
            return round(total, 2), round(total * 0.5, 2)
        except Exception:
            pass
    return 16.0, 8.0


def _probe_macos() -> DeviceProfile:
    """Probe macOS Apple Silicon / Metal hardware capabilities."""
    ram_total, ram_free = _probe_ram()
    device_name = "Apple Silicon"
    
    try:
        res = subprocess.check_output(["sysctl", "-n", "machdep.cpu.brand_str"], stderr=subprocess.DEVNULL)
        brand = res.decode("utf-8").strip()
        if brand:
            device_name = brand
    except Exception:
        pass

    # Apple Silicon shares unified memory between CPU and GPU
    # Usable VRAM is calculated using 80% safety headroom minus 1.5GB display buffer
    vram_usable = max(0.0, round(ram_total * 0.80 - 1.5, 2))
    
    mps_available = False
    if torch and hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        mps_available = True
    
    backend = "metal_mps" if mps_available else "cpu"
    is_capable = mps_available or (ram_total >= 16.0)

    return DeviceProfile(
        os_type="darwin",
        architecture=platform.machine(),
        device_name=device_name,
        backend=backend,
        vram_total_gb=ram_total,
        vram_usable_gb=vram_usable,
        ram_total_gb=ram_total,
        ram_free_gb=ram_free,
        cuda_capability=None,
        isa_flags="ARM_Neon_MPS",
        status="optimal" if is_capable else "degraded",
        is_local_capable=is_capable
    )


def _probe_cuda() -> Optional[DeviceProfile]:
    """Probe NVIDIA CUDA hardware if present."""
    if not torch or not torch.cuda.is_available():
        return None
    
    try:
        device_idx = torch.cuda.current_device()
        device_name = torch.cuda.get_device_name(device_idx)
        props = torch.cuda.get_device_properties(device_idx)
        vram_total = round(props.total_memory / (1024 ** 3), 2)
        vram_usable = max(0.0, round(vram_total * 0.80 - 1.5, 2))
        
        cap = f"{props.major}.{props.minor}"
        ram_total, ram_free = _probe_ram()

        return DeviceProfile(
            os_type=platform.system().lower(),
            architecture=platform.machine(),
            device_name=device_name,
            backend="cuda",
            vram_total_gb=vram_total,
            vram_usable_gb=vram_usable,
            ram_total_gb=ram_total,
            ram_free_gb=ram_free,
            cuda_capability=cap,
            isa_flags="TensorCores_FP8" if props.major >= 8 else "CUDA_Core",
            status="optimal" if vram_usable >= 6.0 else "constrained",
            is_local_capable=True
        )
    except Exception:
        return None


def _probe_cpu_fallback() -> DeviceProfile:
    """CPU fallback device profile."""
    ram_total, ram_free = _probe_ram()
    vram_usable = max(0.0, round(ram_free * 0.70, 2))
    
    return DeviceProfile(
        os_type=platform.system().lower(),
        architecture=platform.machine(),
        device_name=f"Generic CPU ({platform.processor() or platform.machine()})",
        backend="cpu",
        vram_total_gb=ram_total,
        vram_usable_gb=vram_usable,
        ram_total_gb=ram_total,
        ram_free_gb=ram_free,
        cuda_capability=None,
        isa_flags="AVX_SIMD",
        status="cpu_only",
        is_local_capable=ram_free >= 8.0
    )


def probe_local_device() -> DeviceProfile:
    """Probe host platform and return active DeviceProfile."""
    cuda_profile = _probe_cuda()
    if cuda_profile:
        return cuda_profile
    
    if platform.system().lower() == "darwin":
        return _probe_macos()
    
    return _probe_cpu_fallback()
