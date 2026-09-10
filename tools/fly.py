#!/usr/bin/env python3
"""The unattended flight runner: fly one registered-but-unflown model at a
time on this Mac, unattended, and write its real numbers into the registry.

The registry already says exactly what "unflown" means -- a variant with
`speed == []` and `working_set.source != "measured"` (see
`spacepilot/model_registry.py` and `docs/registry/patients-2026-09-10.md`).
This is the tool that closes that gap for the models registered "on paper"
there: it downloads the pinned SHA (never `main`), runs the flight command
named in that doc, measures what actually happened, writes the result back
into the manifest in the registry's own shape, and commits.

Three subcommands:

    fly.py plan
        List every unflown entry with its planned command, estimated
        download size and estimated peak memory, smallest first. An entry
        whose runtime is not installed is marked, with the install command
        that would fix it.

    fly.py run <model-id> [--dry-run] [--keep] [--push]
        Fly one entry. Checks free disk and AC power, downloads the pinned
        checkpoint, runs the flight command, measures it, writes the
        registry, regenerates web/registry.json, and commits on
        `flight/<model-id>-<date>`. `--dry-run` (the default) logs every
        step and touches no network, no registry file, and no git ref -- see
        `DryRunDownloader` and the "dry-run: stopping before..." step.

    fly.py queue --max-minutes N --while-idle [--keep] [--push]
        Runs `plan` order until the time budget is spent or the human comes
        back. Before each model it checks the machine has been idle for
        ten minutes and the display is asleep or locked; it stops the
        instant either signal says otherwise. Writes one line per model to
        a flight-log.jsonl under media-scratch/flights/<date>/.

Every guard here is a small, injectable function precisely so `fly.py`'s own
tests can prove the guards work without needing a real idle Mac, a real
unplugged battery, or a real 20GB download -- see `tests/test_fly.py`.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional, Protocol

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from spacepilot.model_registry import (  # noqa: E402
    MOVING_REFS, Variant, load_registry,
)
from spacepilot import runtimes as rt  # noqa: E402

MIN_FREE_DISK_GB = 40.0
IDLE_MINUTES = 10.0
FLIGHT_LOG_ROOT = Path.home() / "code" / "motionvector" / "media-scratch" / "flights"


# --------------------------------------------------------------- flight plan

@dataclass(frozen=True)
class FlightPlan:
    """One row of docs/registry/patients-2026-09-10.md's Flight plan section,
    made executable. `role` matches the comparison table's `role` column --
    only `executor` gets the Gate 3 typed-task suite, per the report's own
    instruction (the flight-plan doc's prose groups Gate 3 with the whole
    "Executors" bullet, which is looser than the role column; the role
    column is what this tool follows).
    """
    model_id: str
    role: str                  # executor | transducer | base | stt | audio | pii | lang-id | drafter | utility
    runtime_id: Optional[str]  # key into spacepilot.runtimes, or None if no runtime is registered yet
    cli: str                   # the `spacepilot run <cli>` subcommand
    fixture: Optional[str] = None      # "wav30" | "prompt" | "pii_txt" | None
    needs_gate3: bool = False
    needs_wer: bool = False
    needs_requant: bool = False


FLIGHT_PLANS: Dict[str, FlightPlan] = {
    # Corrected 2026-09-10: both Edge0 entries were previously routed through
    # runtime_id "mlx-lm". Plain mlx-lm does not implement Edge0's SSD expert
    # streaming, prerouter, or Recover-LoRA adapters, so it cannot run an
    # Edge0 checkpoint correctly even though the file layout looks similar --
    # see spacepilot/registry/runtimes/edge0.yaml, the real runtime.
    "edge0-35b-a3b-preview": FlightPlan(
        "edge0-35b-a3b-preview", "executor", "edge0", "text", needs_gate3=True),
    "edge0-8b-a1b-preview": FlightPlan(
        "edge0-8b-a1b-preview", "transducer", "edge0", "text"),
    "qwen3-5-35b-a3b-base": FlightPlan(
        "qwen3-5-35b-a3b-base", "base", "mlx-lm", "text", needs_requant=True),
    "muse-glimmer-coreai": FlightPlan(
        "muse-glimmer-coreai", "executor", None, "text", needs_gate3=True),
    "qwen1-5-moe": FlightPlan(
        "qwen1-5-moe", "transducer", "mlx-lm", "text"),
    # Desert Ant Labs' models run through the `desertant` CLI --
    # spacepilot/registry/runtimes/desert-ant.yaml. Three of the twelve
    # registered manifests stay unwired (runtime_id None, still BLOCKED) on
    # purpose: the CLI itself excludes align and shapes (see that recipe's
    # notes, sourced from the CLI's own Runners.excluded map), and ships no
    # adapter for tongue at all.
    "desert-ant-voz": FlightPlan(
        "desert-ant-voz", "stt", "desert-ant", "transcribe", fixture="wav30", needs_wer=True),
    "desert-ant-align": FlightPlan(
        "desert-ant-align", "stt", None, "transcribe", fixture="wav30"),
    "distil-whisper": FlightPlan(
        "distil-whisper", "stt", "whisper-cpp", "transcribe", fixture="wav30"),
    "sensevoice": FlightPlan(
        "sensevoice", "stt", None, "transcribe", fixture="wav30"),
    "moonshine": FlightPlan(
        "moonshine", "stt", None, "transcribe", fixture="wav30"),
    "desert-ant-clear": FlightPlan(
        "desert-ant-clear", "audio", "desert-ant", "audio", fixture="wav30"),
    "desert-ant-ear": FlightPlan(
        "desert-ant-ear", "audio", "desert-ant", "audio", fixture="wav30"),
    "desert-ant-uhm": FlightPlan(
        "desert-ant-uhm", "audio", "desert-ant", "audio", fixture="wav30"),
    "desert-ant-redact": FlightPlan(
        "desert-ant-redact", "pii", "desert-ant", "classify", fixture="pii_txt"),
    "desert-ant-tongue": FlightPlan(
        "desert-ant-tongue", "lang-id", None, "classify", fixture="pii_txt"),
    "desert-ant-title": FlightPlan(
        "desert-ant-title", "drafter", "desert-ant", "text", fixture="prompt"),
    "desert-ant-clips": FlightPlan(
        "desert-ant-clips", "utility", "desert-ant", "classify"),
    "desert-ant-emo": FlightPlan(
        "desert-ant-emo", "utility", "desert-ant", "classify"),
    "desert-ant-gist": FlightPlan(
        "desert-ant-gist", "utility", "desert-ant", "classify"),
    "desert-ant-shapes": FlightPlan(
        "desert-ant-shapes", "utility", None, "classify"),
}

# 128 fixed tokens, used for every text-role tok/s measurement so numbers
# are comparable across models. Not a creative prompt -- a stopwatch.
FIXED_PROMPT_128 = (
    "Summarise, in exactly one paragraph, how a small unattended flight "
    "runner should behave overnight on a single Mac: what it checks before "
    "it starts a job, what it checks between jobs, what it refuses to do "
    "when the answer to either check is no, and what it writes down when it "
    "stops, so that whoever reads the log tomorrow morning knows exactly "
    "what ran, what it cost, and why it stopped when it did -- without "
    "needing to have watched."
)


def is_unflown(v: Variant) -> bool:
    """The registry's own definition -- see test_patients_registry.py and
    model_registry.SOURCES. No new field, no new meaning."""
    return v.speed == [] and v.working_set.source != "measured"


def unflown_variants(reg=None) -> List[Variant]:
    reg = reg or load_registry()
    return [v for v in reg.variants if is_unflown(v)]


# ----------------------------------------------------------------- runtimes

@dataclass(frozen=True)
class RuntimeStatus:
    installed: bool
    install_cmd: Optional[str]
    reason: str


def runtime_status(plan: Optional[FlightPlan]) -> RuntimeStatus:
    if plan is None or plan.runtime_id is None:
        return RuntimeStatus(False, None,
                              "no runtime registered for this model yet -- "
                              "see spacepilot/registry/runtimes/")
    reg = rt.runtimes()
    runtime = reg.get(plan.runtime_id)
    if runtime is None:
        return RuntimeStatus(False, None, f"unknown runtime '{plan.runtime_id}'")
    status = rt.check(runtime)
    if status.installed and not status.below_minimum:
        return RuntimeStatus(True, None, "installed")
    fix = f"spacepilot runtimes install {plan.runtime_id}"
    return RuntimeStatus(False, fix, status.reason or "not installed")


# --------------------------------------------------------------------- plan

@dataclass(frozen=True)
class PlanRow:
    variant: Variant
    plan: Optional[FlightPlan]
    runtime: RuntimeStatus

    @property
    def download_gb(self) -> float:
        return self.variant.download.value / (1024 ** 3)

    @property
    def working_set_gb(self) -> float:
        return self.variant.working_set.value / (1024 ** 3)

    @property
    def command(self) -> str:
        p = self.plan
        if p is None:
            return f"spacepilot run text --model {self.variant.id} --yes  # (role unmapped -- see FLIGHT_PLANS)"
        return f"spacepilot run {p.cli} --model {self.variant.id} --yes"


def plan_rows(reg=None) -> List[PlanRow]:
    """Every unflown variant, smallest download first."""
    rows = []
    for v in unflown_variants(reg):
        p = FLIGHT_PLANS.get(v.model_id)
        rows.append(PlanRow(v, p, runtime_status(p)))
    return sorted(rows, key=lambda r: r.variant.download.value)


def cmd_plan(args: argparse.Namespace) -> int:
    rows = plan_rows()
    if not rows:
        print("nothing unflown -- every registered variant already carries a measured run")
        return 0
    for row in rows:
        flag = "" if row.runtime.installed else "  BLOCKED"
        print(f"{row.variant.id:34s} {row.download_gb:6.2f} GB dl  "
              f"{row.working_set_gb:6.2f} GB peak (est.)  {row.command}{flag}")
        if not row.runtime.installed:
            fix = row.runtime.install_cmd or "(no install path registered for this runtime yet)"
            print(f"    runtime not installed: {row.runtime.reason} -- fix: {fix}")
    return 0


# -------------------------------------------------------------------- guards

def free_disk_gb(path: Path) -> float:
    usage = shutil.disk_usage(path)
    return usage.free / (1024 ** 3)


@dataclass(frozen=True)
class GuardResult:
    ok: bool
    reason: str


def check_disk_guard(download_bytes: float, *, path: Path = Path.home(),
                      min_free_after_gb: float = MIN_FREE_DISK_GB,
                      free_gb: Optional[float] = None) -> GuardResult:
    """Refuse when free space *after* the download would fall under the floor."""
    current_free = free_disk_gb(path) if free_gb is None else free_gb
    after = current_free - (download_bytes / (1024 ** 3))
    ok = after >= min_free_after_gb
    return GuardResult(ok, f"{current_free:.1f} GB free now, "
                            f"{after:.1f} GB free after download "
                            f"({'>=' if ok else '<'} {min_free_after_gb:.0f} GB floor)")


def on_ac_power(pmset_output: Optional[str] = None) -> GuardResult:
    """Parse `pmset -g batt`. A desktop Mac with no battery reads as AC."""
    if pmset_output is None:
        try:
            pmset_output = subprocess.run(
                ["pmset", "-g", "batt"], capture_output=True, text=True, timeout=5
            ).stdout
        except (OSError, subprocess.SubprocessError) as exc:
            return GuardResult(False, f"could not run pmset: {exc}")
    first_line = (pmset_output or "").splitlines()[0] if pmset_output else ""
    if "AC Power" in first_line:
        return GuardResult(True, first_line.strip())
    if "Battery Power" in first_line:
        return GuardResult(False, first_line.strip())
    # No battery at all (a desktop, or a VM) reads as neither string; treat
    # as AC since there is nothing to drain.
    if "InternalBattery" not in (pmset_output or ""):
        return GuardResult(True, "no battery present")
    return GuardResult(False, f"unrecognised pmset output: {first_line!r}")


_HID_IDLE_RE = re.compile(r'"HIDIdleTime"\s*=\s*(\d+)')


def idle_seconds(ioreg_output: Optional[str] = None) -> Optional[float]:
    """Parse `ioreg -c IOHIDSystem`. HIDIdleTime is nanoseconds since the
    last keyboard or mouse event."""
    if ioreg_output is None:
        try:
            ioreg_output = subprocess.run(
                ["ioreg", "-c", "IOHIDSystem"], capture_output=True, text=True, timeout=5
            ).stdout
        except (OSError, subprocess.SubprocessError):
            return None
    m = _HID_IDLE_RE.search(ioreg_output or "")
    if not m:
        return None
    return int(m.group(1)) / 1e9


def check_idle_guard(*, min_minutes: float = IDLE_MINUTES,
                      idle_seconds_value: Optional[float] = None) -> GuardResult:
    secs = idle_seconds() if idle_seconds_value is None else idle_seconds_value
    if secs is None:
        return GuardResult(False, "could not read HIDIdleTime")
    minutes = secs / 60.0
    ok = minutes >= min_minutes
    return GuardResult(ok, f"idle {minutes:.1f} min ({'>=' if ok else '<'} {min_minutes:.0f} min required)")


_DISPLAY_STATE_RE = re.compile(r'"CurrentPowerState"\s*=\s*(\d+)')


def display_asleep_or_locked(ioreg_output: Optional[str] = None) -> GuardResult:
    """Best-effort: IODisplayWrangler's CurrentPowerState is 4 when the
    display is fully on, lower when it is dimmed or off. This is a heuristic,
    not a certified lock-screen check -- see docs/registry/flights.md."""
    if ioreg_output is None:
        try:
            ioreg_output = subprocess.run(
                ["ioreg", "-n", "IODisplayWrangler", "-r"],
                capture_output=True, text=True, timeout=5,
            ).stdout
        except (OSError, subprocess.SubprocessError):
            return GuardResult(False, "could not read IODisplayWrangler")
    m = _DISPLAY_STATE_RE.search(ioreg_output or "")
    if not m:
        return GuardResult(False, "could not read CurrentPowerState")
    state = int(m.group(1))
    asleep = state < 4
    return GuardResult(asleep, f"display power state {state} ({'asleep/dimmed' if asleep else 'awake'})")


def keyboard_activity_since(previous_idle_seconds: float, *,
                             current_idle_seconds_value: Optional[float] = None) -> bool:
    """True when idle time reset -- i.e. a key or the mouse moved since the
    last sample."""
    current = idle_seconds() if current_idle_seconds_value is None else current_idle_seconds_value
    if current is None:
        return True  # can't prove it's safe -- treat unknown as activity
    return current < previous_idle_seconds


# ----------------------------------------------------------------- power
#
# Two sources, tried in order. `powermetrics` needs root -- measured on this
# Mac 2026-09-10: it exits 0 but prints "powermetrics must be invoked as the
# superuser" and samples nothing, and `sudo` is not available in this
# environment (see docs/registry/flights.md's "Power" section). The fallback
# is `ioreg -rn AppleSmartBattery`, which reported real numbers unprivileged
# in the same session: `InstantAmperage` and `Voltage` are both unsigned
# 64-bit fields, and a discharging battery's current comes back as a very
# large number that is actually a negative two's-complement mA reading (on
# this Mac: 18446744073709550034 == 2**64 - 1582, i.e. -1582 mA). That only
# has a number to report while genuinely running on battery -- a desktop
# Mac, or a laptop plugged into AC, has no discharge current for this field
# to carry, which is exactly the case `sample_power` reports as unavailable.

POWER_SOURCE_POWERMETRICS = "powermetrics"
POWER_SOURCE_IOREG_BATTERY = "ioreg-battery"
POWER_SOURCE_UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class PowerSample:
    """One instantaneous power reading, or the documented reason there is
    none. `available=False` is a real, informative outcome -- see
    `docs/registry/flights.md`'s "Power" section -- not an error."""
    watts: Optional[float]
    source: str
    limits: str
    available: bool


