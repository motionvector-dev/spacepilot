"""The model registry: one file per model, one entry per downloadable variant.

Everything that needs to know about a model — the CLI, the MCP server, the
onboarding page, the compatibility engine — resolves against this. Adding a
model means adding a file, not editing code.

Numbers carry their provenance. `download_bytes` measured against the Hub API
and `working_set_bytes` guessed from a multiplier are both useful, but they are
not the same kind of fact, and a reader has to be able to tell them apart. The
schema makes stating the source mandatory so no estimate can quietly pass as a
measurement.

`revision` extends that idea from the numbers to the weights. A repo id names a
moving target: the Hub lets an author force-push, re-upload, or land a new
commit on main, and every one of those silently changes what `repo:` resolves
to. A measurement that says "flux2-klein-4b-4bit took 23.4s" then describes
weights nobody can fetch again, which makes it a bare number wearing a label —
exactly what the `source` rule exists to forbid.

So a variant may pin `revision:` to a commit SHA or an immutable tag. It is
**optional but never silent**: an unpinned variant reports `is_pinned: false`
through `to_dict()`, `Registry.unpinned()` names every one of them, and
`tools/verify_registry.py` fails on them unless explicitly waived. Optional,
because a variant has to be describable the day it is added and before anyone
has resolved a SHA for it; visible, because an unpinned variant that reads like
a pinned one is worse than no field at all. A moving ref (`main`, `master`,
`HEAD`, a branch) is rejected outright — it looks like a pin and is not one.
"""

from __future__ import annotations

import datetime as _dt
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from spacepilot.paths import shipped_dir

SCHEMA_VERSION = 1

# Shipped catalogue: read-only package data, resolved by the package rather
# than by walking up from __file__ (which pointed at site-packages/ once
# installed, where nothing was).
REGISTRY_DIR = shipped_dir("models")

# `speech` is text going in and audio coming out; `transcription` is the
# other direction. They are different capabilities with different runtimes,
# so they are different kinds rather than one "audio" bucket.
# `embedding` is text in, vector out. It is not `text`: nothing generates,
# nothing streams, and the useful measurement is how fast a corpus is
# consumed rather than how fast tokens come back.
KINDS = {"video", "image", "audio", "speech", "transcription", "text", "vision",
         "embedding"}
BACKENDS = {"metal", "cuda", "rocm", "cpu"}

# How a number came to be here. Ordered weakest to strongest.
SOURCES = {
    "declared",        # the model card says so
    "estimated",       # we derived it from a rule; note must say which
    "huggingface-api", # summed from the Hub's file metadata
    "measured",        # somebody ran it and wrote down what happened
}

# Refs that move. Accepting one of these as a `revision:` would be worse than
# leaving the field empty: the file would read as pinned, `is_pinned` would say
# true, and the weights behind it would still change under the next force-push.
MOVING_REFS = {"main", "master", "head", "latest", "default"}

_SHA_RE = re.compile(r"^[0-9a-f]{40}$")

# What an optimisation did to a named capability. `license.restrictions` exists
# because "SOTA but you may not ship it" belongs in a machine-readable field;
# this is the same idea one layer down — "fast but the word timestamps were
# never trained" is a fact about the weights that no size, licence or speed
# number can carry.
#
# Deliberately four words and a mandatory sentence. The failure mode being
# fixed is a variant that reads as a drop-in replacement for the model it was
# derived from, so what matters is that a caveat cannot be added without saying
# what it costs.
CAVEAT_STATUSES = {
    "preserved",   # the derived variant keeps this capability
    "degraded",    # measurably worse, still usable; detail must say how much
    "untrained",   # inherited from the parent, never trained for; unvalidated
    "absent",      # not implemented at all on this path
}

# A caveat is qualitative evidence, not a performance measurement.  Its
# provenance makes clear whether the statement came from a run here, a
# reproducible inference, or the publisher; a sourced sentence is still
# required in `detail` either way.
CAVEAT_PROVENANCES = {"measured", "inferred", "declared"}

