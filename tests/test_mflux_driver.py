"""mflux is a subprocess dependency, never an in-process import — see the
module docstring on src/drivers/mflux_driver.py for why. These tests mock the
subprocess boundary; none of them may invoke real mflux or spend real GPU time.
"""

import subprocess
import threading
import time
from unittest.mock import MagicMock, patch

import pytest

from src.drivers.mflux_driver import (
    MfluxDriver, MfluxSubprocessError, command_for_alias, mflux_bin_dir,
)


class FakeProc:
    """Stands in for subprocess.Popen: yields fixed stdout lines, then exits
    with a fixed code."""

    def __init__(self, lines, returncode=0):
        self.stdout = iter(lines)
        self._returncode = returncode
        self.killed = False

    def wait(self, timeout=None):
        return self._returncode

    def kill(self):
        self.killed = True


class HangingProc:
    """A process whose stdout never produces a line on its own — models mflux
    wedged mid-generation. `kill()` is what unblocks the read loop, the same
    way killing a real process closes its pipe and ends the blocking read
    with EOF. Used to prove the watchdog timer actually reaches the process,
    not just that a TimeoutExpired exception got caught."""

    def __init__(self):
        self._stop = threading.Event()
        self.killed = False
        self.stdout = self

    def __iter__(self):
        return self

    def __next__(self):
        # Blocks until kill() wakes it, with a safety cap so a broken test
        # cannot hang the suite forever.
        self._stop.wait(timeout=2.0)
        raise StopIteration

    def kill(self):
        self.killed = True
        self._stop.set()

    def wait(self, timeout=None):
        return -9 if self.killed else 0


def _driver(tmp_path):
    bin_dir = tmp_path / "mflux-bin"
    bin_dir.mkdir()
    for name in ("mflux-generate", "mflux-generate-flux2"):
        (bin_dir / name).write_text("#!/bin/sh\n")
        (bin_dir / name).chmod(0o755)
    return MfluxDriver(bin_dir=str(bin_dir))


# --------------------------------------------------------------- executable

def test_command_for_alias_routes_flux2_klein_to_its_own_entry_point():
    """flux2-klein-4b needs mflux-generate-flux2, not mflux-generate — running
    it against plain mflux-generate fails with mflux's own error:
    'FLUX.2 Klein is not supported by mflux-generate. Use mflux-generate-flux2
    instead.' (confirmed against a live mflux 0.19.0 install)."""
    assert command_for_alias("flux2-klein-4b") == "mflux-generate-flux2"
    assert command_for_alias("schnell") == "mflux-generate"
    assert command_for_alias("dev") == "mflux-generate"
    assert command_for_alias("some-future-alias-not-in-the-table") == "mflux-generate"


def test_bin_dir_prefers_env_var(monkeypatch):
    monkeypatch.setenv("PLUTO_MFLUX_BIN", "/opt/custom-mflux/bin")
    assert mflux_bin_dir() == "/opt/custom-mflux/bin"


def test_bin_dir_falls_back_to_config(monkeypatch):
    monkeypatch.delenv("PLUTO_MFLUX_BIN", raising=False)
    assert mflux_bin_dir({"mflux_bin_dir": "/opt/other/bin"}) == "/opt/other/bin"


def test_missing_executable_raises_rather_than_silently_failing(tmp_path):
    driver = MfluxDriver(bin_dir=str(tmp_path / "nowhere"))
    with pytest.raises(MfluxSubprocessError, match="not found"):
        driver.infer(prompt="a cat", model="schnell")


# --------------------------------------------------------- string rejection

def test_infer_rejects_a_string_for_extra_args(tmp_path):
    """The one place a caller could turn a real argv list into per-character
    tokens by accident — list("--low-ram") explodes into ['-','-','l',...].
    This must be rejected the same way src.cli.run_cmd rejects a shell string."""
    driver = _driver(tmp_path)
    with pytest.raises(TypeError, match="not a string"):
        driver.infer(prompt="a cat", model="schnell", extra_args="--low-ram")


# ------------------------------------------------------------- exit status

def test_nonzero_exit_is_surfaced_not_swallowed(tmp_path):
    """This repo's own history: ffmpeg stderr piped to /dev/null while the
    caller reported 'completed' regardless, hiding broken renders for weeks.
    Confirm the bug this test guards against would actually reproduce it:
    with the old shape (ignore returncode, always return status=completed)
    this test fails, because no exception is raised and 'boom' never surfaces."""
    driver = _driver(tmp_path)
    fake = FakeProc(lines=["some setup output\n"], returncode=1)
    with patch("subprocess.Popen", return_value=fake):
        with pytest.raises(MfluxSubprocessError, match="exited 1"):
            driver.infer(prompt="a cat", model="schnell", quantize=4, steps=4)


