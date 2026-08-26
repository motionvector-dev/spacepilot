"""Overnight measurement sweeps: a declarative grid, run unattended.

This Mac is idle roughly 8 hours a day. A sweep spec (registry/sweeps/*.yaml)
declares a grid of knobs — resolution, quantisation, steps — for one model
variant; `run_sweep` walks the grid, one real generation per cell, and writes
each result through `spacepilot.pluto.measurements`. The point is a real
quality-and-cost curve for the registry, not a demo: every number that lands
is either `status: ok` (a real speed sample) or `status: failed` (a real
boundary — this is where this machine stops), never a guess.

Everything here is designed to be interrupted. The machine going busy, the
process being killed, a job OOMing — none of those should lose more than the
one job in flight, and none of them should leave the Mac unable to sleep
again. See `run_sweep`'s docstring for the shape of that contract.
"""

from __future__ import annotations

import datetime as _dt
import itertools
import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import yaml

from spacepilot.paths import shipped_dir, writable_dir
from spacepilot.pluto import measurements as ms
from spacepilot.pluto import registry

SCHEMA_VERSION = 1

# Specs are curated content and ship with the release; runs are produced here
# and go wherever this machine's records go (spacepilot.paths).
SPECS_DIR = shipped_dir("sweeps")
RUNS_DIR = writable_dir("sweeps") / "runs"

# Knobs that define a distinct job for resume purposes. Seed and prompt are
# fixed per spec (part of what makes the sweep reproducible), not part of the
# grid, so they are not needed to tell two jobs apart — but resolution,
# quantisation and steps together are exactly what a cell in the grid is.
_DEFINING_KNOBS = ("width", "height", "quantisation", "steps")


class SweepSpecError(ValueError):
    """A sweep spec is wrong. Always names the file and the field."""


class DiskGuardError(RuntimeError):
    """Free space fell below the configured floor. Never swallowed — a sweep
    that silently kept going while the disk filled up is worse than one that
    stopped."""


def _require(d: Dict[str, Any], key: str, where: str) -> Any:
    if key not in d or d[key] is None:
        raise SweepSpecError(f"{where}: missing required key '{key}'")
    return d[key]


@dataclass(frozen=True)
class SweepSpec:
    """One declarative grid: a model, a runtime, fixed knobs, axes to vary,
    and the caps that keep an unattended run from doing something a person
    would have stopped by hand.
    """
    id: str
    model_id: str
    runtime_id: str
    model_alias: str
    metric: str
    prompt: str
    seed: int
    resolutions: List[Tuple[int, int]]
    quantisations: List[int]
    steps: List[int]

    battery_percentage_stop_limit: float = 15.0
    low_ram: bool = False
    vae_tiling: bool = True
    vae_tile_size: Optional[int] = None

    job_timeout_seconds: float = 300.0
    max_jobs: int = 40
    max_wall_seconds: float = 8 * 3600.0
    idle_wait_timeout_minutes: float = 120.0
    idle_poll_seconds: float = 30.0
    disk_free_floor_gb: float = 30.0

    source_path: Optional[Path] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d.pop("source_path", None)
        return d