# Capability names are a small, shared taxonomy rather than prose.  The
# aliases below are deliberately exact: accepting arbitrary punctuation or
# case changes would turn a typo into a different fact silently.
CAVEAT_CAPABILITIES = {
    "audio.transcription",
    "audio.transcription-accuracy",
    "audio.word-timestamps",
    "image.text-rendering",
    "video.temporal-consistency",
    "video.motion-amount",
}
CAVEAT_CAPABILITY_ALIASES = {
    "transcription": "audio.transcription",
    "transcription_accuracy": "audio.transcription-accuracy",
    "word_timestamps": "audio.word-timestamps",
}

SPEED_METRICS = {
    "tokens_per_second",
    "seconds_per_image",
    "seconds_per_second_of_video",
    "realtime_factor",
    # The warm-aware scheduler scores price + (cold ? load_seconds * value_of_latency
    # : 0) ("SpacePilot is an exchange, not a router", 2026-08-23; archived in
    # ~/code/motionvector/handoffs/DECISION-INBOX.md, planned in
    # docs/BUILD-PLAN.md Phase 3) — load_seconds has to be its own measured
    # metric, not folded
    # into a generation-speed number, because it is what makes a cold substrate
    # expensive even when its compute is cheap.
    "load_seconds",
    # Energy-per-unit, added 2026-09-10 alongside tools/fly.py's power
    # sampler. One metric per role shape rather than one generic "joules"
    # number, because the unit an executor produces (a token) is not the
    # unit an STT/audio role produces (a second of audio) is not the unit a
    # classify/drafter role produces (an item) — dividing joules by the
    # wrong denominator silently produces a number that looks comparable
    # across roles and is not.
    "joules_per_token",
    "joules_per_second_of_audio",
    "joules_per_item",
}


class RegistryError(ValueError):
    """A registry file is wrong. Always names the file and the field."""


@dataclass(frozen=True)
class Fact:
    """A number and where it came from."""
    value: float
    source: str
    checked: Optional[str] = None
    note: Optional[str] = None

    @property
    def is_measured(self) -> bool:
        return self.source in ("measured", "huggingface-api")

    def to_dict(self) -> Dict[str, Any]:
        return {"value": self.value, "source": self.source,
                "checked": self.checked, "note": self.note,
                "is_measured": self.is_measured}


@dataclass(frozen=True)
class Speed:
    """One machine's measured throughput. The corpus everyone else lacks.

    `power_source` / `power_watts` / `power_limits` are optional and travel
    together: they name which sampler produced the wattage a `joules_per_*`
    entry was computed from (see tools/fly.py's `sample_power`), the
    instantaneous reading itself, and that source's own stated limitations
    (e.g. "ioreg AppleSmartBattery only reports a number on battery power").
    Every speed entry written before 2026-09-10 has none of these three
    keys and parses unchanged — absent, not false, is what an entry with no
    power sample behind it should read as.
    """
    device: str
    backend: str
    metric: str
    value: float
    source: str
    measured_on: Optional[str] = None
    note: Optional[str] = None
    power_source: Optional[str] = None
    power_watts: Optional[float] = None
    power_limits: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return dict(self.__dict__)


@dataclass(frozen=True)
class Caveat:
    """One capability, what an optimisation did to it, and in what way."""
    capability: str
    status: str
    detail: str
    provenance: str
    metric: Optional[str] = None
    method: Optional[str] = None

    @property
    def is_safe(self) -> bool:
        return self.status == "preserved"

    def to_dict(self) -> Dict[str, Any]:
        d = dict(self.__dict__)
        d["is_safe"] = self.is_safe
        return d


@dataclass(frozen=True)
class License:
    id: str
    open_source: bool
    spdx: Optional[str] = None
    url: Optional[str] = None
    restrictions: List[str] = field(default_factory=list)

    @property
    def is_permissive(self) -> bool:
        return self.open_source and not self.restrictions

    def to_dict(self) -> Dict[str, Any]:
        d = dict(self.__dict__)
        d["is_permissive"] = self.is_permissive
        return d


