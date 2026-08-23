#!/usr/bin/env python3
"""Hardware probe for Pluto / SpacePilot.

Every field is optional. A value that could not be measured is None and is
reported as unknown — never replaced with a plausible default. A fabricated
spec produces a confident, wrong model recommendation that the user has no way
to catch.
"""

from __future__ import annotations

import json
import os
import platform
import re
import shutil
import subprocess
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional

GIB = 1024 ** 3

# What a model may actually occupy. The OS, the window server and whatever the
# user already has open need headroom; claiming all of it produces a swap storm.
MEMORY_RESERVE_FRACTION = 0.10
MEMORY_RESERVE_FLOOR_BYTES = 3 * GIB


def usable_memory_bytes(profile: "DeviceProfile") -> int:
    """How much memory a model may actually occupy.

    Prefer the platform's own answer. Metal reports a recommended max working
    set (78% of RAM on an M1 Max, not the 90% a flat reserve would assume), and
    guessing past it is how you get a confident recommendation that swaps.
    """
    if profile.memory_limit_bytes:
        return profile.memory_limit_bytes
    capacity = profile.accelerator_memory_bytes or 0
    if not capacity:
        return 0
    reserve = max(int(capacity * MEMORY_RESERVE_FRACTION), MEMORY_RESERVE_FLOOR_BYTES)
    return max(0, capacity - reserve)


def _run(argv: List[str], timeout: float = 4.0) -> Optional[str]:
    try:
        out = subprocess.run(
            argv, capture_output=True, timeout=timeout, check=True
        ).stdout.decode("utf-8", "replace").strip()
        return out or None
    except Exception:
        return None


def _sysctl(key: str) -> Optional[str]:
    return _run(["sysctl", "-n", key])


def _sysctl_int(key: str) -> Optional[int]:
    raw = _sysctl(key)
    try:
        return int(raw) if raw is not None else None
    except ValueError:
        return None


@dataclass
class DeviceProfile:
    os_name: Optional[str] = None
    os_version: Optional[str] = None
    arch: Optional[str] = None

    machine_name: Optional[str] = None      # "MacBook Pro"
    machine_model: Optional[str] = None     # "MacBookPro18,4"
    chip: Optional[str] = None              # "Apple M1 Max"

    cpu_cores: Optional[int] = None
    cpu_cores_performance: Optional[int] = None
    cpu_cores_efficiency: Optional[int] = None

    gpu_name: Optional[str] = None
    gpu_cores: Optional[int] = None
    backend: Optional[str] = None           # metal | cuda | rocm | cpu
    backend_detail: Optional[str] = None    # "Metal 4" / "sm_89" / None

    memory_total_bytes: Optional[int] = None
    memory_free_bytes: Optional[int] = None
    memory_unified: bool = False
    vram_total_bytes: Optional[int] = None  # discrete GPUs only

    # The platform's own ceiling on a single allocation, where it reports one.
    memory_limit_bytes: Optional[int] = None
    memory_limit_source: Optional[str] = None   # "metal" | "heuristic"

    disk_free_bytes: Optional[int] = None
    disk_path: Optional[str] = None

    # Fields the probe tried to read and could not, as {field: reason}.
    unknown: Dict[str, str] = field(default_factory=dict)

    @property
    def accelerator_memory_bytes(self) -> Optional[int]:
        """Memory a model's weights actually have to fit inside."""
        if self.vram_total_bytes:
            return self.vram_total_bytes
        if self.memory_unified:
            return self.memory_total_bytes
        return self.memory_total_bytes


    # ---- Names the rest of the codebase still uses. Derived, never invented:
    # anything unmeasured stays 0.0 / None rather than becoming a plausible number.

    @property
    def os_type(self) -> Optional[str]:
        return {"macOS": "darwin", "Linux": "linux"}.get(self.os_name or "", (self.os_name or "").lower()) or None

    @property
    def architecture(self) -> Optional[str]:
        return self.arch

    @property
    def device_name(self) -> Optional[str]:
        return self.gpu_name or self.chip

    @property
    def ram_total_gb(self) -> float:
        return round((self.memory_total_bytes or 0) / GIB, 2)

    @property
    def ram_free_gb(self) -> float:
        return round((self.memory_free_bytes or 0) / GIB, 2)

    @property
    def vram_total_gb(self) -> float:
        return round((self.accelerator_memory_bytes or 0) / GIB, 2)

    @property
    def vram_usable_gb(self) -> float:
        return round(usable_memory_bytes(self) / GIB, 2)

    @property
    def isa_flags(self) -> Optional[str]:
        return {"metal": "ARM_Neon_MPS", "cuda": "CUDA", "rocm": "ROCm"}.get(self.backend or "")

    @property
    def is_local_capable(self) -> bool:
        return self.backend in ("metal", "cuda", "rocm") or self.ram_total_gb >= 16.0

    @property
    def status(self) -> str:
        if self.unknown:
            return "partial"
        return "optimal" if self.is_local_capable else "constrained"

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["accelerator_memory_bytes"] = self.accelerator_memory_bytes
        for name in (
            "os_type", "architecture", "device_name", "ram_total_gb", "ram_free_gb",
            "vram_total_gb", "vram_usable_gb", "isa_flags", "is_local_capable", "status",
        ):
            d[name] = getattr(self, name)
        return d


