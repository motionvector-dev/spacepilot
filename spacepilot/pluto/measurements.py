"""What a machine actually did, as opposed to what a model card claims.

The model registry answers "could this run here". This answers "what happened
when it did", and the two are kept apart on purpose: a capacity claim is a
property of the model, a measurement is a property of one run on one machine.

Three rules the schema enforces, each because the alternative silently lies.

**A measurement names its machine by id, not by prose.** The model registry
carries `device: "Apple M1 Max 32GB"` inline, which cannot be correlated — two
records from the same box may or may not be the same box, and nothing can tell.
Records here reference a system file that the probe wrote.

**A measurement records whether the machine was busy.** Darkbloom keeps two
sample streams for exactly this reason: a rate observed while other work was
running answers "what will a request see", and a rate observed on an idle box
answers "what can this machine do". Averaged together they answer neither. The
contention state is sampled here rather than taken from the caller, because a
caller reporting its own idleness is the least reliable possible source.

**A measurement is measured.** The model registry admits `declared` and
`estimated` because a capacity claim has to come from somewhere before anyone
runs anything. This store does not: a record that was not observed does not
belong in it.

**A measurement names the weights it describes.** `runtime_version` already
pins the software side: "mflux 0.19.0 took 23.4s" is checkable in a way that
"mflux took 23.4s" is not. `model_revision` is the same idea for the model
side, and it matters more, because a repo id moves under you without any
version number changing. If the author force-pushes, re-uploads, or lands a
new commit on main, the record still says `flux2-klein-4b-4bit` and now
describes weights nobody can obtain again. So the revision the registry pins
is copied onto the record at write time (see `record`), not looked up later —
a lookup would return today's answer, which is the thing being defended
against.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import os
import platform
import re
import shutil
import statistics
import subprocess
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import yaml

from spacepilot.paths import shipped_dir, writable_dir

try:
    import psutil
except ImportError:  # pragma: no cover - psutil is a declared dependency; this
    # only guards a broken/partial environment, not an expected path.
    psutil = None

SCHEMA_VERSION = 1

# Records are written by the machine that made them, so they never go inside
# the installed package — see spacepilot.paths. Reads merge what shipped with
# what this machine has recorded; in a checkout the two are the same directory
# and the merge dedupes them.
SHIPPED_SYSTEMS_DIR = shipped_dir("systems")
SHIPPED_MEASUREMENTS_DIR = shipped_dir("measurements")
SYSTEMS_DIR = writable_dir("systems")
MEASUREMENTS_DIR = writable_dir("measurements")


def _roots(shipped: Path, writable: Path) -> List[Path]:
    out: List[Path] = []
    for candidate in (shipped, writable):
        resolved = Path(candidate).resolve()
        if resolved not in out:
            out.append(resolved)
    return out

# Reuse the model registry's vocabulary rather than inventing a parallel one.
from spacepilot.pluto.registry import SPEED_METRICS, BACKENDS  # noqa: E402

CONTENTION = {
    "solo",     # nothing else meaningful was running
    "loaded",   # something else was competing for CPU, GPU or memory
    "unknown",  # could not sample; treated as `loaded` by every summary
}

# Above this per-core share of CPU, attributable to processes OUTSIDE our own
# tree, the box is not idle. Deliberately low: the cost of calling a busy
# machine idle is a permanently wrong ceiling, and the cost of calling an idle
# machine busy is one discarded sample.
#
# This used to be `os.getloadavg()[0] / cpu_count`, which made `solo`
# unreachable by construction: load average counts every process on the box,
# ours included, so a measurement heavy enough to be worth taking always
# pushed its own load average over the threshold by the time it finished.
# Contention means another party competing for the machine, not this process
# doing the work it was asked to do — so this now excludes our own process
# tree (this process plus every descendant, including a subprocess we spawn
# such as the mflux driver's `mflux-generate*` child) and asks only what
# *everyone else* is doing. See `_external_cpu_percent`.
_LOAD_PER_CORE_IDLE = 0.4

# How long to sample CPU% over. psutil.Process.cpu_percent reports "percent
# since the last call", so telling solo from loaded needs two reads spaced
# apart; too short and a competitor between the reads is invisible, too long
# and every `sample_contention()` call (two of which bracket every `pluto
# measure` run) adds real wall time. 150ms is long enough for `ps`-scale
# sampling to be meaningful and short enough not to matter next to the runs
# it brackets, which are seconds to minutes.
_CONTENTION_SAMPLE_SECONDS = 0.15

# NVIDIA reports both counters in real time through nvidia-smi.  A non-zero
# allocation is not automatically contention: an idle resident model is a
# readiness fact, not proof that it is competing with this run.  Sustained
# compute use is, and a nearly-full device is conservatively treated as busy
# because it can prevent an otherwise feasible run from allocating.
_NVIDIA_GPU_BUSY_PERCENT = 5.0
_NVIDIA_GPU_MEMORY_PRESSURE = 0.90


def _nvidia_gpu_contention() -> Optional[str]:
    """Return CUDA host contention, or ``None`` where it cannot be probed.

    The result is deliberately a host-level guard rather than an attribution
    claim: nvidia-smi cannot tell this caller which GPU a future subprocess
    will select.  Seeing *any* accessible GPU busy therefore marks the sample
    ``loaded`` conservatively; seeing all of them quiet only supplements the
    CPU reading.  No nvidia-smi is normal on Metal, ROCm, and CPU-only hosts,
    so absence is ``None`` rather than a fabricated GPU-idle observation.

    A present but failed or malformed nvidia-smi response is ``unknown``.  It
    must not turn an unobservable accelerator into a clean ``solo`` sample.
    """
    executable = shutil.which("nvidia-smi")
    if executable is None:
        return None
    try:
        result = subprocess.run(
            [
                executable,
                "--query-gpu=utilization.gpu,memory.used,memory.total",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=2.0,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return "unknown"
    if result.returncode != 0:
        return "unknown"

    rows = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if not rows:
        return "unknown"
    try:
        samples = []
        for row in rows:
            utilization, used_mib, total_mib = (part.strip() for part in row.split(","))
            used = float(used_mib)
            total = float(total_mib)
            if total <= 0:
                return "unknown"
            samples.append((float(utilization), used / total))
    except (TypeError, ValueError):
        return "unknown"
    return (
        "loaded"
        if any(
            utilization > _NVIDIA_GPU_BUSY_PERCENT
            or memory_ratio >= _NVIDIA_GPU_MEMORY_PRESSURE
            for utilization, memory_ratio in samples
        )
        else "solo"
    )


class MeasurementError(ValueError):
    """A record is wrong. Always names the file and the field."""


def _slug(text: str) -> str:
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", text.lower())).strip("-")


@dataclass(frozen=True)
class System:
    """A machine configuration, written by the probe rather than by hand.

    The id describes a configuration, not an individual: every 32 GB M1 Max
    lands on the same id, which is what makes samples from different people
    comparable. `host_fingerprint` is a truncated salted hash, present only so
    many records can be recognised as coming from one box; it identifies no
    person and does not survive back to a hostname.
    """
    id: str
    chip: Optional[str] = None
    machine_model: Optional[str] = None
    backend: Optional[str] = None
    os_name: Optional[str] = None
    os_version: Optional[str] = None
    cpu_cores: Optional[int] = None
    gpu_cores: Optional[int] = None
    memory_total_bytes: Optional[int] = None
    memory_limit_bytes: Optional[int] = None
    memory_limit_source: Optional[str] = None
    memory_unified: bool = False
    vram_total_bytes: Optional[int] = None
    host_fingerprint: Optional[str] = None
    recorded_on: Optional[str] = None
    unknown: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


STATUS = {
    "ok",      # the run completed and `value` is a real speed number
    "failed",  # the run did not complete; `value` is not a speed number
}


@dataclass(frozen=True)
class Measurement:
    """One run, on one machine, with the knobs it was given.

    `status` defaults to "ok" so every record written before this field
    existed still parses and still counts, unchanged, in every summary. A
    "failed" record is a real observation too — an OOM at 1024²/int8 says
    exactly where this machine stops — but its `value` is not a speed number
    (see `record`'s docstring), so `summarise` excludes it from both streams.
    """
    schema: int
    system_id: str
    model_id: str
    metric: str
    value: float
    contention: str
    measured_on: str
    variant_id: Optional[str] = None
    runtime_id: Optional[str] = None
    runtime_version: Optional[str] = None
    # The exact weights. None means the registry did not pin this variant when
    # the run happened, so the record names a repo that has since been free to
    # change. Absent rather than false, so every record written before this
    # field existed still parses unchanged.
    model_revision: Optional[str] = None
    quantisation: Optional[str] = None
    backend: Optional[str] = None
    interpreter: Optional[str] = None
    peak_memory_bytes: Optional[int] = None
    wall_seconds: Optional[float] = None
    knobs: Dict[str, Any] = field(default_factory=dict)
    note: Optional[str] = None
    status: str = "ok"
    error: Optional[str] = None

    @property
    def is_solo(self) -> bool:
        return self.contention == "solo"

    @property
    def is_ok(self) -> bool:
        return self.status == "ok"

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v not in (None, {}, [])}


def subject_id(measurement: Measurement) -> str:
    """The registry variant a measurement describes.

    New records use ``variant_id``.  Older records used ``model_id`` for the
    same purpose, so readers must consistently prefer the former without
    orphaning the corpus written before that field existed.
    """
    return measurement.variant_id or measurement.model_id


def _own_tree_pids(root_pid: Optional[int] = None) -> Set[int]:
    """This process, plus every descendant — recursively.

    Descendants matter because the heaviest thing this repo ever measures is
    not this process: it's a subprocess it spawns (mflux, ffmpeg). A tree that
    only excluded our own pid would count that subprocess as "someone else"
    and call every real measurement `loaded`, which is the exact bug this
    function exists to close.
    """
    pid = root_pid if root_pid is not None else os.getpid()
    if psutil is None:
        return {pid}
    try:
        me = psutil.Process(pid)
    except psutil.Error:
        return {pid}
    pids = {me.pid}
    try:
        pids.update(child.pid for child in me.children(recursive=True))
    except psutil.Error:
        pass
    return pids


def _external_cpu_percent(own_pids: Set[int], interval: float) -> Optional[float]:
    """Sum of CPU% used by every process outside `own_pids`, over `interval`.

    psutil.Process.cpu_percent(None) reports percent-since-the-last-call, so a
    given process's first read is always 0.0 — this "primes" every process,
    sleeps, then reads it back, the standard psutil two-call pattern. A
    process that starts or exits mid-window is skipped rather than raising:
    this only decides one measurement's contention label, not a standing fact
    about the machine, so missing one transient process for one sample is a
    degraded sample, not a wrong conclusion.

    Returns None (→ "unknown") if the process list cannot be read at all.
    """
    if psutil is None:
        return None
    try:
        procs = []
        for p in psutil.process_iter(["pid"]):
            if p.pid in own_pids:
                continue
            try:
                p.cpu_percent(None)  # prime; discard the meaningless first read
                procs.append(p)
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
    except Exception:
        return None
    time.sleep(interval)
    total = 0.0
    for p in procs:
        try:
            total += p.cpu_percent(None)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
    return total


def sample_contention(
    profile: Optional[Any] = None,
    *,
    own_pids: Optional[Set[int]] = None,
    interval: float = _CONTENTION_SAMPLE_SECONDS,
) -> str:
    """Ask the OS whether something ELSE is busy, rather than asking the caller.

    "Solo" means nothing outside our own process tree is meaningfully
    competing for CPU; "loaded" means something is. It does not mean the box
    is quiet in some absolute sense — our own work, however heavy, is never
    what makes a measurement of that work `loaded`. See `_LOAD_PER_CORE_IDLE`
    for why this replaced a plain load-average check.

    On NVIDIA hosts it also samples instantaneous device utilization and
    memory pressure through nvidia-smi.  That is host-level rather than
    process-attributed telemetry, so any busy accessible GPU conservatively
    marks the sample loaded; Metal and ROCm remain explicitly unobserved by
    this sampler until their native telemetry adapters exist.  A probe error
    is unknown, not a made-up GPU-idle reading.

    `profile` is accepted and ignored — kept for call-site compatibility; it
    was never read even before this fix. `own_pids` overrides what counts as
    "us"; the default is this process's own tree. Tests use the override to
    simulate a genuine external competitor without needing to launch a process
    that is actually outside CI's own process tree.
    """
    if psutil is None:
        cpu_state = "unknown"
    else:
        cores = os.cpu_count() or 1
        pids = own_pids if own_pids is not None else _own_tree_pids()
        external = _external_cpu_percent(pids, interval)
        if external is None:
            cpu_state = "unknown"
        else:
            external_load_per_core = (external / 100.0) / cores
            cpu_state = "solo" if external_load_per_core <= _LOAD_PER_CORE_IDLE else "loaded"

    gpu_state = _nvidia_gpu_contention()
    if "unknown" in {cpu_state, gpu_state}:
        return "unknown"
    if "loaded" in {cpu_state, gpu_state}:
        return "loaded"
    return "solo"


def system_id_for(profile: Any) -> str:
    """A stable id for a configuration: chip plus memory, both of which matter."""
    chip = profile.chip or profile.machine_model or platform.machine() or "unknown"
    gib = round((profile.memory_total_bytes or 0) / (1024 ** 3))
    return _slug(f"{chip}-{gib}gb") if gib else _slug(chip)


FINGERPRINT_SALT_DEFAULT = "pluto-measurements-v1"


def _fingerprint() -> Optional[str]:
    """Truncated salted digest of the hostname. Dedupes boxes, names nobody.

    Both the old environment name and the historical default salt are
    permanent compatibility inputs: changing either would assign every
    existing machine a new identity.
    """
    try:
        host = platform.node()
    except Exception:
        return None
    if not host:
        return None
    from spacepilot.paths import env_value
    salt = env_value(
        "SPACEPILOT_FINGERPRINT_SALT", "PLUTO_FINGERPRINT_SALT",
        default=FINGERPRINT_SALT_DEFAULT,
    )
    return hashlib.sha256(f"{salt}:{host}".encode()).hexdigest()[:12]


def system_from_profile(profile: Any) -> System:
    return System(
        id=system_id_for(profile),
        chip=profile.chip,
        machine_model=profile.machine_model,
        backend=profile.backend,
        os_name=profile.os_name,
        os_version=profile.os_version,
        cpu_cores=profile.cpu_cores,
        gpu_cores=profile.gpu_cores,
        memory_total_bytes=profile.memory_total_bytes,
        memory_limit_bytes=profile.memory_limit_bytes,
        memory_limit_source=profile.memory_limit_source,
        memory_unified=bool(profile.memory_unified),
        vram_total_bytes=profile.vram_total_bytes,
        host_fingerprint=_fingerprint(),
        recorded_on=_dt.date.today().isoformat(),
        unknown=dict(getattr(profile, "unknown", {}) or {}),
    )


def write_system(system: System, root: Optional[Path] = None) -> Path:
    """Write or refresh a system record. Rewriting is expected: free memory and
    OS version drift, and a stale record would misattribute later samples."""
    directory = (root or SYSTEMS_DIR)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{system.id}.yaml"
    payload = {"schema": SCHEMA_VERSION, **system.to_dict()}
    path.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True))
    return path


_UNSET = object()


def revision_for(
    *candidates: Optional[str],
    resolved_revision: object = _UNSET,
) -> Optional[str]:
    """The executed revision, or the registry pin when execution cannot say.

    Records name their subject as `variant_id`, or — for records written before
    that field existed — as `model_id` holding the variant id. Both are tried.

    ``resolved_revision`` is authoritative when supplied, including explicit
    ``None`` for a constructor/env path whose provenance is unknown. This
    prevents a registry SHA from being stamped onto different bytes merely
    because they ran under the same variant id.

    Returns None when nothing matches or the registry cannot be read. A missing
    revision is exactly what an unpinned variant should produce, and a registry
    that fails to load must never take a real measurement down with it: the run
    already happened, and losing the sample is strictly worse than recording it
    without this one field.
    """
    if resolved_revision is not _UNSET:
        return resolved_revision if isinstance(resolved_revision, str) else None
    try:
        from spacepilot.pluto.registry import registry as _registry
        reg = _registry()
    except Exception:
        return None
    for cid in candidates:
        if not cid:
            continue
        v = reg.variant(cid)
        if v is not None and v.revision:
            return v.revision
    return None


def record(
    *,
    system: System,
    model_id: str,
    metric: str,
    value: float,
    contention: Optional[str] = None,
    root: Optional[Path] = None,
    status: str = "ok",
    **fields: Any,
) -> Path:
    """Append one observation. Contention is sampled unless explicitly passed.

    `status="failed"` records a run that did not complete — a crash, an OOM,
    a timeout. `value` still has to be a float (the schema requires one); the
    convention is wall time elapsed before the failure, which is informative
    without being a claim that this is a speed the model achieved. A failed
    record is excluded from both streams in `summarise` — it must never
    pollute a speed summary, only ever explain why one sample is missing.
    """
    if metric not in SPEED_METRICS:
        raise MeasurementError(f"metric {metric!r} not one of {sorted(SPEED_METRICS)}")
    if status not in STATUS:
        raise MeasurementError(f"status {status!r} not one of {sorted(STATUS)}")
    state = contention or sample_contention()
    if state not in CONTENTION:
        raise MeasurementError(f"contention {state!r} not one of {sorted(CONTENTION)}")

    # The subject should be a registry VARIANT. Four kokoro records were
    # written under `kokoro-82m` — a truncation of `kokoro-82m-onnx` — and
    # became invisible to both the export and `models list`: a real
    # measurement the product then denied having. Refuse only the provably
    # wrong ids: a known model id, or a truncation of an existing variant.
    # A wholly unknown id still records — the registry lags reality, and
    # losing a completed run is worse than a missing pin
    # (test_an_unknown_model_records_without_a_revision holds that contract).
    subject = fields.get("variant_id") or model_id
    try:
        from spacepilot.pluto.registry import registry as _registry
        _reg = _registry()
    except Exception:
        _reg = None
    if _reg is not None and _reg.variant(subject) is None:
        model = _reg.model(subject)
        if model is not None:
            names = ", ".join(v.id for v in model.variants)
            raise MeasurementError(
                f"{subject!r} is a model, not a variant. A measurement names the "
                f"exact weights that ran. Use one of: {names}"
            )
        truncated_of = [v.id for v in _reg.variants if v.id.startswith(subject + "-")]
        if truncated_of:
            raise MeasurementError(
                f"{subject!r} is not a registry variant but looks like a "
                f"truncation of: {', '.join(truncated_of)}. Records under it "
                "would be invisible to the export and to `models list`."
            )

    # Stamped at write time from the registry, because that is when the run
    # happened. Resolving it at read time would answer "what does this repo
    # point at now", which is the question a pin exists to stop anyone asking.
    resolved_revision = fields.pop("resolved_revision", _UNSET)
    if fields.get("model_revision", _UNSET) is _UNSET:
        fields["model_revision"] = revision_for(
            fields.get("variant_id"), model_id,
            resolved_revision=resolved_revision,
        )

    now = _dt.datetime.now(_dt.timezone.utc)
    m = Measurement(
        schema=SCHEMA_VERSION,
        system_id=system.id,
        model_id=model_id,
        metric=metric,
        value=float(value),
        contention=state,
        measured_on=now.isoformat(timespec="seconds"),
        backend=fields.pop("backend", system.backend),
        status=status,
        **fields,
    )
    directory = (root or MEASUREMENTS_DIR) / system.id / _slug(model_id)
    directory.mkdir(parents=True, exist_ok=True)
    body = yaml.safe_dump(m.to_dict(), sort_keys=False, allow_unicode=True)

    # Second-resolution names collide: a benchmark loop records several
    # iterations within one second and each overwrote the last, leaving one
    # sample where there were ten. The digest makes the name unique without
    # a counter, which would race between two processes measuring at once.
    stamp = now.strftime("%Y%m%dT%H%M%SZ")
    digest = hashlib.sha256(body.encode()).hexdigest()[:8]
    suffix = "-".join(filter(None, [m.runtime_id, m.quantisation]))
    name = "-".join(filter(None, [stamp, _slug(suffix) or None, digest]))
    path = directory / f"{name}.yaml"
    path.write_text(body)
    return path


def parse_measurement(raw: Dict[str, Any], where: str) -> Measurement:
    if raw.get("schema") != SCHEMA_VERSION:
        raise MeasurementError(f"{where}: schema is {raw.get('schema')!r}, "
                               f"this build reads {SCHEMA_VERSION}")
    for required in ("system_id", "model_id", "metric", "value",
                     "contention", "measured_on"):
        if raw.get(required) is None:
            raise MeasurementError(f"{where}: missing '{required}'")
    if raw["metric"] not in SPEED_METRICS:
        raise MeasurementError(f"{where}: metric {raw['metric']!r} unknown")
    if raw["contention"] not in CONTENTION:
        raise MeasurementError(
            f"{where}: contention {raw['contention']!r} not one of {sorted(CONTENTION)} — "
            f"a sample that does not say whether the machine was busy cannot be "
            f"summarised, because the two streams are never merged")
    if raw.get("status") is not None and raw["status"] not in STATUS:
        raise MeasurementError(f"{where}: status {raw['status']!r} not one of {sorted(STATUS)}")
    known = {f for f in Measurement.__dataclass_fields__}
    return Measurement(**{k: v for k, v in raw.items() if k in known})


def load_measurements(root: Optional[Path] = None) -> List[Measurement]:
    """Every record this machine can see: the corpus that shipped, plus the
    records it made itself. An explicit `root` reads only that directory."""
    directories = [Path(root)] if root else _roots(SHIPPED_MEASUREMENTS_DIR, MEASUREMENTS_DIR)
    out = []
    for directory in directories:
        if not directory.exists():
            continue
        for path in sorted(directory.rglob("*.yaml")):
            raw = yaml.safe_load(path.read_text()) or {}
            out.append(parse_measurement(raw, str(path)))
    return out


def load_systems(root: Optional[Path] = None) -> Dict[str, System]:
    """Shipped systems first, so a locally rewritten record wins on id — the
    machine you are sitting at knows its own memory better than a file that
    shipped six weeks ago."""
    directories = [Path(root)] if root else _roots(SHIPPED_SYSTEMS_DIR, SYSTEMS_DIR)
    out = {}
    for directory in directories:
        if not directory.exists():
            continue
        for path in sorted(directory.glob("*.yaml")):
            raw = yaml.safe_load(path.read_text()) or {}
            raw.pop("schema", None)
            known = {f for f in System.__dataclass_fields__}
            s = System(**{k: v for k, v in raw.items() if k in known})
            out[s.id] = s
    return out


@dataclass(frozen=True)
class Summary:
    """Two streams, never merged.

    `solo` is what the machine can do. `observed` is what a request actually
    saw, busy box included. Reporting one number instead of both is how a
    ceiling quietly collapses under load.
    """
    system_id: str
    model_id: str
    metric: str
    solo_median: Optional[float]
    solo_samples: int
    observed_median: Optional[float]
    observed_samples: int
    failed_samples: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def summarise(measurements: List[Measurement], system_id: str,
              model_id: str, metric: str) -> Summary:
    rows = [m for m in measurements if m.system_id == system_id
            and subject_id(m) == model_id and m.metric == metric]
    ok = [m for m in rows if m.is_ok]
    failed = [m for m in rows if not m.is_ok]
    solo = [m.value for m in ok if m.is_solo]
    return Summary(
        system_id=system_id,
        model_id=model_id,
        metric=metric,
        solo_median=statistics.median(solo) if solo else None,
        solo_samples=len(solo),
        observed_median=statistics.median([m.value for m in ok]) if ok else None,
        observed_samples=len(ok),
        failed_samples=len(failed),
    )
