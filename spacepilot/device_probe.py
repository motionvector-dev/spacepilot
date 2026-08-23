#!/usr/bin/env python3
"""Hardware probe for Pluto / SpacePilot.

Every field is optional. A value that could not be measured is None and is
reported as unknown — never replaced with a plausible default. A fabricated
spec produces a confident, wrong model recommendation that the user has no way
to catch.
"""

from __future__ import annotations

import glob as globlib
import json
import os
import platform
import re
import shutil
import subprocess
from dataclasses import dataclass, field, asdict
from typing import Any, Callable, Dict, List, Optional

GIB = 1024 ** 3

# What a model may actually occupy. The OS, the window server and whatever the
# user already has open need headroom; claiming all of it produces a swap storm.
MEMORY_RESERVE_FRACTION = 0.10
MEMORY_RESERVE_FLOOR_BYTES = 3 * GIB

# Backends a recipe in registry/models/*.yaml can name for accelerated work.
# `cpu` is deliberately absent: of everything in the registry only kokoro (TTS)
# lists cpu among its backends, and no video recipe lists it at all.
ACCELERATED_BACKENDS = ("metal", "cuda", "rocm")

# The floor for calling a machine locally capable. Not a feel-good round
# number: it is the working set of the lightest video recipe the registry
# carries, ltx-video 2b distilled — registry/models/ltx-video.yaml,
# `working_set.value`, read 2026-08-23. A machine that cannot hold that cannot
# run any video model we ship, so it is not "optimal" whatever else is true of
# it. When the registry's floor moves, move this with it. Never adjust it to
# make a particular machine pass.
MIN_USABLE_MEMORY_BYTES = 10_200_547_430