def load_spec(path: Path | str) -> SweepSpec:
    """Parse and validate a sweep spec. Raises SweepSpecError naming the file
    and field on anything malformed — an unattended run must never start
    against a spec nobody actually reviewed."""
    path = Path(path)
    where = str(path)
    if not path.is_file():
        raise SweepSpecError(f"{where}: not a file")
    raw = yaml.safe_load(path.read_text()) or {}
    if raw.get("schema") != SCHEMA_VERSION:
        raise SweepSpecError(f"{where}: schema is {raw.get('schema')!r}, "
                              f"this build reads {SCHEMA_VERSION}")

    spec_id = _require(raw, "id", where)
    model_id = _require(raw, "model_id", where)
    runtime_id = raw.get("runtime_id", "mflux")
    model_alias = _require(raw, "model_alias", where)
    metric = _require(raw, "metric", where)
    if metric not in ms.SPEED_METRICS:
        raise SweepSpecError(f"{where}: metric {metric!r} not one of {sorted(ms.SPEED_METRICS)}")
    # A sweep records the seconds a job took. That is a cost metric by
    # construction: it counts no units, so it cannot produce a rate, and
    # filing seconds under a rate name would store the reciprocal.
    if registry.metric_direction(metric) == "rate":
        raise SweepSpecError(
            f"{where}: metric {metric!r} is a rate (units per second), and a sweep "
            f"only times jobs. Use a seconds-per-unit metric.")

    fixed = raw.get("fixed", {}) or {}
    prompt = _require(fixed, "prompt", f"{where}: fixed")
    seed = int(fixed.get("seed", 42))

    axes = raw.get("axes", {}) or {}
    resolutions_raw = axes.get("resolution") or ([fixed["resolution"]] if "resolution" in fixed else None)
    if not resolutions_raw:
        raise SweepSpecError(f"{where}: need axes.resolution or fixed.resolution")
    resolutions = []
    for r in resolutions_raw:
        if not (isinstance(r, (list, tuple)) and len(r) == 2):
            raise SweepSpecError(f"{where}: resolution entry {r!r} is not [width, height]")
        resolutions.append((int(r[0]), int(r[1])))

    quantisations_raw = axes.get("quantisation")
    if quantisations_raw is None:
        quantisations_raw = [fixed["quantisation"]] if "quantisation" in fixed else [None]
    quantisations = [None if q in (None, "none") else int(q) for q in quantisations_raw]

    steps_raw = axes.get("steps")
    if steps_raw is None:
        steps_raw = [fixed["steps"]] if "steps" in fixed else None
    if not steps_raw:
        raise SweepSpecError(f"{where}: need axes.steps or fixed.steps")
    steps = [int(s) for s in steps_raw]

    mflux_flags = raw.get("mflux_flags", {}) or {}
    runner = raw.get("runner", {}) or {}

    return SweepSpec(
        id=spec_id,
        model_id=model_id,
        runtime_id=runtime_id,
        model_alias=model_alias,
        metric=metric,
        prompt=prompt,
        seed=seed,
        resolutions=resolutions,
        quantisations=quantisations,
        steps=steps,
        battery_percentage_stop_limit=float(mflux_flags.get("battery_percentage_stop_limit", 15.0)),
        low_ram=bool(mflux_flags.get("low_ram", False)),
        vae_tiling=bool(mflux_flags.get("vae_tiling", True)),
        vae_tile_size=mflux_flags.get("vae_tile_size"),
        job_timeout_seconds=float((raw.get("job_cap") or {}).get("timeout_seconds", 300.0)),
        max_jobs=int(runner.get("max_jobs", 40)),
        max_wall_seconds=float(runner.get("max_wall_seconds", 8 * 3600.0)),
        idle_wait_timeout_minutes=float(runner.get("idle_wait_timeout_minutes", 120.0)),
        idle_poll_seconds=float(runner.get("idle_poll_seconds", 30.0)),
        disk_free_floor_gb=float(runner.get("disk_free_floor_gb", 30.0)),
        source_path=path,
    )


@dataclass(frozen=True)
class Job:
    """One cell of the grid: the knobs that fully determine one generation."""
    width: int
    height: int
    quantisation: Optional[int]
    steps: int

    @property
    def slug(self) -> str:
        q = f"q{self.quantisation}" if self.quantisation is not None else "qnone"
        return f"{self.width}x{self.height}-{q}-s{self.steps}"

    def knobs(self, spec: SweepSpec) -> Dict[str, Any]:
        return {
            "width": self.width, "height": self.height,
            "quantisation": self.quantisation, "steps": self.steps,
            "seed": spec.seed, "model_alias": spec.model_alias,
        }


def expand_jobs(spec: SweepSpec) -> List[Job]:
    """Every cell of the grid, in a fixed order so a resumed run and a fresh
    run walk it identically."""
    jobs = []
    for (w, h), q, s in itertools.product(spec.resolutions, spec.quantisations, spec.steps):
        jobs.append(Job(width=w, height=h, quantisation=q, steps=s))
    return jobs


