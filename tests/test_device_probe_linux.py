#!/usr/bin/env python3
"""The Linux hardware probe, tested against a fixture sysfs tree.

Built from a real reconnaissance run on a Lenovo ideapad 500-15ISK: i5-6200U
(Skylake, 2 cores / 4 threads), 15.48 GiB RAM, Ubuntu 24.04, Intel HD 520
integrated graphics plus a discrete AMD Radeon R7 M360 carrying 4 GiB of its
own VRAM.

`spacepilot doctor` on that machine printed:

    Backend  : CPU
    VRAM     : 12.5GB usable / 15.5GB total (Safety Headroom: 3.0GB)

Every figure on the VRAM line was fiction. The probe never looked for a GPU,
and the number it printed was system RAM wearing a VRAM label. These tests are
mostly negative on purpose: what the probe refuses to claim matters more here
than what it reports.
"""

from __future__ import annotations

import os
from typing import Dict, List, Optional

import pytest

from spacepilot.device_probe import (
    GIB,
    MIN_USABLE_MEMORY_BYTES,
    DeviceProfile,
    LinuxSources,
    _probe_linux,
    usable_memory_bytes,
)

# --- the real machine ------------------------------------------------------

# 15.48 GiB, not 16: the firmware reserves the difference. Half a gigabyte is
# all that stood between this box and the old rule declaring it "optimal".
IDEAPAD_MEMTOTAL_KB = 16_231_648
IDEAPAD_MEMAVAILABLE_KB = 12_004_224

# 4.00 GiB, straight out of amdgpu's mem_info_vram_total.
R7_M360_VRAM_BYTES = 4 * GIB

# PCI ids from the pci.ids database.
AMD_VENDOR = "0x1002"
R7_M360_DEVICE = "0x6900"      # Topaz XT [Radeon R7 M260/M340/M360]
INTEL_VENDOR = "0x8086"
HD_520_DEVICE = "0x1916"       # HD Graphics 520

LSPCI_OUTPUT = (
    "00:02.0 VGA compatible controller [0300]: Intel Corporation "
    "HD Graphics 520 [8086:1916] (rev 07)\n"
    "01:00.0 Display controller [0380]: Advanced Micro Devices, Inc. [AMD/ATI] "
    "Topaz XT [Radeon R7 M260/M340/M360] [1002:6900] (rev 83)\n"
)

CPUINFO_I5_6200U = "\n\n".join(
    "\n".join([
        f"processor\t: {cpu}",
        "vendor_id\t: GenuineIntel",
        "model name\t: Intel(R) Core(TM) i5-6200U CPU @ 2.30GHz",
        f"physical id\t: 0",
        f"core id\t\t: {core}",
        "siblings\t: 4",
        "cpu cores\t: 2",
    ])
    # 2 physical cores, 4 threads: cpu 0/2 on core 0, cpu 1/3 on core 1.
    for cpu, core in ((0, 0), (1, 1), (2, 0), (3, 1))
) + "\n\n"


# --- fixture tree builder --------------------------------------------------