# PCI vendor ids, from the pci.ids database. Used only to name the maker of a
# card found in sysfs — never to infer anything about its capability.
PCI_VENDORS = {
    "0x1002": "AMD",
    "0x10de": "NVIDIA",
    "0x8086": "Intel",
    "0x1af4": "Virtio",
    "0x15ad": "VMware",
}


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
    cpu_cores_physical: Optional[int] = None
    cpu_cores_logical: Optional[int] = None

    gpu_name: Optional[str] = None
    gpu_cores: Optional[int] = None
    backend: Optional[str] = None           # metal | cuda | rocm | cpu
    backend_detail: Optional[str] = None    # "Metal 4" / "sm_89" / None

    # Every display adapter the probe found, whether or not it is usable for
    # compute. A card with no runtime still belongs here: "4 GiB present, no
    # usable compute runtime" is an answer, and silence is not.
    gpus: List[Dict[str, Any]] = field(default_factory=list)
    compute_runtime: Optional[str] = None        # "rocm" | "cuda" | "metal"
    compute_runtime_detail: Optional[str] = None

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
        """Memory a model's weights actually have to fit inside.

        None when no accelerator memory could be measured. System RAM is NOT a
        substitute: it used to be returned here, so a laptop with a 4 GiB
        Radeon the probe never looked for was told it had 15.5 GB of "VRAM".
        Unknown is the honest answer, and every caller already handles it.
        """
        if self.vram_total_bytes:
            return self.vram_total_bytes
        if self.memory_unified:
            return self.memory_total_bytes
        return None


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
    def accelerator_memory_known(self) -> bool:
        return self.accelerator_memory_bytes is not None

    @property
    def vram_total_gb(self) -> float:
        """0.0 means *not measured*, not "zero bytes" — check `unknown` for why."""
        return round((self.accelerator_memory_bytes or 0) / GIB, 2)

    @property
    def vram_usable_gb(self) -> float:
        """0.0 means *not measured*, not "zero bytes" — check `unknown` for why."""
        return round(usable_memory_bytes(self) / GIB, 2)

    @property
    def isa_flags(self) -> Optional[str]:
        return {"metal": "ARM_Neon_MPS", "cuda": "CUDA", "rocm": "ROCm"}.get(self.backend or "")

    @property
    def is_local_capable(self) -> bool:
        """Can this machine actually run the lightest local video recipe?

        Two conditions, both measured, both required:

          * the backend is one the recipes name (ACCELERATED_BACKENDS). A GPU
            with no compute runtime does not count — the probe leaves `backend`
            at "cpu" in that case, which is what "present but unusable" means.
          * usable accelerator memory covers MIN_USABLE_MEMORY_BYTES.

        The old rule was `backend in (...) or ram_total_gb >= 16.0`. That bare
        16.0 came from nowhere, and it meant a 2015 dual-core i5-6200U with no
        usable GPU was one firmware reservation (15.48 GiB reported, not 16.0)
        away from being declared `optimal`. RAM alone can no longer earn that.
        """
        if self.backend not in ACCELERATED_BACKENDS:
            return False
        return usable_memory_bytes(self) >= MIN_USABLE_MEMORY_BYTES

    @property
    def status(self) -> str:
        """partial > optimal > constrained.

        `partial` wins over everything: if any field went unread we do not know
        enough to grade the machine, and saying so is the whole point.
        """
        if self.unknown:
            return "partial"
        return "optimal" if self.is_local_capable else "constrained"

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["accelerator_memory_bytes"] = self.accelerator_memory_bytes
        for name in (
            "os_type", "architecture", "device_name", "ram_total_gb", "ram_free_gb",
            "vram_total_gb", "vram_usable_gb", "isa_flags", "is_local_capable", "status",
            "accelerator_memory_known",
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

    if not apple_silicon and profile.vram_total_bytes is None:
        # Intel Mac: memory is not unified, so system RAM is not the model's
        # working set and must not be reported as though it were.
        profile.unknown.setdefault(
            "vram_total_bytes",
            "this Mac has no unified memory and SPDisplaysDataType reported no "
            "VRAM size, so accelerator memory is unknown — not the machine's RAM",
        )

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


def _probe_nvidia(profile: DeviceProfile, run: Callable[..., Optional[str]] = _run) -> bool:
    out = run([
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
        profile.compute_runtime = "cuda"
        profile.compute_runtime_detail = f"nvidia-smi reports compute {cap}"
        return True
    except Exception as e:
        profile.unknown["nvidia_smi"] = str(e)
        return False


class LinuxSources:
    """Everything the Linux probe reads, in one injectable place.

    The probe runs on machines we do not have — a laptop with a discrete
    Radeon, a headless server, a container with no /sys/class/drm at all. The
    only way to test that it stays honest on those is to point it at a fixture
    tree, so every path is relative to `root` and every command goes through
    `run`.
    """

    def __init__(self, root: str = "/", run: Optional[Callable[..., Optional[str]]] = None):
        self.root = root
        self.run = run or _run

    def path(self, *parts: str) -> str:
        return os.path.join(self.root, *parts)

    def read_text(self, *parts: str) -> Optional[str]:
        try:
            with open(self.path(*parts)) as f:
                return f.read()
        except Exception:
            return None

    def read_stripped(self, *parts: str) -> Optional[str]:
        raw = self.read_text(*parts)
        return raw.strip("\x00 \n\t") if raw is not None else None

    def glob(self, pattern: str) -> List[str]:
        return sorted(globlib.glob(os.path.join(self.root, pattern)))


def _lspci_names(src: LinuxSources) -> Optional[Dict[str, str]]:
    """{"1002:6900": "Topaz XT [Radeon R7 M260/M340/M360]"} from `lspci -nn`.

    None — not {} — when lspci is absent, so the caller can tell "no such tool"
    apart from "tool ran, said nothing about this card".
    """
    out = src.run(["lspci", "-nn"], timeout=6.0)
    if not out:
        return None
    names: Dict[str, str] = {}
    for line in out.splitlines():
        # "01:00.0 Display controller [0380]: AMD/ATI Topaz XT [...] [1002:6900] (rev 83)"
        # The class code [0380] carries no colon, so only the vendor:device id
        # matches; take the last one in case a device name contains another.
        ids = list(re.finditer(r"\[([0-9a-fA-F]{4}):([0-9a-fA-F]{4})\]", line))
        head = re.match(r"^\S+\s+[^\[]*\[[0-9a-fA-F]{4}\]:\s*", line)
        if not ids or not head:
            continue
        name = line[head.end():ids[-1].start()].strip()
        names[f"{ids[-1].group(1).lower()}:{ids[-1].group(2).lower()}"] = name
    return names


def _drm_cards(src: LinuxSources) -> List[str]:
    """/sys/class/drm/cardN, excluding the cardN-HDMI-A-1 connector entries."""
    return [p for p in src.glob("sys/class/drm/card*")
            if re.fullmatch(r"card\d+", os.path.basename(p))]


def _card_driver(src: LinuxSources, card: str) -> Optional[str]:
    uevent = src.read_text(card, "device", "uevent") or ""
    m = re.search(r"^DRIVER=(\S+)", uevent, re.MULTILINE)
    if m:
        return m.group(1)
    try:
        return os.path.basename(os.path.realpath(src.path(card, "device", "driver"))) or None
    except Exception:
        return None


def _detect_linux_gpus(src: LinuxSources, profile: DeviceProfile) -> List[Dict[str, Any]]:
    """Read every DRM card out of sysfs. Absent facts become named unknowns.

    Nothing here is inferred from a model name. VRAM comes from amdgpu's own
    `mem_info_vram_total`; the vendor and device ids come from sysfs; the human
    name comes from lspci or not at all.
    """
    cards = _drm_cards(src)
    if not cards:
        profile.unknown["gpu"] = (
            f"no {src.path('sys/class/drm')}/card* entries; the kernel exposes no "
            "DRM device, so no GPU could be looked for"
        )
        return []

    names = _lspci_names(src)
    gpus: List[Dict[str, Any]] = []
    for card in cards:
        node = os.path.basename(card)
        vendor_id = (src.read_stripped(card, "device", "vendor") or "").lower() or None
        device_id = (src.read_stripped(card, "device", "device") or "").lower() or None
        vendor = PCI_VENDORS.get(vendor_id or "")
        driver = _card_driver(src, card)

        name = None
        if names is not None and vendor_id and device_id:
            name = names.get(f"{vendor_id[2:]}:{device_id[2:]}")
        if not name:
            # Measured, not invented: this is the PCI id, said out loud.
            name = " ".join(filter(None, [vendor, f"device {device_id}" if device_id else None])) or None
            if names is None:
                profile.unknown.setdefault(
                    "gpu_name",
                    "lspci is not installed, so only the PCI vendor:device id could be read; "
                    "the card's marketing name is unknown",
                )
            else:
                profile.unknown.setdefault(
                    "gpu_name",
                    f"lspci lists no entry for {vendor_id}:{device_id}; "
                    "the card's marketing name is unknown",
                )

        vram = None
        vram_source = None
        raw_vram = src.read_stripped(card, "device", "mem_info_vram_total")
        if raw_vram is not None:
            try:
                vram = int(raw_vram)
                vram_source = f"{node}/device/mem_info_vram_total"
            except ValueError:
                profile.unknown[f"vram_{node}"] = (
                    f"{node}/device/mem_info_vram_total held {raw_vram!r}, which is not a byte count"
                )
        else:
            profile.unknown.setdefault(
                f"vram_{node}",
                f"the {driver or 'unknown'} driver exports no mem_info_vram_total for {node}, "
                "so this card's memory size could not be read",
            )

        gpus.append({
            "node": node,
            "vendor": vendor,
            "vendor_id": vendor_id,
            "device_id": device_id,
            "driver": driver,
            "name": name,
            "vram_total_bytes": vram,
            "vram_source": vram_source,
        })
    return gpus


def _linux_compute_runtime(src: LinuxSources, profile: DeviceProfile, gpus: List[Dict[str, Any]]) -> None:
    """Decide whether any detected card has a runtime that can actually reach it.

    Presence of silicon is not capability. A gfx8 Radeon is real, has real
    VRAM, and is years past ROCm support — "4 GiB present, no usable compute
    runtime" is the correct and useful answer, so this reports the card and
    still leaves the backend at cpu.
    """
    amd = [g for g in gpus if g.get("vendor") == "AMD"]
    if not amd:
        return

    product = src.run(["rocm-smi", "--showproductname"], timeout=8.0)
    if product:
        profile.backend = "rocm"
        profile.compute_runtime = "rocm"
        profile.compute_runtime_detail = "rocm-smi reports the device"
        if profile.vram_total_bytes is None:
            profile.unknown.setdefault(
                "vram_total_bytes",
                "rocm-smi is present but no card exported mem_info_vram_total, "
                "so the VRAM size was not read",
            )
        return

    agents = src.run(["rocminfo"], timeout=8.0)
    if agents and "gfx" in agents:
        profile.backend = "rocm"
        profile.compute_runtime = "rocm"
        m = re.search(r"(gfx\d+\w*)", agents)
        profile.compute_runtime_detail = f"rocminfo reports agent {m.group(1)}" if m else "rocminfo reports an agent"
        return

    profile.unknown["compute_runtime"] = (
        "an AMD card was detected but neither rocm-smi nor rocminfo is installed, "
        "so no runtime was found that can reach it; the card is present and not usable "
        "for compute until one is"
    )


def _linux_machine_name(src: LinuxSources, profile: DeviceProfile) -> None:
    """DMI product_name is often the SKU code ("80NT"), not a name anyone types.

    product_version carries the friendly string on Lenovo, and product_family
    on some others. Take the first candidate that reads like a name; if none
    does, say unknown rather than handing the user a part number.
    """
    dmi = "sys/devices/virtual/dmi/id"
    product_name = src.read_stripped(dmi, "product_name")
    profile.machine_model = product_name or profile.machine_model

    def looks_human(v: Optional[str]) -> bool:
        if not v or len(v) < 4:
            return False
        if v.lower() in ("to be filled by o.e.m.", "system product name", "default string", "none"):
            return False
        # A SKU is short, uppercase and unspaced: "80NT", "10M8S0X600".
        return bool(re.search(r"[a-z]", v)) and (" " in v or len(v.split("-")) > 1)

    for value in (
        src.read_stripped(dmi, "product_version"),
        product_name,
        src.read_stripped(dmi, "product_family"),
        src.read_stripped("proc/device-tree/model"),
    ):
        if looks_human(value):
            profile.machine_name = value
            return

    profile.unknown["machine_name"] = (
        f"DMI reports only {product_name!r} for product_name and no friendly "
        "product_version or product_family, so this machine's name is unknown"
    )


def _linux_cpu_cores(src: LinuxSources, profile: DeviceProfile) -> None:
    """Physical cores and threads are different numbers; report both or neither.

    os.cpu_count() counts threads. On a 2-core i5-6200U with SMT that is 4, and
    calling it "4 cores" overstates the machine by exactly a factor of two.
    """
    cpuinfo = src.read_text("proc", "cpuinfo")
    logical = None
    physical = None
    chip = None
    if cpuinfo:
        blocks = [b for b in cpuinfo.split("\n\n") if "processor" in b]
        logical = len(blocks) or None
        pairs = set()
        for b in blocks:
            pid = re.search(r"^physical id\s*:\s*(\d+)", b, re.MULTILINE)
            cid = re.search(r"^core id\s*:\s*(\d+)", b, re.MULTILINE)
            if pid and cid:
                pairs.add((pid.group(1), cid.group(1)))
        physical = len(pairs) or None
        m = re.search(r"^model name\s*:\s*(.+)$", cpuinfo, re.MULTILINE)
        if m:
            chip = m.group(1).strip()

    if logical is None:
        logical = os.cpu_count()
    profile.cpu_cores_logical = logical
    profile.cpu_cores = logical
    profile.cpu_cores_physical = physical
    profile.chip = chip or profile.chip

    if logical is None:
        profile.unknown["cpu_cores"] = "neither /proc/cpuinfo nor os.cpu_count() gave a thread count"
    if physical is None:
        profile.unknown["cpu_cores_physical"] = (
            "/proc/cpuinfo carries no physical id / core id pairs, so physical cores "
            "could not be told apart from threads"
        )
    if not profile.chip:
        profile.unknown["chip"] = "/proc/cpuinfo has no model name line"


def _probe_linux(profile: DeviceProfile, src: Optional[LinuxSources] = None) -> None:
    src = src or LinuxSources()
    profile.os_name = "Linux"
    profile.os_version = platform.release()

    meminfo = src.read_text("proc", "meminfo")
    if meminfo:
        try:
            mem = dict(
                (k.strip(), v.strip()) for k, v in
                (line.split(":", 1) for line in meminfo.splitlines() if ":" in line)
            )
            profile.memory_total_bytes = int(mem["MemTotal"].split()[0]) * 1024
            avail = mem.get("MemAvailable")
            if avail:
                profile.memory_free_bytes = int(avail.split()[0]) * 1024
            else:
                profile.unknown["memory_free_bytes"] = "/proc/meminfo has no MemAvailable line"
        except Exception as e:
            profile.unknown["memory_total_bytes"] = f"/proc/meminfo unparseable: {e}"
    else:
        profile.unknown["memory_total_bytes"] = f"{src.path('proc/meminfo')} could not be read"

    _linux_cpu_cores(src, profile)
    _linux_machine_name(src, profile)

    # NVIDIA first and on its own terms: nvidia-smi answers name, VRAM and
    # compute capability in one call, and its cards need no sysfs archaeology.
    if _probe_nvidia(profile, run=src.run):
        return

    profile.backend = "cpu"
    profile.gpus = _detect_linux_gpus(src, profile)

    with_vram = [g for g in profile.gpus if g.get("vram_total_bytes")]
    if with_vram:
        best = max(with_vram, key=lambda g: g["vram_total_bytes"])
        profile.vram_total_bytes = best["vram_total_bytes"]
        profile.gpu_name = best.get("name") or profile.gpu_name
    elif profile.gpus:
        named = next((g for g in profile.gpus if g.get("name")), None)
        if named:
            profile.gpu_name = named["name"]
        profile.unknown["vram_total_bytes"] = (
            "a GPU was detected but no driver exported its memory size, so the "
            "amount of accelerator memory is unknown — it is NOT this machine's RAM"
        )
    else:
        profile.unknown["vram_total_bytes"] = (
            "no GPU was detected, so there is no accelerator memory to report — "
            "system RAM is not a substitute for it"
        )

    _linux_compute_runtime(src, profile, profile.gpus)

    if profile.backend == "cpu" and profile.gpus and "compute_runtime" not in profile.unknown:
        profile.unknown.setdefault(
            "compute_runtime",
            "a display adapter was detected but no compute runtime (CUDA or ROCm) "
            "was found that can reach it",
        )


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
