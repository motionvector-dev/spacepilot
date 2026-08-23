"""The model registry: one file per model, one entry per downloadable variant.

Everything that needs to know about a model — the CLI, the MCP server, the
onboarding page, the compatibility engine — resolves against this. Adding a
model means adding a file, not editing code.

Numbers carry their provenance. `download_bytes` measured against the Hub API
and `working_set_bytes` guessed from a multiplier are both useful, but they are
not the same kind of fact, and a reader has to be able to tell them apart. The
schema makes stating the source mandatory so no estimate can quietly pass as a
measurement.
"""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

SCHEMA_VERSION = 1

REGISTRY_DIR = Path(__file__).resolve().parents[2] / "registry" / "models"

KINDS = {"video", "image", "audio", "speech", "text", "vision"}
BACKENDS = {"metal", "cuda", "rocm", "cpu"}

# How a number came to be here. Ordered weakest to strongest.
SOURCES = {
    "declared",        # the model card says so
    "estimated",       # we derived it from a rule; note must say which
    "huggingface-api", # summed from the Hub's file metadata
    "measured",        # somebody ran it and wrote down what happened
}

SPEED_METRICS = {
    "tokens_per_second",
    "seconds_per_image",
    "seconds_per_second_of_video",
    "realtime_factor",
    # The warm-aware scheduler scores price + (cold ? load_seconds * value_of_latency
    # : 0) (docs/DECISION-INBOX.md, "SpacePilot is an exchange, not a router",
    # 2026-08-23) — load_seconds has to be its own measured metric, not folded
    # into a generation-speed number, because it is what makes a cold substrate
    # expensive even when its compute is cheap.
    "load_seconds",
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
    """One machine's measured throughput. The corpus everyone else lacks."""
    device: str
    backend: str
    metric: str
    value: float
    source: str
    measured_on: Optional[str] = None
    note: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return dict(self.__dict__)


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
    speed: List[Speed] = field(default_factory=list)
    notes: Optional[str] = None

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
            "backends": list(self.backends),
            "download": self.download.to_dict(),
            "working_set": self.working_set.to_dict(),
            "license": self.license.to_dict(),
            "speed": [s.to_dict() for s in self.speed],
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
    return Speed(
        device=str(_require(raw, "device", where)),
        backend=str(_require(raw, "backend", where)),
        metric=metric,
        value=float(_require(raw, "value", where)),
        source=source,
        measured_on=raw.get("measured_on"),
        note=raw.get("note"),
    )


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
            speed=[_speed(s, f"{vw}.speed[{j}]") for j, s in enumerate(rv.get("speed") or [])],
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