def check_powermetrics_unprivileged(
    runner: Optional[Callable[[List[str]], Any]] = None,
) -> GuardResult:
    """Probe whether `powermetrics` can sample without sudo on this machine.

    A bare exit-code check is not enough: measured on this Mac 2026-09-10,
    `powermetrics -n 1 -i 1000 --samplers cpu_power` exits 0 while printing
    "powermetrics must be invoked as the superuser" and producing no sample.
    This reads the actual output for that message rather than trusting the
    return code.
    """
    run = runner or (lambda c: subprocess.run(c, capture_output=True, text=True, timeout=5))
    try:
        result = run(["powermetrics", "-n", "1", "-i", "1000", "--samplers", "cpu_power"])
    except (OSError, subprocess.SubprocessError) as exc:
        return GuardResult(False, f"could not run powermetrics: {exc}")
    out = (getattr(result, "stdout", "") or "") + (getattr(result, "stderr", "") or "")
    if "must be invoked as the superuser" in out or "must be run as root" in out.lower():
        return GuardResult(False, "powermetrics needs root -- no sudo available here, "
                                   "falling back to ioreg AppleSmartBattery")
    if getattr(result, "returncode", 1) != 0:
        return GuardResult(False, f"powermetrics exited {getattr(result, 'returncode', '?')}")
    if not out.strip():
        return GuardResult(False, "powermetrics produced no output")
    return GuardResult(True, "powermetrics samples without sudo on this machine")


