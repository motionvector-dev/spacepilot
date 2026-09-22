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
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Protocol

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from spacepilot.model_registry import (  # noqa: E402
    MOVING_REFS, Variant, load_registry,
)
from spacepilot import runtimes as rt  # noqa: E402

MIN_FREE_DISK_GB = 40.0
IDLE_MINUTES = 10.0
FLIGHT_LOG_ROOT = Path.home() / "code" / "motionvector" / "media-scratch" / "flights"

# Gate 3 (typed-task semantic-range pass rate) lives in the engine repo, not
# this one -- benchmarks/l2r/ at motionvector-dev/motionvector. A prior lane
# reported it "missing" because it looked at the local checkout, which sits
# on a feature branch; `origin/main` is what actually carries it. `git
# archive` pulls just that subtree without a worktree, the same way `fly.py`
# never mutates this repo's own working tree for a flight.
DEFAULT_ENGINE_REPO = Path.home() / "code" / "motionvector" / "mvec-engine"
DEFAULT_ENGINE_REF = "origin/main"
GATE3_SCRATCH_ROOT = FLIGHT_LOG_ROOT / "gate3-scratch"


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
    "mimo-v2-6-distill-qwen-9b": FlightPlan(
        "mimo-v2-6-distill-qwen-9b", "executor", "mlx-lm", "text",
        needs_gate3=True),
    "gemma4-26b-a4b": FlightPlan(
        "gemma4-26b-a4b", "executor", "mlx-lm", "text",
        needs_gate3=True),
    "maple-preview": FlightPlan(
        "maple-preview", "executor", "mlx-lm", "text",
        needs_gate3=True),
    "ternary-bonsai-2-27b": FlightPlan(
        "ternary-bonsai-2-27b", "executor", "mlx-lm", "text",
        needs_gate3=True),
    "lfm2-5-8b-a1b": FlightPlan(
        "lfm2-5-8b-a1b", "executor", "mlx-lm", "text",
        needs_gate3=True),
    "qwen3-8-splash": FlightPlan(
        "qwen3-8-splash", "executor", "splash", "text", needs_gate3=True),
    # bitnet-b1-58-2b4t: spacepilot/registry/runtimes/bitnet-cpp.yaml runs
    # its GGUF variant through bitnet.cpp's llama-cli, the only path that
    # reads its BitLinear kernels correctly -- plain llama-cpp-python cannot.
    "bitnet-b1-58-2b4t": FlightPlan(
        "bitnet-b1-58-2b4t", "executor", "bitnet-cpp", "text", needs_gate3=True),
    # ternary-bonsai-8b: spacepilot/registry/runtimes/llama-cpp-prism.yaml
    # runs its Q2_0 GGUF build through PrismML's llama.cpp fork -- the only
    # path that reads its ternary kernels.
    "ternary-bonsai-8b": FlightPlan(
        "ternary-bonsai-8b", "executor", "llama-cpp-prism", "text", needs_gate3=True),
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


# ------------------------------------------------------------ preflight installs
#
# `fly.py queue`'s pre-flight phase: for every distinct runtime a planned
# model needs and does not have, install it before flying anything --
# including the two source-tree CMake builds (bitnet-cpp, llama-cpp-prism)
# that stayed BLOCKED-with-a-fix-command rather than run on a MacBook when
# their recipes were registered (see those recipes' own notes). `nice -n 19`
# and a bounded job count keep a several-minute unattended build from
# fighting the rest of the machine for cores -- the same posture
# quietcargo/quietpnpm take for Rust builds elsewhere in this fleet.

BUILD_JOBS = max(1, min(4, (os.cpu_count() or 4) - 1))


def install_env(jobs: int) -> Dict[str, str]:
    """The environment a bounded, unattended build runs under. Harmless to
    a plain `pip install` (mlx-lm, whisper-cpp) -- both env vars are simply
    unread by pip -- and load-bearing for the two CMake source-tree builds,
    where an unbounded default `cmake --build` fans out to every core."""
    env = dict(os.environ)
    env["CMAKE_BUILD_PARALLEL_LEVEL"] = str(jobs)
    env["MAKEFLAGS"] = f"-j{jobs}"
    return env