def _probe_disk(profile: DeviceProfile) -> None:
    target = os.environ.get("SPACEPILOT_MODELS_DIR") or os.path.expanduser("~/.spacepilot/models")
    probe_at = target
    while probe_at and not os.path.exists(probe_at):
        parent = os.path.dirname(probe_at)
        if parent == probe_at:
            break
        probe_at = parent
    try:
        profile.disk_free_bytes = shutil.disk_usage(probe_at).free
        profile.disk_path = target
    except Exception as e:
        profile.unknown["disk_free_bytes"] = str(e)


def _probe_darwin(profile: DeviceProfile) -> None:
    profile.os_name = "macOS"
    profile.os_version = _run(["sw_vers", "-productVersion"])
    if not profile.os_version:
        profile.unknown["os_version"] = "sw_vers unavailable"

    profile.chip = _sysctl("machdep.cpu.brand_string")
    profile.machine_model = _sysctl("hw.model")

    hw = _run(["system_profiler", "SPHardwareDataType", "-json"], timeout=12.0)
    if hw:
        try:
            item = json.loads(hw)["SPHardwareDataType"][0]
            profile.machine_name = item.get("machine_name")
            profile.chip = item.get("chip_type") or profile.chip
            profile.machine_model = item.get("machine_model") or profile.machine_model
            # "proc 10:8:2:0" -> total, performance, efficiency
            m = re.match(r"proc\s+(\d+):(\d+):(\d+)", item.get("number_processors", "") or "")
            if m:
                profile.cpu_cores = int(m.group(1))
                profile.cpu_cores_performance = int(m.group(2))
                profile.cpu_cores_efficiency = int(m.group(3))
        except Exception as e:
            profile.unknown["system_profiler"] = str(e)
    else:
        profile.unknown["system_profiler"] = "SPHardwareDataType returned nothing"

    if profile.cpu_cores is None:
        profile.cpu_cores = _sysctl_int("hw.ncpu")
        profile.cpu_cores_performance = _sysctl_int("hw.perflevel0.logicalcpu")
        profile.cpu_cores_efficiency = _sysctl_int("hw.perflevel1.logicalcpu")

    profile.memory_total_bytes = _sysctl_int("hw.memsize")
    if profile.memory_total_bytes is None:
        profile.unknown["memory_total_bytes"] = "hw.memsize unreadable"

    profile.memory_free_bytes = _darwin_free_memory()
    if profile.memory_free_bytes is None:
        profile.unknown["memory_free_bytes"] = "vm_stat unreadable"

    apple_silicon = (profile.arch or "").startswith("arm")
    profile.memory_unified = apple_silicon

    gpu = _run(["system_profiler", "SPDisplaysDataType", "-json"], timeout=12.0)
    if gpu:
        try:
            item = json.loads(gpu)["SPDisplaysDataType"][0]
            profile.gpu_name = item.get("sppci_model") or item.get("_name")
            fam = item.get("spdisplays_mtlgpufamilysupport")
            if fam:
                profile.backend_detail = fam.replace("spdisplays_metal", "Metal ")
            vram = item.get("spdisplays_vram") or item.get("_spdisplays_vram")
            if vram and not apple_silicon:
                mv = re.match(r"(\d+)\s*(MB|GB)", vram)
                if mv:
                    n = int(mv.group(1))
                    profile.vram_total_bytes = n * (GIB if mv.group(2) == "GB" else 1024 ** 2)
        except Exception as e:
            profile.unknown["gpu"] = str(e)
    else:
        profile.unknown["gpu"] = "SPDisplaysDataType returned nothing"

    cores = _run(["ioreg", "-rd1", "-c", "AGXAccelerator"], timeout=8.0)
    if cores:
        m = re.search(r'"gpu-core-count"\s*=\s*(\d+)', cores)
        if m:
            profile.gpu_cores = int(m.group(1))

    profile.backend = "metal" if profile.gpu_name else "cpu"

    if profile.backend == "metal":
        try:
            import torch
            if torch.backends.mps.is_available():
                profile.memory_limit_bytes = int(torch.mps.recommended_max_memory())
                profile.memory_limit_source = "metal"
        except Exception:
            pass  # torch absent or too old; the reserve heuristic covers it