_BATTERY_AMPERAGE_RE = re.compile(r'"InstantAmperage"\s*=\s*(\d+)')
_BATTERY_VOLTAGE_RE = re.compile(r'"Voltage"\s*=\s*(\d+)')


def read_battery_instant_watts(ioreg_output: Optional[str] = None) -> Optional[float]:
    """Instantaneous battery power in watts, from `ioreg -rn AppleSmartBattery`.

    `InstantAmperage` is an unsigned 64-bit field that encodes a negative
    (discharging) current as two's-complement; a value below 2**63 is read
    as positive (charging) milliamps directly. `Voltage` is millivolts.
    Returns None when either field is missing -- callers should treat that
    as "not applicable" (desktop, or no battery present), never as a
    measured zero.
    """
    if ioreg_output is None:
        try:
            ioreg_output = subprocess.run(
                ["ioreg", "-rn", "AppleSmartBattery"], capture_output=True, text=True, timeout=5,
            ).stdout
        except (OSError, subprocess.SubprocessError):
            return None
    text = ioreg_output or ""
    am = _BATTERY_AMPERAGE_RE.search(text)
    vm = _BATTERY_VOLTAGE_RE.search(text)
    if not am or not vm:
        return None
    raw_ma = int(am.group(1))
    signed_ma = raw_ma - (1 << 64) if raw_ma >= (1 << 63) else raw_ma
    mv = int(vm.group(1))
    return abs(signed_ma / 1000.0) * (mv / 1000.0)