def _job_already_recorded(job: Job, spec: SweepSpec, system_id: str,
                           existing: List[ms.Measurement]) -> bool:
    """A job counts as done if any measurement — success or failure — already
    exists for this system, model and metric, with the same defining knobs.
    A failure is not retried: the failure itself is the recorded fact (this is
    where this machine stops), and retrying it would just burn the night
    reproducing an OOM already on file.
    """
    want = job.knobs(spec)
    for m in existing:
        if m.system_id != system_id or m.model_id != spec.model_id:
            continue
        if m.metric not in (spec.metric, "load_seconds"):
            continue
        if all(m.knobs.get(k) == want.get(k) for k in _DEFINING_KNOBS):
            return True
    return False


def disk_free_gb(path: Path) -> float:
    path = path if path.exists() else path.parent
    return shutil.disk_usage(path).free / (1024 ** 3)


def wait_for_idle(
    *,
    timeout_minutes: float,
    poll_seconds: float,
    sample_fn: Callable[[], str] = ms.sample_contention,
    sleep_fn: Callable[[float], None] = time.sleep,
    clock_fn: Callable[[], float] = time.monotonic,
    log: Callable[[str], None] = print,
) -> bool:
    """Poll contention until the machine is genuinely idle, or give up.

    Never trusts a single reading — the whole point of the underlying fix is
    that a snapshot can be wrong for the length of one sample, so this keeps
    asking rather than sampling once and believing it.
    """
    deadline = clock_fn() + timeout_minutes * 60
    while True:
        state = sample_fn()
        if state == "solo":
            return True
        if clock_fn() >= deadline:
            return False
        log(f"  machine is {state}; waiting ({poll_seconds:.0f}s)...")
        sleep_fn(poll_seconds)