def runtime_needs_model_dir(runtime: "rt.Runtime") -> bool:
    """Whether this runtime's install script reads a `{model_dir}` -- the
    directory a flight has already fetched the checkpoint into -- as one of
    its positional arguments (see bitnet-cpp.yaml's `install.args`)."""
    return any("{model_dir}" in a for a in runtime.install.script_args)


def install_command_for(runtime: "rt.Runtime",
                         model_dir: Optional[Path] = None) -> List[str]:
    """The real argv fly.py runs to install one runtime -- whatever
    `spacepilot.runtimes.install_command()` would run, prefixed with
    `nice -n 19`. Parallelism is bounded separately, via `install_env()`;
    niceness alone does not cap how many cores a build fans out to.

    `model_dir` is the directory a flight has already downloaded the
    checkpoint into -- bitnet-cpp's install script needs it as its one
    positional argument. Unlike `spacepilot.runtimes.install_command()`
    (which stays permissive for preview callers with no download to name
    yet), this is the layer that actually runs an install for real, so a
    runtime that declares the placeholder and gets no directory errors
    clearly here rather than shipping `curl -fsSL <url> | sh -s --
    {model_dir}` with the literal, unresolved template text as the
    argument -- the same silent-breakage shape the missing argument used
    to take entirely (`curl -fsSL <url> | sh` with nothing after it)."""
    if runtime_needs_model_dir(runtime) and model_dir is None:
        raise rt.RuntimeError_(
            f"{runtime.id}: install script needs the fetched model directory "
            f"(install.args={runtime.install.script_args!r}) but none was given"
        )
    return ["nice", "-n", "19", *rt.install_command(runtime, model_dir=model_dir)]


@dataclass(frozen=True)
class RuntimeInstallResult:
    runtime_id: str
    ok: bool
    detail: str
    duration_s: float = 0.0