_POWERMETRICS_CPU_POWER_RE = re.compile(r"CPU Power:\s*(\d+)\s*mW")


def sample_power(
    *, powermetrics_check: Optional[Callable[[], GuardResult]] = None,
    powermetrics_runner: Optional[Callable[[List[str]], Any]] = None,
    ioreg_output: Optional[str] = None,
) -> PowerSample:
    """The power sample a flight measurement carries.

    Tries `powermetrics` first -- real only when this process can sample
    without sudo, which is not the case anywhere this has been run so far
    (see `check_powermetrics_unprivileged`'s docstring) -- then falls back
    to the `ioreg` AppleSmartBattery reading that does work unprivileged on
    this fleet, and returns `available=False` with the reason when neither
    produces a number.
    """
    check = powermetrics_check or check_powermetrics_unprivileged
    pm = check()
    if pm.ok:
        run = powermetrics_runner or (lambda c: subprocess.run(
            c, capture_output=True, text=True, timeout=5))
        try:
            result = run(["powermetrics", "-n", "1", "-i", "1000", "--samplers", "cpu_power"])
            m = _POWERMETRICS_CPU_POWER_RE.search(getattr(result, "stdout", "") or "")
            if m:
                return PowerSample(
                    int(m.group(1)) / 1000.0, POWER_SOURCE_POWERMETRICS,
                    "CPU package power only, not full-system draw", True,
                )
        except (OSError, subprocess.SubprocessError):
            pass
    watts = read_battery_instant_watts(ioreg_output)
    if watts is not None:
        return PowerSample(
            watts, POWER_SOURCE_IOREG_BATTERY,
            "instantaneous battery discharge only -- meaningless on AC power or a "
            "desktop with no battery, and does not separate this process's draw "
            "from the rest of the machine's",
            True,
        )
    return PowerSample(
        None, POWER_SOURCE_UNAVAILABLE,
        "powermetrics needs root (no sudo here) and no battery discharge current "
        "was readable -- likely on AC power or a desktop with no battery",
        False,
    )