@dataclass(frozen=True)
class Variant:
    """One thing you can actually download and run."""
    id: str
    model_id: str
    name: str
    kind: str
    family: str
    license: License
    repo: str
    files: Optional[List[str]]          # None means the whole repo
    backends: List[str]
    download: Fact
    working_set: Fact
    params: Optional[str] = None
    precision: Optional[str] = None
    # The exact weights this row describes. None means the row points at
    # whatever `repo:` resolves to today, which is not reproducible — see
    # `is_pinned`, which is what makes that visible rather than silent.
    revision: Optional[str] = None
    speed: List[Speed] = field(default_factory=list)
    caveats: List[Caveat] = field(default_factory=list)
    notes: Optional[str] = None

    @property
    def compromised(self) -> List[str]:
        """Capabilities this variant does not fully carry. Empty is the normal case."""
        return [c.capability for c in self.caveats if not c.is_safe]

    @property
    def is_pinned(self) -> bool:
        return bool(self.revision)

    def speed_for(self, device: str) -> Optional[Speed]:
        for s in self.speed:
            if s.device.lower() == device.lower():
                return s
        return None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id, "model_id": self.model_id, "name": self.name,
            "kind": self.kind, "family": self.family, "params": self.params,
            "precision": self.precision, "repo": self.repo, "files": self.files,
            "revision": self.revision, "is_pinned": self.is_pinned,
            "backends": list(self.backends),
            "download": self.download.to_dict(),
            "working_set": self.working_set.to_dict(),
            "license": self.license.to_dict(),
            "speed": [s.to_dict() for s in self.speed],
            "caveats": [c.to_dict() for c in self.caveats],
            "compromised": self.compromised,
            "notes": self.notes,
        }


@dataclass(frozen=True)
class Model:
    id: str
    name: str
    family: str
    kind: str
    license: License
    variants: List[Variant]
    summary: Optional[str] = None
    homepage: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id, "name": self.name, "family": self.family,
            "kind": self.kind, "summary": self.summary, "homepage": self.homepage,
            "license": self.license.to_dict(),
            "variants": [v.to_dict() for v in self.variants],
        }


# --------------------------------------------------------------------- parse

def _require(d: Dict[str, Any], key: str, where: str) -> Any:
    if key not in d or d[key] is None:
        raise RegistryError(f"{where}: missing required field '{key}'")
    return d[key]


def _fact(raw: Any, where: str) -> Fact:
    if not isinstance(raw, dict):
        raise RegistryError(
            f"{where}: must be a mapping with 'value' and 'source', not a bare number — "
            f"a number without a source cannot be told apart from a guess")
    value = _require(raw, "value", where)
    source = _require(raw, "source", where)
    if source not in SOURCES:
        raise RegistryError(f"{where}: source '{source}' not one of {sorted(SOURCES)}")
    if source == "estimated" and not raw.get("note"):
        raise RegistryError(f"{where}: an estimate must carry a 'note' saying how it was derived")
    if source in ("huggingface-api", "measured") and not raw.get("checked"):
        raise RegistryError(f"{where}: source '{source}' must carry the date it was 'checked'")
    return Fact(float(value), source, raw.get("checked"), raw.get("note"))


def _revision(raw: Any, where: str) -> Optional[str]:
    """Validate a `revision:`. Absent is allowed; a moving ref is not.

    The only two things that pin weights are a commit SHA and an immutable
    tag. A branch name resolves to something different tomorrow while looking
    exactly as authoritative as a SHA in the file, so it is rejected rather
    than accepted with a warning nobody reads.
    """
    if raw is None:
        return None
    rev = str(raw).strip()
    if not rev:
        raise RegistryError(
            f"{where}: revision is empty — omit the field entirely rather than "
            f"writing a blank one, so the variant reads as unpinned")
    if rev.lower() in MOVING_REFS or rev.startswith("refs/heads/"):
        raise RegistryError(
            f"{where}: revision '{rev}' is a moving ref, not a pin — it resolves "
            f"to different weights after any push. Use the commit SHA it points "
            f"at today, or leave the field out so the variant reads as unpinned")
    if len(rev) == 40 and not _SHA_RE.match(rev):
        raise RegistryError(
            f"{where}: revision '{rev}' is 40 characters but not a hex SHA")
    return rev