def _darwin_free_memory() -> Optional[int]:
    """Free + inactive + speculative pages, which is what a new allocation can take."""
    out = _run(["vm_stat"])
    if not out:
        return None
    try:
        page = 4096
        head = re.search(r"page size of (\d+) bytes", out)
        if head:
            page = int(head.group(1))
        counts = dict(re.findall(r"^(.*?):\s+(\d+)\.$", out, re.MULTILINE))
        pages = 0
        for key in ("Pages free", "Pages inactive", "Pages speculative", "Pages purgeable"):
            pages += int(counts.get(key, 0))
        return pages * page
    except Exception:
        return None


def _probe_nvidia(profile: DeviceProfile) -> bool:
    out = _run([
        "nvidia-smi",
        "--query-gpu=name,memory.total,memory.free,compute_cap",
        "--format=csv,noheader,nounits",
    ], timeout=8.0)
    if not out:
        return False
    try:
        name, total_mib, _free_mib, cap = [c.strip() for c in out.splitlines()[0].split(",")]
        profile.gpu_name = name
        profile.vram_total_bytes = int(float(total_mib)) * 1024 ** 2
        profile.backend = "cuda"
        profile.backend_detail = f"compute {cap}"
        return True
    except Exception as e:
        profile.unknown["nvidia_smi"] = str(e)
        return False


def _probe_linux(profile: DeviceProfile) -> None:
    profile.os_name = "Linux"
    profile.os_version = platform.release()

    try:
        with open("/proc/meminfo") as f:
            mem = dict(
                (k.strip(), v.strip()) for k, v in
                (line.split(":", 1) for line in f if ":" in line)
            )
        total_kb = int(mem["MemTotal"].split()[0])
        profile.memory_total_bytes = total_kb * 1024
        avail = mem.get("MemAvailable")
        if avail:
            profile.memory_free_bytes = int(avail.split()[0]) * 1024
    except Exception as e:
        profile.unknown["memory_total_bytes"] = str(e)

    profile.cpu_cores = os.cpu_count()

    for path in ("/sys/devices/virtual/dmi/id/product_name", "/proc/device-tree/model"):
        try:
            with open(path) as f:
                profile.machine_name = f.read().strip("\x00 \n")
                break
        except Exception:
            continue

    try:
        with open("/proc/cpuinfo") as f:
            for line in f:
                if line.startswith("model name"):
                    profile.chip = line.split(":", 1)[1].strip()
                    break
    except Exception:
        pass

    if not _probe_nvidia(profile):
        if _run(["rocm-smi", "--showproductname"], timeout=8.0):
            profile.backend = "rocm"
            profile.unknown["vram_total_bytes"] = "rocm-smi present, VRAM not parsed"
        else:
            profile.backend = "cpu"


def probe_local_device() -> DeviceProfile:
    profile = DeviceProfile(arch=platform.machine())
    system = platform.system().lower()

    try:
        if system == "darwin":
            _probe_darwin(profile)
        elif system == "linux":
            _probe_linux(profile)
        else:
            profile.os_name = platform.system()
            profile.os_version = platform.release()
            profile.cpu_cores = os.cpu_count()
            if not _probe_nvidia(profile):
                profile.backend = "cpu"
            profile.unknown["memory_total_bytes"] = f"no probe for {system}"
    except Exception as e:
        profile.unknown["probe"] = str(e)

    _probe_disk(profile)
    if profile.memory_limit_bytes is None and profile.accelerator_memory_bytes:
        profile.memory_limit_bytes = usable_memory_bytes(profile)
        profile.memory_limit_source = "heuristic"
    return profile


if __name__ == "__main__":
    print(json.dumps(probe_local_device().to_dict(), indent=2))