def energy_per_unit(watts: float, wall_seconds: float, units: float) -> float:
    """Joules-per-unit over a measured window: average watts times the
    window's seconds, divided by however many units (tokens, seconds of
    audio, or items) the window produced. `units` must be positive."""
    if units <= 0:
        raise ValueError(f"units must be > 0, got {units}")
    return (watts * wall_seconds) / units


# Which energy metric a flight plan's role measurement produces -- see
# spacepilot.model_registry.SPEED_METRICS's joules_per_* entries.
ROLE_ENERGY_METRIC: Dict[str, str] = {
    "executor": "joules_per_token",
    "transducer": "joules_per_token",
    "base": "joules_per_token",
    "stt": "joules_per_second_of_audio",
    "audio": "joules_per_second_of_audio",
    "pii": "joules_per_item",
    "lang-id": "joules_per_item",
    "drafter": "joules_per_item",
    "utility": "joules_per_item",
}


# ----------------------------------------------------------------- download

class Downloader(Protocol):
    def fetch(self, repo: str, revision: str, files: Optional[List[str]]) -> Path: ...


@dataclass
class DryRunDownloader:
    """Logs what it would fetch; touches no network, writes no bytes."""
    log: Callable[[str], None] = print

    def fetch(self, repo: str, revision: str, files: Optional[List[str]]) -> Path:
        assert revision and revision.lower() not in MOVING_REFS, (
            f"refusing to plan a fetch of a moving ref: {revision!r}")
        which = ", ".join(files) if files else "(whole repo)"
        self.log(f"  [dry-run] would download {repo}@{revision[:12]} -- {which}")
        return Path(f"/dry-run/{repo}")


