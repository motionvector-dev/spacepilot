#!/usr/bin/env python3
"""Unmeasured accelerator memory is unknown, not zero.

Zero means "measured, and there is none". Unknown means "we could not read it".
Collapsing the two produces two different confident lies:

  * `local_workers` refused to run kokoro on a CPU-only Linux box, because a
    budget of 0.00 GB looked like a machine with no room rather than a machine
    whose accelerator memory nobody measured. Kokoro is ONNX on CPU and was
    measured on that exact laptop at 0.89x realtime.
  * `assess()` returned `wont_fit` for all twelve recipes on an Intel MacBook
    Air, including one that then ran fine on it, because a truthy-but-zero
    capacity walked straight past the engine's own "promise nothing" branch.
"""

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(REPO_ROOT))

from spacepilot.device_probe import GIB, DeviceProfile, usable_memory_bytes
from spacepilot.drivers.base import DriverSpec, InferenceDriver
from spacepilot.local_workers import LocalWorkerManager
from spacepilot.services.compatibility import assess


def cpu_only_profile() -> DeviceProfile:
    """The CI runner and the ideapad: RAM measured, accelerator memory not.

    Nothing here is invented — this is what `_probe_linux` produces on a box
    with no GPU it can reach.
    """
    return DeviceProfile(
        os_name="Linux",
        arch="x86_64",
        backend="cpu",
        cpu_cores=8,
        memory_total_bytes=16 * GIB,
        memory_free_bytes=12 * GIB,
        disk_free_bytes=200 * GIB,
        memory_unified=False,
        vram_total_bytes=None,
        unknown={"vram_total_bytes": "no GPU with readable memory was found"},
    )


class _Recipe:
    def __init__(self, recipe_id, working_set_bytes, backends=()):
        self.recipe_id = recipe_id
        self.working_set_bytes = working_set_bytes
        self.backends = list(backends)
        self.working_set_confidence = "measured"
        self.download_bytes = 1 * GIB


class _StubDriver(InferenceDriver):
    def load(self) -> bool:
        self.spec.is_loaded = True
        return True

    def unload(self) -> bool:
        self.spec.is_loaded = False
        return True

    def infer(self, **kwargs):
        return {}


# --- the contract itself ---------------------------------------------------


def test_unmeasured_usable_memory_is_none_not_zero():
    assert usable_memory_bytes(DeviceProfile()) is None
    assert usable_memory_bytes(cpu_only_profile()) is None


def test_measured_capacity_still_yields_a_number():
    """Zero must remain reachable for a machine we did measure."""
    tiny = DeviceProfile(backend="rocm", vram_total_bytes=2 * GIB)
    assert usable_memory_bytes(tiny) == 0  # 2 GiB minus the 3 GiB reserve floor

    real = DeviceProfile(backend="rocm", vram_total_bytes=48 * GIB)
    assert usable_memory_bytes(real) == 48 * GIB - int(48 * GIB * 0.10)


# --- the Air bug: a verdict the engine cannot support ----------------------


def test_unknown_capacity_yields_unknown_verdict():
    """Not `wont_fit`. The engine has no capacity to compare against."""
    profile = cpu_only_profile()
    recipe = _Recipe("kokoro-82m", int(0.4 * GIB))

    v = assess(recipe, profile)

    assert v.verdict == "unknown", f"got {v.verdict!r}: {v.reason}"
    assert v.usable_memory_bytes is None
    assert v.deficit_bytes is None


def test_a_measured_machine_that_is_genuinely_too_small_still_says_wont_fit():
    """The unknown branch must not swallow real answers."""
    small = DeviceProfile(backend="rocm", vram_total_bytes=8 * GIB)
    v = assess(_Recipe("ltx-video-2b", 20 * GIB, backends=["rocm"]), small)

    assert v.verdict == "wont_fit"
    assert v.deficit_bytes and v.deficit_bytes > 0


