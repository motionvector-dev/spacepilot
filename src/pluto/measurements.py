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
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import os
import platform
import re
import statistics
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

SCHEMA_VERSION = 1

_ROOT = Path(__file__).resolve().parents[2]
SYSTEMS_DIR = _ROOT / "registry" / "systems"
MEASUREMENTS_DIR = _ROOT / "registry" / "measurements"

# Reuse the model registry's vocabulary rather than inventing a parallel one.
from src.pluto.registry import SPEED_METRICS, BACKENDS  # noqa: E402

CONTENTION = {
    "solo",     # nothing else meaningful was running
    "loaded",   # something else was competing for CPU, GPU or memory
    "unknown",  # could not sample; treated as `loaded` by every summary
}

# Above this 1-minute load average per core the box is not idle. Deliberately
# low: the cost of calling a busy machine idle is a permanently wrong ceiling,
# and the cost of calling an idle machine busy is one discarded sample.
_LOAD_PER_CORE_IDLE = 0.4


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


@dataclass(frozen=True)
class Measurement:
    """One run, on one machine, with the knobs it was given."""
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
    quantisation: Optional[str] = None
    backend: Optional[str] = None
    interpreter: Optional[str] = None
    peak_memory_bytes: Optional[int] = None
    wall_seconds: Optional[float] = None
    knobs: Dict[str, Any] = field(default_factory=dict)
    note: Optional[str] = None

    @property
    def is_solo(self) -> bool:
        return self.contention == "solo"

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v not in (None, {}, [])}


def sample_contention(profile: Optional[Any] = None) -> str:
    """Ask the OS whether this machine is busy, rather than asking the caller.

    Load average is a blunt instrument and says nothing about GPU contention,
    so this can call a GPU-saturated box `solo`. It is still better than a
    self-report, and a wrong answer here degrades a sample rather than a
    conclusion — summaries report the two streams separately and never merge
    them.
    """
    try:
        one_minute = os.getloadavg()[0]
    except (OSError, AttributeError):
        return "unknown"
    cores = os.cpu_count() or 1
    return "solo" if (one_minute / cores) <= _LOAD_PER_CORE_IDLE else "loaded"


def system_id_for(profile: Any) -> str:
    """A stable id for a configuration: chip plus memory, both of which matter."""
    chip = profile.chip or profile.machine_model or platform.machine() or "unknown"
    gib = round((profile.memory_total_bytes or 0) / (1024 ** 3))
    return _slug(f"{chip}-{gib}gb") if gib else _slug(chip)


def _fingerprint() -> Optional[str]:
    """Truncated salted digest of the hostname. Dedupes boxes, names nobody."""
    try:
        host = platform.node()
    except Exception:
        return None
    if not host:
        return None
    salt = os.environ.get("PLUTO_FINGERPRINT_SALT", "pluto-measurements-v1")
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


def record(
    *,
    system: System,
    model_id: str,
    metric: str,
    value: float,
    contention: Optional[str] = None,
    root: Optional[Path] = None,
    **fields: Any,
) -> Path:
    """Append one observation. Contention is sampled unless explicitly passed."""
    if metric not in SPEED_METRICS:
        raise MeasurementError(f"metric {metric!r} not one of {sorted(SPEED_METRICS)}")
    state = contention or sample_contention()
    if state not in CONTENTION:
        raise MeasurementError(f"contention {state!r} not one of {sorted(CONTENTION)}")

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
    known = {f for f in Measurement.__dataclass_fields__}
    return Measurement(**{k: v for k, v in raw.items() if k in known})


def load_measurements(root: Optional[Path] = None) -> List[Measurement]:
    directory = root or MEASUREMENTS_DIR
    if not directory.exists():
        return []
    out = []
    for path in sorted(directory.rglob("*.yaml")):
        raw = yaml.safe_load(path.read_text()) or {}
        out.append(parse_measurement(raw, str(path)))
    return out


def load_systems(root: Optional[Path] = None) -> Dict[str, System]:
    directory = root or SYSTEMS_DIR
    if not directory.exists():
        return {}
    out = {}
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

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def summarise(measurements: List[Measurement], system_id: str,
              model_id: str, metric: str) -> Summary:
    rows = [m for m in measurements if m.system_id == system_id
            and m.model_id == model_id and m.metric == metric]
    solo = [m.value for m in rows if m.is_solo]
    return Summary(
        system_id=system_id,
        model_id=model_id,
        metric=metric,
        solo_median=statistics.median(solo) if solo else None,
        solo_samples=len(solo),
        observed_median=statistics.median([m.value for m in rows]) if rows else None,
        observed_samples=len(rows),
    )