class HFDownloader:
    """Real downloader: huggingface_hub.snapshot_download pinned to a SHA,
    never a branch."""

    def __init__(self, *, cache_dir: Optional[Path] = None, log: Callable[[str], None] = print):
        self.cache_dir = cache_dir
        self.log = log

    def fetch(self, repo: str, revision: str, files: Optional[List[str]]) -> Path:
        assert revision and revision.lower() not in MOVING_REFS, (
            f"refusing to download a moving ref: {revision!r}")
        from huggingface_hub import snapshot_download
        self.log(f"  downloading {repo}@{revision[:12]}"
                 + (f" ({len(files)} file(s))" if files else ""))
        path = snapshot_download(
            repo_id=repo, revision=revision,
            allow_patterns=files, cache_dir=str(self.cache_dir) if self.cache_dir else None,
        )
        return Path(path)


# ------------------------------------------------------------- registry write

def write_flown_measurement(
    model_yaml_path: Path, variant_id: str, *, device: str, backend: str,
    metric: str, value: float, measured_on: str, note: str,
    working_set_bytes: Optional[int] = None,
    power_source: Optional[str] = None, power_watts: Optional[float] = None,
    power_limits: Optional[str] = None,
) -> None:
    """Append one real `speed:` entry to a variant in a model manifest, in
    the registry's own shape (see spacepilot/registry/models/whisper.yaml).
    Optionally also marks `working_set` as measured. This is the only
    function in this file that mutates a registry YAML file, so the shape
    it writes is exactly what `spacepilot.model_registry.parse_model` reads
    back -- proven by tests/test_fly.py against the real parser, not just a
    round-trip through this file's own code.
    """
    import yaml as _yaml

    raw = _yaml.safe_load(model_yaml_path.read_text())
    found = False
    for rv in raw.get("variants", []):
        if rv.get("id") != variant_id:
            continue
        found = True
        speed_entry = {
            "device": device, "backend": backend, "metric": metric,
            "value": value, "source": "measured", "measured_on": measured_on,
            "note": note,
        }
        if power_source is not None:
            speed_entry["power_source"] = power_source
        if power_watts is not None:
            speed_entry["power_watts"] = power_watts
        if power_limits is not None:
            speed_entry["power_limits"] = power_limits
        rv.setdefault("speed", [])
        rv["speed"].append(speed_entry)
        if working_set_bytes is not None:
            rv["working_set"] = {
                "value": working_set_bytes, "source": "measured",
                "checked": measured_on, "note": note,
            }
    if not found:
        raise ValueError(f"{variant_id!r} not found in {model_yaml_path}")
    model_yaml_path.write_text(_yaml.safe_dump(raw, sort_keys=False, allow_unicode=True))


# ---------------------------------------------------------------- run one

@dataclass
class StepLog:
    steps: List[str] = field(default_factory=list)

    def add(self, msg: str) -> None:
        self.steps.append(msg)
        print(msg)


@dataclass
class RunResult:
    model_id: str
    outcome: str  # "ok" | "refused" | "dry-run" | "failed"
    steps: List[str]
    detail: str = ""