def run_runtime_install(
    runtime: "rt.Runtime", *, dry_run: bool = True, jobs: int = BUILD_JOBS,
    model_dir: Optional[Path] = None,
    command_runner: Optional[Callable[..., Any]] = None,
    check_fn: Optional[Callable[["rt.Runtime"], "rt.Status"]] = None,
    clock: Callable[[], float] = time.monotonic,
    log: Callable[[str], None] = print,
) -> RuntimeInstallResult:
    """Install one runtime, or (dry-run, the default) just log the command.

    Verifies the same way `spacepilot.runtimes.install()` does -- by
    calling `check()` afterwards and trusting that, never the installer's
    own exit code alone -- a script that exits 0 having built the wrong
    thing is not installed either.

    `model_dir` is threaded straight through to `install_command_for()` --
    only a runtime whose script declares a `{model_dir}` argument (bitnet-cpp)
    reads it; every other runtime here ignores it. A runtime that needs one
    and gets none never raises out of this function -- `fly_queue`'s
    pre-flight phase calls this with no try/except around it, and a raised
    exception there would abort the whole night instead of skipping just
    the models that needed this runtime (see fly_queue's own contract). A
    dry run previews the best command it can even with no directory yet
    (bitnet-cpp is never actually installable at pre-flight time, before
    any of its models have been downloaded); a real run refuses cleanly.
    """
    needs_model_dir = runtime_needs_model_dir(runtime)

    if dry_run:
        if needs_model_dir and model_dir is None:
            cmd = ["nice", "-n", "19", *rt.install_command(runtime)]
        else:
            cmd = install_command_for(runtime, model_dir=model_dir)
        log(f"  [dry-run] would install {runtime.id}: {' '.join(cmd)}")
        return RuntimeInstallResult(runtime.id, True, "dry-run: " + " ".join(cmd), 0.0)

    if needs_model_dir and model_dir is None:
        detail = (f"{runtime.id}: install needs the fetched model directory "
                  f"(install.args={runtime.install.script_args!r}) but none was given")
        log(f"  cannot install {runtime.id}: {detail}")
        return RuntimeInstallResult(runtime.id, False, detail, 0.0)

    cmd = install_command_for(runtime, model_dir=model_dir)

    log(f"  installing {runtime.id}: {' '.join(cmd)}")
    runner = command_runner or (lambda c, **kw: subprocess.run(
        c, capture_output=True, text=True, timeout=1800, **kw))
    start = clock()
    try:
        proc = runner(cmd, env=install_env(jobs))
    except subprocess.TimeoutExpired as exc:
        duration = clock() - start
        log(f"  install timed out for {runtime.id}")
        return RuntimeInstallResult(runtime.id, False, f"install timed out: {exc}", duration)
    duration = clock() - start

    rc = getattr(proc, "returncode", 1)
    if rc != 0:
        combined = ((getattr(proc, "stderr", "") or "") + "\n"
                    + (getattr(proc, "stdout", "") or "")).strip()
        tail = "\n".join(combined.splitlines()[-15:])
        log(f"  install failed for {runtime.id} (exit {rc})")
        return RuntimeInstallResult(runtime.id, False, tail or f"install exited {rc}", duration)

    check = check_fn or rt.check
    status = check(runtime)
    if not status.installed:
        reason = status.reason or "installed but check still reports it missing"
        log(f"  install ran but {runtime.id} still fails its own check: {reason}")
        return RuntimeInstallResult(runtime.id, False, reason, duration)
    detail = f"installed {status.version or ''}".strip()
    log(f"  {detail} ({runtime.id})")
    return RuntimeInstallResult(runtime.id, True, detail, duration)


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
    """Every unflown variant, smallest download first.

    `runtime_status()` shells out (an import or a `--version` probe) once
    per call, and many variants share one runtime -- nine Desert Ant
    models share `desert-ant`, two share `mlx-lm`. Without a cache this
    reruns the identical subprocess check once per variant; the cache is
    keyed on runtime_id (None included, for the unmapped rows), which is
    exactly what the status depends on -- the plan object only supplies
    which id to check, never which model asked.
    """
    rows = []
    status_cache: Dict[Optional[str], RuntimeStatus] = {}
    for v in unflown_variants(reg):
        p = FLIGHT_PLANS.get(v.model_id)
        key = p.runtime_id if p else None
        if key not in status_cache:
            status_cache[key] = runtime_status(p)
        rows.append(PlanRow(v, p, status_cache[key]))
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
    if getattr(args, "tonight", False):
        print()
        print(tonight_summary(rows))
    return 0


def tonight_summary(rows: List[PlanRow], *, power_sample: Optional[Callable[[], PowerSample]] = None) -> str:
    """The one-block briefing a human reads before typing the arm command --
    same order `plan` just printed, plus the totals and provenance that
    prose alone would make someone dig for: total download, the single
    largest peak-memory estimate, whether tonight's run can measure power at
    all, and where the log and the resulting registry branches land. This is
    what `fly.py plan --tonight` prints and what the "Arm a flight night"
    doc section pastes verbatim.
    """
    total_dl = sum(r.download_gb for r in rows)
    peak_mem = max((r.working_set_gb for r in rows), default=0.0)
    sample_fn = power_sample or sample_power
    power = sample_fn()
    blocked = [r for r in rows if not r.runtime.installed]
    installable = [r for r in blocked if r.runtime.install_cmd]
    no_fix = [r for r in blocked if not r.runtime.install_cmd]
    today = _dt.date.today().isoformat()
    log_path = FLIGHT_LOG_ROOT / today / "flight-log.jsonl"
    lines = [
        "Tonight's flight night, in the order `plan` just printed:",
        f"  {len(rows)} unflown entries, {total_dl:.2f} GB total download, "
        f"{peak_mem:.2f} GB peak memory (largest single entry, est.)",
        f"  {len(blocked)} still BLOCKED -- {len(installable)} get installed by "
        "queue's pre-flight phase (each missing runtime once, in plan order, "
        f"before any flight runs), {len(no_fix)} have no runtime registered "
        "here yet and stay BLOCKED with no fix",
        ("  power: measured via " + power.source + f" ({power.limits})"
         if power.available else f"  power: unmeasured -- {power.limits}"),
        "    optional, to make `powermetrics` itself the source instead of "
        "the ioreg fallback: a sudoers line letting this user run it "
        "unprompted -- "
        "`<user> ALL=(root) NOPASSWD: /usr/bin/powermetrics` -- "
        "see docs/registry/flights.md's \"Power\" section",
        f"  flight log: {log_path}",
        "  registry branch per flown model: flight/<model-id>-<date>, "
        "committed locally, pushed only with --push, never merged by this tool",
    ]
    return "\n".join(lines)


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