def _write(path: str, text: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(text)


def build_tree(
    root,
    *,
    cards: Optional[List[Dict[str, Optional[str]]]] = None,
    memtotal_kb: int = IDEAPAD_MEMTOTAL_KB,
    memavailable_kb: Optional[int] = IDEAPAD_MEMAVAILABLE_KB,
    cpuinfo: Optional[str] = CPUINFO_I5_6200U,
    dmi: Optional[Dict[str, str]] = None,
) -> str:
    """Write a fake /proc + /sys tree and return its root."""
    root = str(root)
    meminfo = [f"MemTotal:       {memtotal_kb} kB"]
    if memavailable_kb is not None:
        meminfo.append(f"MemAvailable:   {memavailable_kb} kB")
    _write(os.path.join(root, "proc", "meminfo"), "\n".join(meminfo) + "\n")

    if cpuinfo is not None:
        _write(os.path.join(root, "proc", "cpuinfo"), cpuinfo)

    if dmi is None:
        dmi = {
            "product_name": "80NT",
            "product_version": "Lenovo ideapad 500-15ISK",
            "product_family": "IDEAPAD",
            "sys_vendor": "LENOVO",
        }
    for key, value in dmi.items():
        _write(os.path.join(root, "sys/devices/virtual/dmi/id", key), value + "\n")

    for card in cards or []:
        base = os.path.join(root, "sys/class/drm", card["node"], "device")
        _write(os.path.join(base, "vendor"), card["vendor"] + "\n")
        _write(os.path.join(base, "device"), card["device"] + "\n")
        _write(os.path.join(base, "uevent"), f"DRIVER={card['driver']}\nPCI_ID=X\n")
        if card.get("vram") is not None:
            _write(os.path.join(base, "mem_info_vram_total"), str(card["vram"]) + "\n")
        # A connector directory, which is not a card and must not be counted.
        _write(os.path.join(root, "sys/class/drm", card["node"] + "-HDMI-A-1", "status"),
               "disconnected\n")
    return root


IDEAPAD_CARDS = [
    {"node": "card0", "vendor": INTEL_VENDOR, "device": HD_520_DEVICE,
     "driver": "i915", "vram": None},
    {"node": "card1", "vendor": AMD_VENDOR, "device": R7_M360_DEVICE,
     "driver": "amdgpu", "vram": R7_M360_VRAM_BYTES},
]


def fake_run(responses: Optional[Dict[str, str]] = None):
    """A `run` that answers only the commands named, and None for the rest.

    None is what an absent binary looks like, which is the case that matters:
    every one of lspci, rocm-smi, rocminfo and nvidia-smi can be missing.
    """
    responses = responses or {}

    def run(argv, timeout=4.0):
        return responses.get(argv[0])

    return run


def probe(root, run=None) -> DeviceProfile:
    profile = DeviceProfile(arch="x86_64")
    _probe_linux(profile, LinuxSources(root=str(root), run=run or fake_run()))
    return profile


# --- the defect that mattered most -----------------------------------------


def test_no_gpu_at_all_reports_accelerator_memory_as_unknown(tmp_path):
    """Nothing detectable must produce unknown, never a plausible number."""
    p = probe(build_tree(tmp_path, cards=[]))

    assert p.accelerator_memory_bytes is None
    assert p.vram_total_bytes is None
    assert usable_memory_bytes(p) is None
    assert "vram_total_bytes" in p.unknown


def test_accelerator_memory_never_falls_back_to_system_ram(tmp_path):
    """The original defect, stated as an assertion.

    accelerator_memory_bytes returned memory_total_bytes, so usable_memory_bytes
    applied the reserve to system RAM and doctor printed the result as VRAM:
    15.48 GiB total, 12.48 GiB "usable". Both numbers were about RAM.
    """
    p = probe(build_tree(tmp_path, cards=[]))

    assert p.memory_total_bytes == IDEAPAD_MEMTOTAL_KB * 1024
    assert p.ram_total_gb == pytest.approx(15.48, abs=0.01)
    assert p.accelerator_memory_bytes != p.memory_total_bytes
    assert p.accelerator_memory_bytes is None
    assert p.vram_total_gb == 0.0
    assert p.vram_usable_gb == 0.0


def test_unknown_is_never_empty_when_something_went_unread(tmp_path):
    """`status` derives "partial" from `unknown`, so an empty dict disarms it."""
    p = probe(build_tree(tmp_path, cards=[]))

    assert p.unknown, "a probe that found no GPU must record that it found none"
    assert p.status == "partial"


def test_every_unknown_carries_a_reason(tmp_path):
    p = probe(build_tree(tmp_path, cards=IDEAPAD_CARDS))

    for key, reason in p.unknown.items():
        assert isinstance(reason, str) and len(reason) > 20, f"{key} has no real reason"


# --- detection -------------------------------------------------------------


def test_discrete_radeon_is_detected_with_its_real_vram(tmp_path):
    """4 GiB from amdgpu's own mem_info_vram_total, not a fraction of anything."""
    p = probe(build_tree(tmp_path, cards=IDEAPAD_CARDS),
              run=fake_run({"lspci": LSPCI_OUTPUT}))

    assert p.vram_total_bytes == R7_M360_VRAM_BYTES
    assert p.accelerator_memory_bytes == R7_M360_VRAM_BYTES
    assert p.vram_total_gb == 4.0
    assert "R7 M260/M340/M360" in (p.gpu_name or "")

    nodes = {g["node"]: g for g in p.gpus}
    assert set(nodes) == {"card0", "card1"}, "connector dirs must not count as cards"
    assert nodes["card1"]["driver"] == "amdgpu"
    assert nodes["card1"]["vendor"] == "AMD"
    assert nodes["card0"]["driver"] == "i915"
    assert nodes["card0"]["vram_total_bytes"] is None


def test_detected_gpu_with_no_runtime_is_present_and_honestly_unusable(tmp_path):
    """A gfx8 Radeon is real, has real VRAM, and ROCm dropped it years ago.

    "4 GiB present, no usable compute runtime" is the useful answer. Reporting
    the card is not the same as claiming it can run anything.
    """
    p = probe(build_tree(tmp_path, cards=IDEAPAD_CARDS),
              run=fake_run({"lspci": LSPCI_OUTPUT}))

    assert p.gpus, "the card must be reported"
    assert p.vram_total_bytes == R7_M360_VRAM_BYTES
    assert p.backend == "cpu", "no runtime reaches it, so it is not an accelerator"
    assert p.compute_runtime is None
    assert "rocm" in p.unknown["compute_runtime"].lower()
    assert p.is_local_capable is False


def test_rocm_present_promotes_the_backend(tmp_path):
    p = probe(build_tree(tmp_path, cards=IDEAPAD_CARDS),
              run=fake_run({"lspci": LSPCI_OUTPUT,
                            "rocm-smi": "GPU[0]: Card series: Radeon Instinct MI25"}))

    assert p.backend == "rocm"
    assert p.compute_runtime == "rocm"
    assert "compute_runtime" not in p.unknown


def test_lspci_absent_reports_the_pci_ids_and_flags_the_name_unknown(tmp_path):
    """No lspci means no marketing name. The ids are still measured facts."""
    p = probe(build_tree(tmp_path, cards=IDEAPAD_CARDS))

    assert p.gpus[1]["vendor_id"] == AMD_VENDOR
    assert p.gpus[1]["device_id"] == R7_M360_DEVICE
    assert p.gpus[1]["vram_total_bytes"] == R7_M360_VRAM_BYTES
    assert "gpu_name" in p.unknown
    assert "lspci" in p.unknown["gpu_name"]


def test_no_drm_at_all_says_it_could_not_look(tmp_path):
    """A container with no /sys/class/drm: "found nothing" is not "looked"."""
    root = build_tree(tmp_path, cards=[])
    p = probe(root)

    assert p.gpus == []
    assert "drm" in p.unknown["gpu"].lower()


# --- the rest of the reconnaissance table ----------------------------------


def test_machine_name_prefers_the_friendly_string_over_the_sku(tmp_path):
    """DMI product_name is "80NT". Nobody calls the machine that."""
    p = probe(build_tree(tmp_path, cards=[]))

    assert p.machine_name == "Lenovo ideapad 500-15ISK"
    assert p.machine_model == "80NT"
    assert "machine_name" not in p.unknown


def test_machine_name_is_unknown_when_only_a_sku_exists(tmp_path):
    p = probe(build_tree(tmp_path, cards=[], dmi={"product_name": "80NT"}))

    assert p.machine_name is None
    assert "80NT" in p.unknown["machine_name"]


def test_cpu_cores_distinguish_physical_from_logical(tmp_path):
    """2 physical / 4 threads. Calling it "4 cores" doubles the machine."""
    p = probe(build_tree(tmp_path, cards=[]))

    assert p.cpu_cores_physical == 2
    assert p.cpu_cores_logical == 4
    assert p.chip == "Intel(R) Core(TM) i5-6200U CPU @ 2.30GHz"


def test_unparseable_cpuinfo_names_what_it_could_not_read(tmp_path):
    p = probe(build_tree(tmp_path, cards=[], cpuinfo=""))

    assert p.cpu_cores_physical is None
    assert "cpu_cores_physical" in p.unknown
    assert "chip" in p.unknown


def test_missing_memavailable_is_recorded(tmp_path):
    p = probe(build_tree(tmp_path, cards=[], memavailable_kb=None))

    assert p.memory_free_bytes is None
    assert "memory_free_bytes" in p.unknown


# --- status -----------------------------------------------------------------


def test_a_cpu_only_machine_is_never_optimal():
    """The absurd verdict half a gigabyte away from firing.

    At a clean 16.0 GiB this 2015 dual-core with no usable GPU satisfied the
    old `ram_total_gb >= 16.0` and was graded `optimal`.
    """
    p = DeviceProfile(
        os_name="Linux", arch="x86_64", backend="cpu",
        memory_total_bytes=16 * GIB,
        chip="Intel(R) Core(TM) i5-6200U CPU @ 2.30GHz",
    )

    assert p.is_local_capable is False
    assert p.status == "constrained"


def test_local_capability_needs_an_accelerator_and_the_memory_for_it():
    too_small = DeviceProfile(backend="cuda", vram_total_bytes=4 * GIB)
    assert too_small.is_local_capable is False

    big_enough = DeviceProfile(
        backend="cuda",
        vram_total_bytes=int(MIN_USABLE_MEMORY_BYTES * 1.5) + 3 * GIB,
    )
    assert big_enough.is_local_capable is True
    assert big_enough.status == "optimal"


def test_partial_outranks_every_other_status():
    p = DeviceProfile(backend="cuda", vram_total_bytes=48 * GIB)
    assert p.status == "optimal"

    p.unknown["gpu_name"] = "lspci is not installed"
    assert p.status == "partial", "an unread field must not be graded as optimal"