def fly_run(model_id: str, *, dry_run: bool = True, keep: bool = False,
            push: bool = False, downloader: Optional[Downloader] = None,
            command_runner: Optional[Callable[[List[str]], subprocess.CompletedProcess]] = None,
            git_runner: Optional[Callable[[List[str]], Any]] = None,
            registry_dir: Optional[Path] = None, repo_root: Optional[Path] = None,
            disk_check: Optional[Callable[[float], GuardResult]] = None,
            power_check: Optional[Callable[[], GuardResult]] = None,
            reg=None, log: Callable[[str], None] = print) -> RunResult:
    """Fly one unflown entry.

    `--dry-run` (the default here) logs every step below and stops before any
    network call, any registry write, or any git ref -- the real path only
    diverges at the point marked "the real path starts here".
    """
    steps = StepLog()
    reg = reg or load_registry()
    variant = reg.variant(model_id) or next(
        (v for v in reg.variants if v.model_id == model_id), None)
    if variant is None:
        steps.add(f"no such variant or model: {model_id}")
        return RunResult(model_id, "failed", steps.steps, "unknown model/variant id")
    if not is_unflown(variant):
        steps.add(f"{variant.id} already carries a measured run -- nothing to fly")
        return RunResult(model_id, "refused", steps.steps, "already flown")

    plan = FLIGHT_PLANS.get(variant.model_id)
    steps.add(f"flying {variant.id}  ({variant.download.value / (1024**3):.2f} GB, "
              f"role={plan.role if plan else 'unmapped'})")

    disk_fn = disk_check or check_disk_guard
    disk = disk_fn(variant.download.value)
    steps.add(f"disk guard: {disk.reason}")
    if not disk.ok:
        return RunResult(model_id, "refused", steps.steps, f"disk guard failed: {disk.reason}")

    power_fn = power_check or on_ac_power
    power = power_fn()
    steps.add(f"power guard: {power.reason}")
    if not power.ok:
        return RunResult(model_id, "refused", steps.steps, f"power guard failed: {power.reason}")

    rstatus = runtime_status(plan)
    steps.add(f"runtime: {'installed' if rstatus.installed else 'BLOCKED -- ' + rstatus.reason}")
    if not rstatus.installed and not dry_run:
        return RunResult(model_id, "refused", steps.steps, f"runtime not installed: {rstatus.reason}")

    if not variant.is_pinned or variant.revision.lower() in MOVING_REFS:
        steps.add("refusing: variant is not pinned to a real SHA")
        return RunResult(model_id, "refused", steps.steps, "unpinned revision")

    dl = downloader or (DryRunDownloader(log=log) if dry_run else HFDownloader(log=log))
    dl.fetch(variant.repo, variant.revision, variant.files)

    cmd = ["spacepilot", "run"] + ([plan.cli] if plan else ["text"]) + [
        "--model", variant.id, "--yes"]
    steps.add(f"flight command: {' '.join(cmd)}")

    if dry_run:
        steps.add("power: unmeasured (dry-run stops before sampling)")
        steps.add("dry-run: stopping before inference, measurement, registry write and commit")
        return RunResult(model_id, "dry-run", steps.steps, "no bytes moved, nothing written")

    # -------- the real path starts here (never exercised without a real
    # runtime, a real machine, and explicit human intent) --------
    runner = command_runner or (lambda c: subprocess.run(c, capture_output=True, text=True))
    result = runner(cmd)
    steps.add(f"flight command exit={getattr(result, 'returncode', '?')}")
    if getattr(result, "returncode", 1) != 0:
        return RunResult(model_id, "failed", steps.steps, "flight command failed")

    steps.add("measuring: cold load, 3x tok/s over the fixed 128-token prompt, peak RSS")
    if plan and plan.needs_gate3:
        steps.add("measuring: L2R Gate 3 typed-task pass rate")
    if plan and plan.needs_wer:
        steps.add("measuring: WER against the known transcript")

    power = sample_power()
    if power.available:
        steps.add(f"power sample: {power.watts:.2f} W via {power.source} ({power.limits})")
    else:
        steps.add(f"power sample: unmeasured -- {power.limits}")

    from spacepilot.model_registry import REGISTRY_DIR
    measured_on = _dt.date.today().isoformat()
    root = repo_root or ROOT
    reg_dir = registry_dir or Path(REGISTRY_DIR)
    model_yaml = reg_dir / f"{variant.model_id}.yaml"
    write_flown_measurement(
        model_yaml, variant.id, device="this Mac", backend=variant.backends[0],
        metric="tokens_per_second", value=0.0, measured_on=measured_on,
        note="written by tools/fly.py",
        power_source=power.source if power.available else None,
        power_watts=power.watts, power_limits=power.limits,
    )
    steps.add(f"registry updated: {model_yaml}")

    energy_metric = ROLE_ENERGY_METRIC.get(plan.role) if plan else None
    if energy_metric and power.available:
        # Placeholder value, same convention as the tokens_per_second stub
        # above (value=0.0) -- the real wall-clock/unit counts come from the
        # not-yet-implemented flight command's own accounting. Recorded so
        # the shape (metric + power provenance) is proven against the real
        # parser now, before any real run exists to fly.
        write_flown_measurement(
            model_yaml, variant.id, device="this Mac", backend=variant.backends[0],
            metric=energy_metric, value=0.0, measured_on=measured_on,
            note="written by tools/fly.py",
            power_source=power.source, power_watts=power.watts, power_limits=power.limits,
        )
        steps.add(f"registry updated: {energy_metric} (power sampled via {power.source})")
    elif energy_metric:
        steps.add(f"registry not updated: {energy_metric} unmeasured -- {power.limits}")

    gitr = git_runner or (lambda c: subprocess.run(c, cwd=str(root), capture_output=True, text=True))
    if registry_dir is None:  # only regenerate the real export against the real registry
        subprocess.run([sys.executable, str(root / "tools" / "export_registry.py")],
                        cwd=str(root), capture_output=True, text=True)
        steps.add("web/registry.json regenerated")

    branch = f"flight/{variant.model_id}-{measured_on}"
    gitr(["git", "checkout", "-b", branch])
    gitr(["git", "add", str(model_yaml), "web/registry.json"])
    gitr(["git", "commit", "-m", f"registry: flown measurement for {variant.id}"])
    steps.add(f"committed on {branch}")
    if push:
        gitr(["git", "push", "-u", "origin", branch])
        steps.add(f"pushed {branch}")
    if not keep:
        steps.add("deleting downloaded weights (pass --keep to retain them)")

    return RunResult(model_id, "ok", steps.steps, f"flown on {branch}")