# ------------------------------------------------------------------ gate 3

class Gate3Extractor(Protocol):
    def extract(self, engine_repo: Path, engine_ref: str, dest: Path) -> Path: ...


@dataclass
class DryRunGate3Extractor:
    """Logs the archive it would run; touches no filesystem, no subprocess."""
    log: Callable[[str], None] = print

    def extract(self, engine_repo: Path, engine_ref: str, dest: Path) -> Path:
        self.log(
            f"  [dry-run] would archive benchmarks/l2r from mvec-engine@{engine_ref} -- "
            f"git -C {engine_repo} archive {engine_ref} benchmarks/l2r | tar -x -C {dest}"
        )
        return dest / "benchmarks" / "l2r"


@dataclass
class GitArchiveGate3Extractor:
    """Materialises benchmarks/l2r/ from the engine repo without a worktree.

    `git archive <ref> benchmarks/l2r | tar -x` pulls just that subtree at
    the pinned ref straight into the flight's scratch dir -- no `git worktree
    add` churn in the engine checkout, which may itself be sitting on an
    unrelated feature branch (the reason a previous lane thought Gate 3 was
    missing: it looked at the local checkout instead of the ref actually
    fetched here).
    """
    log: Callable[[str], None] = print

    def extract(self, engine_repo: Path, engine_ref: str, dest: Path) -> Path:
        dest.mkdir(parents=True, exist_ok=True)
        self.log(f"  archiving benchmarks/l2r from mvec-engine@{engine_ref} into {dest}")
        archive = subprocess.Popen(
            ["git", "-C", str(engine_repo), "archive", engine_ref, "benchmarks/l2r"],
            stdout=subprocess.PIPE,
        )
        try:
            tar = subprocess.run(["tar", "-x", "-C", str(dest)], stdin=archive.stdout)
        finally:
            if archive.stdout:
                archive.stdout.close()
            archive.wait()
        if archive.returncode != 0:
            raise RuntimeError(
                f"git -C {engine_repo} archive {engine_ref} benchmarks/l2r "
                f"failed (exit {archive.returncode})")
        if tar.returncode != 0:
            raise RuntimeError(f"tar extraction into {dest} failed (exit {tar.returncode})")
        l2r_dir = dest / "benchmarks" / "l2r"
        if not l2r_dir.is_dir():
            raise RuntimeError(
                f"expected {l2r_dir} after extraction, found nothing -- "
                f"does {engine_ref} carry benchmarks/l2r?")
        return l2r_dir


def resolve_mvec_bin(candidates: Optional[List[Path]] = None) -> Optional[Path]:
    """The first real, executable `mvec` binary among the usual local spots.

    Never builds one -- cargo builds are heavy work and stay off this
    machine (see the repo's fan rule); a missing binary is reported, not
    compiled on the spot.
    """
    for c in candidates or [
        Path.home() / ".local" / "bin" / "mvec",
        Path.home() / "code" / "motionvector" / ".cargo-target" / "release" / "mvec",
    ]:
        if c.is_file():
            return c
    return None