def test_a_reserve_that_eats_the_whole_card_is_unknown_not_wont_fit():
    """The Air's verdict, stated as an assertion.

    A 2 GiB card minus the 3 GiB reserve floor clamps to 0 "available to
    models". That 0 is arithmetic, not a measurement, and grading a 0.4 GB
    model against it produced `wont_fit` for a model that then ran.
    """
    tiny = DeviceProfile(backend="rocm", vram_total_bytes=2 * GIB)
    assert usable_memory_bytes(tiny) == 0

    v = assess(_Recipe("kokoro-82m", int(0.4 * GIB), backends=["rocm"]), tiny)

    assert v.verdict == "unknown", f"got {v.verdict!r}: {v.reason}"
    assert v.deficit_bytes is None


def test_a_model_larger_than_the_whole_card_is_wont_fit_even_so():
    """Capacity alone answers this one, so the reserve never gets a say."""
    tiny = DeviceProfile(backend="rocm", vram_total_bytes=2 * GIB)
    v = assess(_Recipe("ltx-video-2b", 20 * GIB, backends=["rocm"]), tiny)

    assert v.verdict == "wont_fit"
    assert v.deficit_bytes and v.deficit_bytes > 0


# --- the CI bug: a CPU-capable driver refused for want of VRAM -------------


def test_cpu_capable_driver_runs_on_a_machine_with_no_accelerator(monkeypatch):
    """Kokoro is ONNX on CPU. Weight availability is separate from VRAM."""
    monkeypatch.setattr(
        "spacepilot.local_workers.probe_local_device", cpu_only_profile
    )
    def fake_load(driver):
        driver._session = object()
        driver.spec.is_loaded = True
        return True

    monkeypatch.setattr(
        "spacepilot.drivers.kokoro_driver.KokoroDriver.load", fake_load
    )
    LocalWorkerManager.reset_instance()
    try:
        mgr = LocalWorkerManager.get_instance()
        assert mgr.max_vram_gb is None, "unmeasured budget must not read as 0.0"

        driver = mgr.load_driver("kokoro-82m-onnx")
        assert driver.is_loaded is True
    finally:
        LocalWorkerManager.reset_instance()


def test_accelerator_only_driver_still_fails_with_no_accelerator(monkeypatch):
    """An unknown budget is not a licence to run everything."""
    monkeypatch.setattr(
        "spacepilot.local_workers.probe_local_device", cpu_only_profile
    )
    LocalWorkerManager.reset_instance()
    try:
        mgr = LocalWorkerManager.get_instance()
        spec = DriverSpec(
            driver_id="needs-a-gpu",
            task="video",
            backend="cuda",
            resident_vram_gb=12.0,
            requires_accelerator=True,
        )
        mgr.register_driver_class("needs-a-gpu", lambda **kw: _StubDriver(spec))

        with pytest.raises(MemoryError, match="no accelerator"):
            mgr.load_driver("needs-a-gpu")
    finally:
        LocalWorkerManager.reset_instance()


def test_an_explicit_budget_is_still_enforced_on_a_cpu_only_machine(monkeypatch):
    """Unknown loosens nothing the caller actually told us."""
    monkeypatch.setattr(
        "spacepilot.local_workers.probe_local_device", cpu_only_profile
    )
    LocalWorkerManager.reset_instance()
    try:
        mgr = LocalWorkerManager.get_instance(max_vram_gb=1.0)
        spec = DriverSpec(
            driver_id="hog-4gb", task="hog", backend="cpu", resident_vram_gb=4.0
        )
        mgr.register_driver_class("hog-4gb", lambda **kw: _StubDriver(spec))

        with pytest.raises(MemoryError):
            mgr.load_driver("hog-4gb")
    finally:
        LocalWorkerManager.reset_instance()


def test_is_local_capable_is_false_when_memory_is_unknown():
    assert cpu_only_profile().is_local_capable is False