@dataclass
class RunRecord:
    """What one sweep run did — the log that makes progress readable after
    the fact, and the thing `pluto sweep run` prints a summary of."""
    spec_id: str
    system_id: Optional[str] = None
    started_at: str = ""
    finished_at: Optional[str] = None
    jobs_total: int = 0
    jobs_skipped: int = 0
    jobs_run: int = 0
    jobs_succeeded: int = 0
    jobs_failed: int = 0
    stopped_reason: str = "not_started"
    last_job_slug: Optional[str] = None
    events: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class _Caffeinate:
    """Keeps the Mac awake for the duration of the `with` block. Releases on
    normal exit, on an uncaught exception, and via `-w <our pid>` as a
    backstop if this process itself dies without a clean unwind — a Mac that
    never sleeps again is exactly the failure mode to design against.

    A no-op off Darwin, since `caffeinate` doesn't exist elsewhere and a
    sweep run there has no equivalent standing assumption to defend.
    """

    def __init__(self, enabled: bool = True, log: Callable[[str], None] = print):
        self.enabled = enabled and sys.platform == "darwin"
        self.log = log
        self.proc: Optional[subprocess.Popen] = None

    def __enter__(self) -> "_Caffeinate":
        if self.enabled:
            self.proc = subprocess.Popen(
                ["caffeinate", "-i", "-w", str(os.getpid())],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            self.log("  caffeinate started — this Mac will not idle-sleep until the sweep ends")
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self.proc is None:
            return
        self.proc.terminate()
        try:
            self.proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.proc.wait(timeout=5)
        self.log("  caffeinate released")


def _resolve_job_output(outputs_dir: Path, run_id: str, job: Job) -> Path:
    """Where a job's generated image lands. Contained the same way
    `spacepilot.pluto.core.utils.resolve_output` enforces containment for reads: the
    resolved path must stay inside `outputs_dir` before anything is written."""
    outputs_dir = outputs_dir.resolve()
    candidate = (outputs_dir / "sweeps" / run_id / f"{job.slug}.png").resolve()
    if not candidate.is_relative_to(outputs_dir):
        raise ValueError(f"job output path {candidate} escapes outputs_dir {outputs_dir}")
    candidate.parent.mkdir(parents=True, exist_ok=True)
    return candidate


def _default_driver(spec: SweepSpec):
    from spacepilot.drivers.mflux_driver import MfluxDriver
    return MfluxDriver()


def run_sweep(
    spec: SweepSpec,
    *,
    outputs_dir: Optional[Path] = None,
    measurements_root: Optional[Path] = None,
    systems_root: Optional[Path] = None,
    runs_dir: Optional[Path] = None,
    driver: Optional[Any] = None,
    sample_fn: Optional[Callable[[], str]] = None,
    sleep_fn: Callable[[float], None] = time.sleep,
    clock_fn: Callable[[], float] = time.monotonic,
    caffeinate: bool = True,
    log: Callable[[str], None] = print,
    profile: Optional[Any] = None,
) -> RunRecord:
    """Walk a sweep spec's grid, one real generation per cell, unattended.

    The contract this exists to keep, end to end:

    - **Starts only when genuinely idle.** Polls `sample_fn` (the fixed
      contention check) up to `idle_wait_timeout_minutes`; if the machine
      never goes idle, this returns without running a single job or ever
      starting caffeinate.
    - **Keeps the Mac awake while running**, and only while running — see
      `_Caffeinate`.
    - **Yields between jobs.** Idleness, the job-count cap, the wall-clock
      cap and the disk floor are all re-checked before every job, never only
      once at the start. A job in flight is never interrupted; the check
      happens strictly between jobs, and a job is about a minute.
    - **Resumable.** A job already present in `measurements_root` — success
      or failure, matched on system, model, metric and the knobs defining the
      grid cell (see `_job_already_recorded`) — is skipped, not re-run.
    - **Records failures as measurements**, `status="failed"`, distinguished
      from a success and excluded from every speed summary by
      `measurements.summarise`.
    - **Disk guard**, before starting and before every job.

    `driver` defaults to a real `MfluxDriver`; tests pass a fake with a
    scripted `.infer()` so no real mflux subprocess ever runs. `sample_fn`
    defaults to `measurements.sample_contention`; tests script it to prove
    the mid-sweep yield without needing the machine to actually go busy.
    """
    from spacepilot.device_probe import probe_local_device

    profile = profile or probe_local_device()
    system = ms.system_from_profile(profile)
    ms.write_system(system, root=systems_root)

    outputs_dir = Path(outputs_dir) if outputs_dir else (_ROOT / "outputs")
    outputs_dir.mkdir(parents=True, exist_ok=True)
    sample_fn = sample_fn or ms.sample_contention
    driver = driver or _default_driver(spec)

    record = RunRecord(
        spec_id=spec.id, system_id=system.id,
        started_at=_dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
    )

    def _event(msg: str) -> None:
        record.events.append(msg)
        log(f"  {msg}")

    free_gb = disk_free_gb(outputs_dir)
    if free_gb < spec.disk_free_floor_gb:
        record.stopped_reason = "disk_floor_before_start"
        _event(f"refusing to start: {free_gb:.1f} GB free < floor {spec.disk_free_floor_gb:.1f} GB")
        record.finished_at = _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")
        _write_run_record(record, runs_dir)
        return record

    if not wait_for_idle(
        timeout_minutes=spec.idle_wait_timeout_minutes,
        poll_seconds=spec.idle_poll_seconds,
        sample_fn=sample_fn, sleep_fn=sleep_fn, clock_fn=clock_fn, log=log,
    ):
        record.stopped_reason = "never_idle"
        _event(f"machine never went idle within {spec.idle_wait_timeout_minutes:.0f} minutes; exiting")
        record.finished_at = _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")
        _write_run_record(record, runs_dir)
        return record

    existing = ms.load_measurements(measurements_root)
    all_jobs = expand_jobs(spec)
    todo = [j for j in all_jobs if not _job_already_recorded(j, spec, system.id, existing)]
    record.jobs_total = len(all_jobs)
    record.jobs_skipped = len(all_jobs) - len(todo)
    _event(f"{len(all_jobs)} jobs in spec, {record.jobs_skipped} already recorded, "
           f"{len(todo)} to run")

    run_id = _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    wall_start = clock_fn()

    with _Caffeinate(enabled=caffeinate, log=log):
        for job in todo:
            if record.jobs_run >= spec.max_jobs:
                record.stopped_reason = "max_jobs"
                _event(f"stopping: reached max_jobs ({spec.max_jobs})")
                break
            if clock_fn() - wall_start >= spec.max_wall_seconds:
                record.stopped_reason = "max_wall_seconds"
                _event(f"stopping: reached max_wall_seconds ({spec.max_wall_seconds:.0f}s)")
                break
            free_gb = disk_free_gb(outputs_dir)
            if free_gb < spec.disk_free_floor_gb:
                record.stopped_reason = "disk_floor_mid_sweep"
                _event(f"stopping: {free_gb:.1f} GB free < floor {spec.disk_free_floor_gb:.1f} GB")
                break
            state = sample_fn()
            if state != "solo":
                record.stopped_reason = "human_returned"
                _event(f"stopping: machine is {state}, not solo — yielding the machine back")
                break

            _event(f"running {job.slug}")
            out_path = _resolve_job_output(outputs_dir, run_id, job)
            knobs = job.knobs(spec)
            extra_args = ["-B", str(spec.battery_percentage_stop_limit)]
            if spec.low_ram:
                extra_args.append("--low-ram")
            if spec.vae_tiling:
                extra_args.append("--vae-tiling")
            if spec.vae_tile_size:
                extra_args += ["--vae-tile-size", str(spec.vae_tile_size)]

            job_start = clock_fn()
            try:
                result = driver.infer(
                    prompt=spec.prompt, model=spec.model_alias,
                    quantize=job.quantisation, steps=job.steps,
                    seed=spec.seed, height=job.height, width=job.width,
                    out_path=str(out_path), extra_args=extra_args,
                    timeout=spec.job_timeout_seconds,
                )
            except Exception as exc:  # a failed job is a recorded fact, not a crashed sweep
                elapsed = clock_fn() - job_start
                ms.record(
                    system=system, model_id=spec.model_id, metric=spec.metric,
                    value=round(elapsed, 3), contention=state, root=measurements_root,
                    runtime_id=spec.runtime_id, quantisation=_quant_label(job.quantisation),
                    knobs=knobs, status="failed", error=str(exc)[:300],
                    note=f"sweep {spec.id} job {job.slug} did not complete",
                )
                record.jobs_failed += 1
                _event(f"FAILED {job.slug}: {exc}")
            else:
                generate_s = result.get("generate_seconds")
                load_s = result.get("load_seconds")
                value = generate_s if generate_s is not None else result.get("wall_seconds")
                ms.record(
                    system=system, model_id=spec.model_id, metric=spec.metric,
                    value=value, contention=state, root=measurements_root,
                    runtime_id=spec.runtime_id, quantisation=_quant_label(job.quantisation),
                    knobs=knobs, status="ok", wall_seconds=result.get("wall_seconds"),
                    note=f"sweep {spec.id} job {job.slug}",
                )
                if load_s is not None:
                    ms.record(
                        system=system, model_id=spec.model_id, metric="load_seconds",
                        value=load_s, contention=state, root=measurements_root,
                        runtime_id=spec.runtime_id, quantisation=_quant_label(job.quantisation),
                        knobs=knobs, status="ok",
                        note=f"sweep {spec.id} job {job.slug}",
                    )
                record.jobs_succeeded += 1
                _event(f"ok {job.slug}: {value}")

            record.jobs_run += 1
            record.last_job_slug = job.slug
        else:
            record.stopped_reason = "completed"
            _event("sweep exhausted every job in the spec")

    record.finished_at = _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")
    _write_run_record(record, runs_dir)
    return record


def _quant_label(q: Optional[int]) -> Optional[str]:
    """Matches the `intN` convention already on file, e.g. the flux2-klein-4b
    measurements recorded manually before this runner existed."""
    return f"int{q}" if q is not None else None


def _write_run_record(record: RunRecord, runs_dir: Optional[Path]) -> Path:
    directory = Path(runs_dir) if runs_dir else RUNS_DIR
    directory.mkdir(parents=True, exist_ok=True)
    stamp = record.started_at.replace(":", "").replace("-", "")
    path = directory / f"{stamp}-{record.spec_id}.json"
    path.write_text(json.dumps(record.to_dict(), indent=2))
    return path