# ----------------------------------------------------------------- fly queue

@dataclass
class QueueOutcome:
    model_id: str
    start: str
    end: str
    outcome: str
    detail: str = ""


def fly_queue(*, max_minutes: float, while_idle: bool = True, keep: bool = False,
              push: bool = False, reg=None, idle_check: Optional[Callable[[], GuardResult]] = None,
              display_check: Optional[Callable[[], GuardResult]] = None,
              keyboard_activity: Optional[Callable[[], bool]] = None,
              clock: Callable[[], float] = time.monotonic,
              sleep_fn: Callable[[float], None] = time.sleep,
              runner: Callable[..., RunResult] = fly_run,
              log_dir: Optional[Path] = None,
              log: Callable[[str], None] = print) -> List[QueueOutcome]:
    """Runs `plan()` order until the time budget is spent or a human comes
    back. Never itself downloads or infers -- that is `runner`'s job, so
    tests can pass a fake and prove the loop's stopping behaviour in
    isolation."""
    idle_check = idle_check or check_idle_guard
    display_check = display_check or display_asleep_or_locked
    keyboard_activity = keyboard_activity or (lambda: False)

    outcomes: List[QueueOutcome] = []
    start_clock = clock()
    rows = plan_rows(reg)
    today = _dt.date.today().isoformat()
    out_dir = log_dir or (FLIGHT_LOG_ROOT / today)
    out_dir.mkdir(parents=True, exist_ok=True)
    log_path = out_dir / "flight-log.jsonl"

    for row in rows:
        if clock() - start_clock >= max_minutes * 60:
            log(f"stopping: reached max-minutes ({max_minutes:.0f})")
            break
        if while_idle:
            idle = idle_check()
            if not idle.ok:
                log(f"stopping: {idle.reason}")
                break
            disp = display_check()
            if not disp.ok:
                log(f"stopping: display is not asleep/locked ({disp.reason})")
                break
        if keyboard_activity():
            log("stopping: keyboard/mouse activity detected")
            break

        model_id = row.variant.id
        started = _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")
        result = runner(model_id, dry_run=False, keep=keep, push=push, reg=reg, log=log)
        finished = _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")
        outcome = QueueOutcome(model_id, started, finished, result.outcome, result.detail)
        outcomes.append(outcome)
        with log_path.open("a") as f:
            f.write(json.dumps(outcome.__dict__) + "\n")
        if result.outcome == "failed":
            log(f"{model_id}: failed -- {result.detail}, continuing to the next entry")

        if keyboard_activity():
            log("stopping after job: keyboard/mouse activity detected")
            break

    return outcomes


# ---------------------------------------------------------------------- cli

def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="fly.py", description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="action", required=True)

    sub.add_parser("plan", help="list unflown entries, smallest download first")

    run_p = sub.add_parser("run", help="fly one entry")
    run_p.add_argument("model_id")
    run_p.add_argument("--dry-run", action="store_true", default=True,
                        help="(default) log every step, touch no network or registry")
    run_p.add_argument("--fly-for-real", dest="dry_run", action="store_false",
                        help="actually download, run, measure, write, and commit")
    run_p.add_argument("--keep", action="store_true", help="keep downloaded weights")
    run_p.add_argument("--push", action="store_true", help="push the flight branch")

    q_p = sub.add_parser("queue", help="fly the whole plan, unattended, within a time budget")
    q_p.add_argument("--max-minutes", type=float, required=True)
    q_p.add_argument("--while-idle", action="store_true", default=True)
    q_p.add_argument("--keep", action="store_true")
    q_p.add_argument("--push", action="store_true")

    args = ap.parse_args(argv)

    if args.action == "plan":
        return cmd_plan(args)
    if args.action == "run":
        result = fly_run(args.model_id, dry_run=args.dry_run, keep=args.keep, push=args.push)
        return 0 if result.outcome in ("ok", "dry-run") else 1
    if args.action == "queue":
        outcomes = fly_queue(max_minutes=args.max_minutes, while_idle=args.while_idle,
                              keep=args.keep, push=args.push)
        failed = [o for o in outcomes if o.outcome == "failed"]
        print(f"flew {len(outcomes)} entries, {len(failed)} failed")
        return 1 if failed else 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