def _license(raw: Dict[str, Any], where: str) -> License:
    return License(
        id=str(_require(raw, "id", where)),
        open_source=bool(_require(raw, "open_source", where)),
        spdx=raw.get("spdx"),
        url=raw.get("url"),
        restrictions=list(raw.get("restrictions") or []),
    )


def _speed(raw: Dict[str, Any], where: str) -> Speed:
    metric = _require(raw, "metric", where)
    if metric not in SPEED_METRICS:
        raise RegistryError(f"{where}: metric '{metric}' not one of {sorted(SPEED_METRICS)}")
    source = _require(raw, "source", where)
    if source not in SOURCES:
        raise RegistryError(f"{where}: source '{source}' not one of {sorted(SOURCES)}")
    power_watts = raw.get("power_watts")
    return Speed(
        device=str(_require(raw, "device", where)),
        backend=str(_require(raw, "backend", where)),
        metric=metric,
        value=float(_require(raw, "value", where)),
        source=source,
        measured_on=raw.get("measured_on"),
        note=raw.get("note"),
        power_source=raw.get("power_source"),
        power_watts=float(power_watts) if power_watts is not None else None,
        power_limits=raw.get("power_limits"),
    )


def _caveat(raw: Dict[str, Any], where: str) -> Caveat:
    """Parse one capability caveat. A status with no detail is refused.

    `status: degraded` on its own tells a reader that something is worse and
    nothing about whether it matters to them. The sentence is the whole value
    of the field, so it is required rather than encouraged.
    """
    if not isinstance(raw, dict):
        raise RegistryError(
            f"{where}: must be a mapping with 'capability', 'status', 'detail' and 'provenance'")
    capability = str(_require(raw, "capability", where)).strip()
    capability = CAVEAT_CAPABILITY_ALIASES.get(capability, capability)
    if capability not in CAVEAT_CAPABILITIES:
        raise RegistryError(
            f"{where}: capability '{raw['capability']}' is not one of "
            f"{sorted(CAVEAT_CAPABILITIES)}")
    status = str(_require(raw, "status", where))
    if status not in CAVEAT_STATUSES:
        raise RegistryError(f"{where}: status '{status}' not one of {sorted(CAVEAT_STATUSES)}")
    provenance = str(_require(raw, "provenance", where))
    if provenance not in CAVEAT_PROVENANCES:
        raise RegistryError(
            f"{where}: provenance '{provenance}' not one of {sorted(CAVEAT_PROVENANCES)}")
    detail = str(raw.get("detail") or "").strip()
    if not detail:
        raise RegistryError(
            f"{where}: a caveat must say what the effect is — a bare status "
            f"tells a reader something changed and nothing about whether it matters")
    optional = {}
    for key in ("metric", "method"):
        value = raw.get(key)
        if value is not None:
            value = str(value).strip()
            if not value:
                raise RegistryError(f"{where}: {key} must be a non-empty string when present")
        optional[key] = value
    return Caveat(capability, status, detail, provenance, **optional)