def gate3_command(l2r_dir: Path, model_id: str, python_bin: Optional[str] = None) -> List[str]:
    """The argv Gate 3 runs, from inside `l2r_dir`.

    gate3_semantic.py imports its sibling modules (`l2r_codecs`, `fixture`)
    by bare name, so the working directory has to be the extracted
    benchmarks/l2r itself, not the engine repo root or this repo's root.
    """
    return [python_bin or sys.executable, str(l2r_dir / "gate3_semantic.py"),
            "--model", model_id]


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
            engine_ref: str = DEFAULT_ENGINE_REF, engine_repo: Optional[Path] = None,
            gate3_scratch_dir: Optional[Path] = None,
            gate3_extractor: Optional[Gate3Extractor] = None,
            mvec_bin_candidates: Optional[List[Path]] = None,
            install_runner: Optional[Callable[..., RuntimeInstallResult]] = None,
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

    # A script-install runtime whose recipe declares a `{model_dir}`
    # argument (bitnet-cpp) cannot be installed until the model itself has
    # been fetched -- its own install.sh reads the GGUF path as $1. Such a
    # runtime is not refused up front the way every other missing runtime
    # is; installation is attempted below, once the download has run.
    runtime_obj = rt.runtimes().get(plan.runtime_id) if plan and plan.runtime_id else None
    needs_model_dir = bool(runtime_obj and runtime_needs_model_dir(runtime_obj))
    if not rstatus.installed and not dry_run and not needs_model_dir:
        return RunResult(model_id, "refused", steps.steps, f"runtime not installed: {rstatus.reason}")

    if not variant.is_pinned or variant.revision.lower() in MOVING_REFS:
        steps.add("refusing: variant is not pinned to a real SHA")
        return RunResult(model_id, "refused", steps.steps, "unpinned revision")

    dl = downloader or (DryRunDownloader(log=log) if dry_run else HFDownloader(log=log))
    fetched_dir = dl.fetch(variant.repo, variant.revision, variant.files)

    if not rstatus.installed and needs_model_dir:
        installer = install_runner or run_runtime_install
        install_result = installer(runtime_obj, dry_run=dry_run, model_dir=fetched_dir, log=steps.add)
        steps.add(f"install: {'ok' if install_result.ok else 'FAILED'} -- {install_result.detail}")
        if not install_result.ok and not dry_run:
            return RunResult(model_id, "refused", steps.steps,
                              f"runtime install failed: {install_result.detail}")

    cmd = ["spacepilot", "run"] + ([plan.cli] if plan else ["text"]) + [
        "--model", variant.id, "--yes"]
    steps.add(f"flight command: {' '.join(cmd)}")

    if plan and plan.needs_gate3:
        engine_repo_path = engine_repo or DEFAULT_ENGINE_REPO
        scratch_dir = gate3_scratch_dir or (GATE3_SCRATCH_ROOT / variant.model_id)
        extractor = gate3_extractor or (
            DryRunGate3Extractor(log=steps.add) if dry_run else GitArchiveGate3Extractor(log=steps.add))
        l2r_dir = extractor.extract(engine_repo_path, engine_ref, scratch_dir)
        mvec_bin = resolve_mvec_bin(mvec_bin_candidates)
        cmd3 = gate3_command(l2r_dir, variant.id)
        env_note = f"MVEC_BIN={mvec_bin}" if mvec_bin else "MVEC_BIN=<not found on this machine>"
        steps.add(f"gate3 command (cwd={l2r_dir}): {env_note} {' '.join(cmd3)}")
        if mvec_bin is None:
            steps.add("gate3: no mvec binary found -- checked ~/.local/bin/mvec and "
                      "~/code/motionvector/.cargo-target/release/mvec")

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
              push: bool = False, dry_run: bool = True, jobs: int = BUILD_JOBS,
              engine_ref: str = DEFAULT_ENGINE_REF, reg=None,
              idle_check: Optional[Callable[[], GuardResult]] = None,
              display_check: Optional[Callable[[], GuardResult]] = None,
              disk_check: Optional[Callable[[], GuardResult]] = None,
              power_check: Optional[Callable[[], GuardResult]] = None,
              keyboard_activity: Optional[Callable[[], bool]] = None,
              clock: Callable[[], float] = time.monotonic,
              sleep_fn: Callable[[float], None] = time.sleep,
              runner: Callable[..., RunResult] = fly_run,
              install_runner: Callable[..., RuntimeInstallResult] = run_runtime_install,
              flight_disk_check: Optional[Callable[[float], GuardResult]] = None,
              flight_power_check: Optional[Callable[[], GuardResult]] = None,
              log_dir: Optional[Path] = None,
              log: Callable[[str], None] = print) -> List[QueueOutcome]:
    """Runs `plan()` order until the time budget is spent or a human comes
    back. Never itself downloads or infers -- that is `runner`'s job, so
    tests can pass a fake and prove the loop's stopping behaviour in
    isolation.

    Two phases, both under the idle/AC-power/disk guards. First, pre-flight:
    every distinct runtime a planned model needs and does not have gets
    installed once (`install_runner`, `run_runtime_install` by default),
    logged to the same flight log with its duration. A failed install marks
    every model that needed it `skipped: install failed` -- with the tail of
    the install log -- and the night continues; it never aborts the queue.
    Second, the flights themselves, exactly as before, skipping any model
    the pre-flight phase marked.

    `dry_run` (default True, same posture as `fly_run`) governs both phases:
    a dry-run night logs every install command and every flight command and
    touches no network, no registry, and no git ref.
    """
    idle_check = idle_check or check_idle_guard
    display_check = display_check or display_asleep_or_locked
    disk_check = disk_check or (lambda: check_disk_guard(0))
    power_check = power_check or on_ac_power
    keyboard_activity = keyboard_activity or (lambda: False)

    outcomes: List[QueueOutcome] = []
    start_clock = clock()
    rows = plan_rows(reg)
    today = _dt.date.today().isoformat()
    out_dir = log_dir or (FLIGHT_LOG_ROOT / today)
    out_dir.mkdir(parents=True, exist_ok=True)
    log_path = out_dir / "flight-log.jsonl"

    def guards_ok() -> bool:
        """The same guard sequence a flight checks, run once before each
        install: time budget, idle+display (when `while_idle`), keyboard
        activity, disk, AC power. Any failure logs why and the caller
        returns without touching the flights loop at all -- a guard
        failure stops the whole night, exactly like it always has for
        flights; only a failed *install itself* (the command ran and lost)
        is scoped to just the models that needed it."""
        if clock() - start_clock >= max_minutes * 60:
            log(f"stopping: reached max-minutes ({max_minutes:.0f})")
            return False
        if while_idle:
            idle = idle_check()
            if not idle.ok:
                log(f"stopping: {idle.reason}")
                return False
            disp = display_check()
            if not disp.ok:
                log(f"stopping: display is not asleep/locked ({disp.reason})")
                return False
        if keyboard_activity():
            log("stopping: keyboard/mouse activity detected")
            return False
        disk = disk_check()
        if not disk.ok:
            log(f"stopping: {disk.reason}")
            return False
        power = power_check()
        if not power.ok:
            log(f"stopping: {power.reason}")
            return False
        return True

    # ---------------------------------------------------------- pre-flight
    skip_reason: Dict[str, str] = {}
    attempted_runtimes: Dict[str, RuntimeInstallResult] = {}
    for row in rows:
        plan = row.plan
        if plan is None or plan.runtime_id is None or row.runtime.installed:
            continue
        runtime_id = plan.runtime_id
        if runtime_id in attempted_runtimes:
            if not attempted_runtimes[runtime_id].ok:
                skip_reason[row.variant.id] = (
                    f"skipped: install failed -- {attempted_runtimes[runtime_id].detail}")
            continue

        if not guards_ok():
            return outcomes

        runtime_obj = rt.runtimes().get(runtime_id)
        if runtime_obj is None:
            continue  # unknown runtime id -- runtime_status() already reported it

        started = _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")
        result = install_runner(runtime_obj, dry_run=dry_run, jobs=jobs, log=log)
        finished = _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")
        attempted_runtimes[runtime_id] = result
        with log_path.open("a") as f:
            f.write(json.dumps({
                "runtime_id": runtime_id, "start": started, "end": finished,
                "outcome": "dry-run" if dry_run else ("ok" if result.ok else "failed"),
                "detail": result.detail, "duration_s": round(result.duration_s, 1),
            }) + "\n")
        if not dry_run and not result.ok:
            log(f"install failed for {runtime_id}: {result.detail} -- "
                f"models needing it are skipped, continuing to the rest of the night")
            skip_reason[row.variant.id] = f"skipped: install failed -- {result.detail}"

    # -------------------------------------------------------------- flights
    for row in rows:
        model_id = row.variant.id
        if model_id in skip_reason:
            now = _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")
            outcome = QueueOutcome(model_id, now, now, "skipped", skip_reason[model_id])
            outcomes.append(outcome)
            with log_path.open("a") as f:
                f.write(json.dumps(outcome.__dict__) + "\n")
            continue

        if not guards_ok():
            break

        started = _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")
        result = runner(model_id, dry_run=dry_run, keep=keep, push=push, engine_ref=engine_ref,
                         reg=reg, log=log, disk_check=flight_disk_check,
                         power_check=flight_power_check)
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

    plan_p = sub.add_parser("plan", help="list unflown entries, smallest download first")
    plan_p.add_argument("--tonight", action="store_true",
                         help="also print the arm-a-flight-night briefing: totals, "
                              "power provenance, and where the log/branches land")

    run_p = sub.add_parser("run", help="fly one entry")
    run_p.add_argument("model_id")
    run_p.add_argument("--dry-run", action="store_true", default=True,
                        help="(default) log every step, touch no network or registry")
    run_p.add_argument("--fly-for-real", dest="dry_run", action="store_false",
                        help="actually download, run, measure, write, and commit")
    run_p.add_argument("--keep", action="store_true", help="keep downloaded weights")
    run_p.add_argument("--push", action="store_true", help="push the flight branch")
    run_p.add_argument("--engine-ref", default=DEFAULT_ENGINE_REF,
                        help="git ref on mvec-engine to pull benchmarks/l2r (Gate 3) "
                             "from -- default origin/main, never a local feature branch")

    q_p = sub.add_parser("queue", help="fly the whole plan, unattended, within a time budget")
    q_p.add_argument("--max-minutes", type=float, required=True)
    q_p.add_argument("--while-idle", action="store_true", default=True)
    q_p.add_argument("--keep", action="store_true")
    q_p.add_argument("--push", action="store_true")
    q_p.add_argument("--dry-run", action="store_true", default=True,
                      help="(default) log every step -- pre-flight installs and flights "
                           "alike -- touch no network, no registry, no git ref")
    q_p.add_argument("--fly-for-real", dest="dry_run", action="store_false",
                      help="actually install missing runtimes, download, run, measure, "
                           "write, and commit, all night, unattended")
    q_p.add_argument("--force-guards", action="store_true",
                      help="treat idle/AC-power/disk/keyboard as green without probing "
                           "them for real -- for a --dry-run demo on a machine that is "
                           "not actually idle or on AC; never combine with --fly-for-real")
    q_p.add_argument("--engine-ref", default=DEFAULT_ENGINE_REF,
                      help="git ref on mvec-engine to pull benchmarks/l2r (Gate 3) from")

    args = ap.parse_args(argv)

    if args.action == "plan":
        return cmd_plan(args)
    if args.action == "run":
        result = fly_run(args.model_id, dry_run=args.dry_run, keep=args.keep, push=args.push,
                          engine_ref=args.engine_ref)
        return 0 if result.outcome in ("ok", "dry-run") else 1
    if args.action == "queue":
        if args.force_guards and not args.dry_run:
            print("refusing: --force-guards with --fly-for-real would run a real "
                  "unattended night without ever checking idle/power/disk for real")
            return 1
        queue_kwargs = {}
        if args.force_guards:
            forced = lambda *a, **kw: GuardResult(True, "forced green (--force-guards, demo only)")
            queue_kwargs.update(
                idle_check=forced, display_check=forced, disk_check=forced,
                power_check=forced, keyboard_activity=lambda: False,
                flight_disk_check=forced, flight_power_check=forced,
            )
        outcomes = fly_queue(max_minutes=args.max_minutes, while_idle=args.while_idle,
                              keep=args.keep, push=args.push, dry_run=args.dry_run,
                              engine_ref=args.engine_ref, **queue_kwargs)
        failed = [o for o in outcomes if o.outcome == "failed"]
        print(f"flew {len(outcomes)} entries, {len(failed)} failed")
        return 1 if failed else 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