def test_timeout_kills_the_process_and_raises(tmp_path):
    """The read loop blocks on `for line in proc.stdout`, so the watchdog has
    to actually call kill() to unblock it — a naive `proc.wait(timeout=...)`
    placed after the loop would never fire here, because the loop itself
    never returns on its own. HangingProc only stops once kill() is called,
    so this fails against that naive implementation (it hangs until the
    2s safety cap, then reports "still working" was never interrupted)."""
    driver = _driver(tmp_path)
    fake = HangingProc()
    with patch("subprocess.Popen", return_value=fake):
        with pytest.raises(MfluxSubprocessError, match="timed out"):
            driver.infer(prompt="a cat", model="schnell", timeout=0.05)
    assert fake.killed


# --------------------------------------------------- load/generate split

def test_load_and_generate_time_are_reported_separately(tmp_path):
    """The entire point of this driver: load_seconds and generate_seconds must
    be two different numbers, not one wall-clock figure split arbitrarily.
    Fixed perf_counter() ticks make the split deterministic to assert on."""
    driver = _driver(tmp_path)
    lines = [
        "Loading model...\n",
        "Quantizing...\n",
        "  0%|          | 0/4 [00:00<?, ?it/s]\n",
        " 25%|##5       | 1/4 [00:01<00:03,  1.00s/it]\n",
        " 50%|#####     | 2/4 [00:02<00:02,  1.00s/it]\n",
        " 75%|#######5  | 3/4 [00:03<00:01,  1.00s/it]\n",
        "100%|##########| 4/4 [00:04<00:00,  1.00s/it]\n",
        "Saved image.\n",
    ]
    fake = FakeProc(lines=lines, returncode=0)

    # infer() reads perf_counter() exactly three times regardless of how many
    # progress lines follow the first match: once at process start, once at
    # the first line matching the progress-bar shape, once at process exit.
    ticks = iter([0.0, 2.0, 6.0])

    with patch("subprocess.Popen", return_value=fake), \
         patch("time.perf_counter", side_effect=lambda: next(ticks)):
        result = driver.infer(prompt="a cat", model="schnell", quantize=4, steps=4)

    assert result["status"] == "completed"
    assert result["timing_source"] == "first-progress-line"
    assert result["load_seconds"] == pytest.approx(2.0)
    assert result["generate_seconds"] == pytest.approx(4.0)
    assert result["wall_seconds"] == pytest.approx(6.0)
    # Two distinct phases — this is what "reported separately" means.
    assert result["load_seconds"] != result["generate_seconds"]
    # The two phases must add back up to the whole run, not double-count or drop time.
    assert result["load_seconds"] + result["generate_seconds"] == pytest.approx(result["wall_seconds"])


def test_no_progress_line_reports_unknown_split_rather_than_a_guess(tmp_path):
    """If mflux's output never matches the progress-bar shape this driver looks
    for, it must say the split is unknown — never invent one. This project's
    own rule (registry/measurements) is that an unmeasured number does not get
    to look like a measured one."""
    driver = _driver(tmp_path)
    fake = FakeProc(lines=["Loading model...\n", "Saved image.\n"], returncode=0)
    with patch("subprocess.Popen", return_value=fake):
        result = driver.infer(prompt="a cat", model="schnell")

    assert result["status"] == "completed"
    assert result["load_seconds"] is None
    assert result["generate_seconds"] is None
    assert result["timing_source"] == "no-progress-line-observed"
    assert result["wall_seconds"] is not None


def test_infer_rejects_empty_prompt(tmp_path):
    driver = _driver(tmp_path)
    with pytest.raises(ValueError):
        driver.infer(prompt="   ", model="schnell")


def test_command_uses_flux2_entry_point_for_klein(tmp_path):
    """Model-to-binary routing must actually reach subprocess.Popen, not just
    the lookup table — assert the real argv Popen was called with."""
    driver = _driver(tmp_path)
    fake = FakeProc(lines=["100%|##########| 4/4 [00:01<00:00]\n"], returncode=0)
    captured = {}

    def fake_popen(cmd, **kwargs):
        captured["cmd"] = cmd
        return fake

    with patch("subprocess.Popen", side_effect=fake_popen):
        driver.infer(prompt="a cat", model="flux2-klein-4b", quantize=4, steps=4)

    assert isinstance(captured["cmd"], list)
    assert captured["cmd"][0].endswith("mflux-generate-flux2")
    assert "--quantize" in captured["cmd"]