def parse_model(raw: Dict[str, Any], where: str) -> Model:
    schema = raw.get("schema")
    if schema != SCHEMA_VERSION:
        raise RegistryError(f"{where}: schema is {schema!r}, this build reads {SCHEMA_VERSION}")

    model_id = str(_require(raw, "id", where))
    kind = str(_require(raw, "kind", where))
    if kind not in KINDS:
        raise RegistryError(f"{where}: kind '{kind}' not one of {sorted(KINDS)}")

    lic = _license(_require(raw, "license", where), f"{where}.license")
    family = str(_require(raw, "family", where))

    variants: List[Variant] = []
    raw_variants = _require(raw, "variants", where)
    if not raw_variants:
        raise RegistryError(f"{where}: needs at least one variant")

    for i, rv in enumerate(raw_variants):
        vid = str(_require(rv, "id", f"{where}.variants[{i}]"))
        vw = f"{where}.variants[{vid}]"
        backends = list(_require(rv, "backends", vw))
        bad = set(backends) - BACKENDS
        if bad:
            raise RegistryError(f"{vw}: unknown backends {sorted(bad)}")
        variants.append(Variant(
            id=vid,
            model_id=model_id,
            name=str(_require(rv, "name", vw)),
            kind=kind,
            family=family,
            license=_license(rv["license"], f"{vw}.license") if rv.get("license") else lic,
            repo=str(_require(rv, "repo", vw)),
            files=list(rv["files"]) if rv.get("files") else None,
            backends=backends,
            download=_fact(_require(rv, "download", vw), f"{vw}.download"),
            working_set=_fact(_require(rv, "working_set", vw), f"{vw}.working_set"),
            params=rv.get("params"),
            precision=rv.get("precision"),
            revision=_revision(rv.get("revision"), f"{vw}.revision"),
            speed=[_speed(s, f"{vw}.speed[{j}]") for j, s in enumerate(rv.get("speed") or [])],
            caveats=[_caveat(c, f"{vw}.caveats[{j}]") for j, c in enumerate(rv.get("caveats") or [])],
            notes=rv.get("notes"),
        ))

    return Model(
        id=model_id,
        name=str(_require(raw, "name", where)),
        family=family,
        kind=kind,
        license=lic,
        variants=variants,
        summary=raw.get("summary"),
        homepage=raw.get("homepage"),
    )


# ------------------------------------------------------------------ registry

@dataclass
class Registry:
    models: Dict[str, Model]

    @property
    def variants(self) -> List[Variant]:
        return [v for m in self.models.values() for v in m.variants]

    def variant(self, variant_id: str) -> Optional[Variant]:
        for v in self.variants:
            if v.id == variant_id:
                return v
        return None

    def model(self, model_id: str) -> Optional[Model]:
        return self.models.get(model_id)

    def unpinned(self) -> List[Variant]:
        """Every variant whose weights can change under it.

        Callers use this to make the gap loud — the release gate fails on a
        non-empty list, the export carries the count. An unpinned variant is
        allowed; an unpinned variant nobody can see is not.
        """
        return [v for v in self.variants if not v.is_pinned]

    def by_kind(self, kind: str) -> List[Variant]:
        return [v for v in self.variants if v.kind == kind]

    def to_dict(self) -> Dict[str, Any]:
        return {"schema": SCHEMA_VERSION,
                "models": [m.to_dict() for m in self.models.values()]}


def load_registry(directory: Path | str | None = None) -> Registry:
    """Read every model file. Raises on the first bad one rather than skipping it —
    a registry that silently drops entries is worse than one that will not load."""
    d = Path(directory or REGISTRY_DIR)
    if not d.is_dir():
        raise RegistryError(f"registry directory not found: {d}")

    models: Dict[str, Model] = {}
    seen_variants: Dict[str, str] = {}

    for path in sorted(d.glob("*.yaml")) + sorted(d.glob("*.yml")):
        try:
            raw = yaml.safe_load(path.read_text())
        except yaml.YAMLError as e:
            raise RegistryError(f"{path.name}: not valid YAML — {e}") from e
        model = parse_model(raw, path.name)

        if model.id in models:
            raise RegistryError(f"{path.name}: duplicate model id '{model.id}'")
        for v in model.variants:
            if v.id in seen_variants:
                raise RegistryError(
                    f"{path.name}: variant id '{v.id}' already used by {seen_variants[v.id]}")
            seen_variants[v.id] = path.name
        models[model.id] = model

    if not models:
        raise RegistryError(f"no model files in {d}")
    return Registry(models)


_cache: Optional[Registry] = None


def registry() -> Registry:
    global _cache
    if _cache is None:
        _cache = load_registry()
    return _cache


def reload() -> Registry:
    global _cache
    _cache = None
    return registry()
