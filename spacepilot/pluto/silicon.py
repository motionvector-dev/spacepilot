"""Silicon: the hardware that exists, as opposed to the hardware we have probed.

`systems/` records machines this project actually measured. This records parts
you could buy, or will be able to. They answer different questions and the split
matters: a probe tells you what one box turned out to be, this tells you what the
scheduler might one day be asked to route to.

Nothing here is measured. Every figure is something a vendor published or a named
report claimed, so every figure carries its source and the date it was read. A
roadmap read six months ago and a spec page read today look identical on the
page and are not the same kind of fact.

Two rules follow from that, and the loader enforces both:

  - A bare number will not load. `bandwidth_bytes_per_sec: 819000000000` is
    refused; the value needs a source beside it.
  - `declared` and `reported` both require a `checked` date and a `url`. An
    undated vendor claim is a rumour with better clothes.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from spacepilot.paths import shipped_dir

SCHEMA_VERSION = 1
SILICON_DIR = shipped_dir("silicon")

# What a part IS. A box is a whole machine you can buy; an accelerator is a part
# that goes in someone else's machine. The distinction is not pedantry — you can
# own a box, you can only rent time on most accelerators.
KINDS = {"accelerator", "box", "memory", "client-soc"}

# How the compute is reached. This is deliberately wider than the probe's own
# backend list: the point of this file is to name paths we cannot yet route to.
COMPUTE_PATHS = {
    "cuda", "rocm", "hip", "metal", "vulkan", "sycl", "openvino",
    "opencl", "webgpu", "webnn", "directml", "cann", "npu", "cpu",
}

# How memory is arranged, because "how much memory" has a different answer per
# architecture and the fit check cannot be written without knowing which.
MEMORY_MODELS = {
    "discrete",       # its own VRAM, separate from system RAM
    "unified",        # CPU and GPU share all of it (Apple)
    "partitionable",  # shared, but a slice is assignable as VRAM (Ryzen AI Max)
    "coherent",       # shared across heterogeneous cores (Grace Blackwell)
    "near-memory",    # compute sited next to the memory array
}

# Where a claim came from. No `measured` here on purpose: a measurement belongs
# in the corpus with the machine that produced it, not in a catalogue of parts.
SOURCES = {
    "declared",  # the vendor published it
    "reported",  # a named publication claimed it; the vendor has not confirmed
}

# Whether you can buy it. `prototype` and `roadmap` are not the same: one has
# been shown working, the other is a date on a slide.
AVAILABILITY = {"shipping", "sampling", "announced", "prototype", "roadmap"}


class SiliconError(ValueError):
    """A silicon file is wrong. Always names the file and the field."""


@dataclass(frozen=True)
class Claim:
    """One number, and where it came from."""

    value: float
    source: str
    checked: str
    url: str
    note: Optional[str] = None

    @property
    def is_vendor(self) -> bool:
        return self.source == "declared"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "value": self.value,
            "source": self.source,
            "checked": self.checked,
            "url": self.url,
            "note": self.note,
            "is_vendor": self.is_vendor,
        }


@dataclass(frozen=True)
class Part:
    id: str
    name: str
    vendor: str
    kind: str
    availability: str
    summary: str
    compute_paths: tuple
    memory_model: Optional[str] = None
    memory_bytes: Optional[Claim] = None
    bandwidth_bytes_per_sec: Optional[Claim] = None
    npu_tops: Optional[Claim] = None
    power_watts: Optional[Claim] = None
    price_usd: Optional[Claim] = None
    note: Optional[str] = None

    @property
    def is_buyable(self) -> bool:
        return self.availability == "shipping"

    def to_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {
            "id": self.id,
            "name": self.name,
            "vendor": self.vendor,
            "kind": self.kind,
            "availability": self.availability,
            "summary": self.summary,
            "compute_paths": list(self.compute_paths),
            "memory_model": self.memory_model,
            "is_buyable": self.is_buyable,
            "note": self.note,
        }
        for field_name in (
            "memory_bytes", "bandwidth_bytes_per_sec",
            "npu_tops", "power_watts", "price_usd",
        ):
            claim = getattr(self, field_name)
            out[field_name] = claim.to_dict() if claim else None
        return out


def _req(raw: Dict[str, Any], key: str, where: str) -> Any:
    if key not in raw:
        raise SiliconError(f"{where}: missing required field '{key}'")
    return raw[key]


def _claim(raw: Any, where: str) -> Claim:
    """Parse one sourced number.

    A bare number is refused rather than assumed. Every figure in this registry
    is somebody's claim, and a value without its source cannot be weighed
    against one that has it.
    """
    if not isinstance(raw, dict):
        raise SiliconError(
            f"{where}: expected a value with its source, got a bare "
            f"{type(raw).__name__}. Write "
            f"'{{value: N, source: declared, checked: YYYY-MM-DD, url: ...}}'"
        )

    source = _req(raw, "source", where)
    if source not in SOURCES:
        raise SiliconError(
            f"{where}: unknown source {source!r}, expected one of {sorted(SOURCES)}"
        )

    # Both source kinds need a date and a link. A vendor page changes without
    # notice and a report is only as good as the day it was written.
    checked = _req(raw, "checked", where)
    if not isinstance(checked, str) or len(checked) != 10 or checked[4] != "-":
        raise SiliconError(
            f"{where}: 'checked' must be an ISO date (YYYY-MM-DD), got {checked!r}"
        )
    url = _req(raw, "url", where)
    if not isinstance(url, str) or not url.startswith("https://"):
        raise SiliconError(f"{where}: 'url' must be an https link, got {url!r}")

    value = _req(raw, "value", where)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SiliconError(f"{where}: 'value' must be a number, got {value!r}")

    return Claim(
        value=float(value),
        source=source,
        checked=checked,
        url=url,
        note=raw.get("note"),
    )


def parse_part(raw: Dict[str, Any], where: str) -> Part:
    schema = _req(raw, "schema", where)
    if schema != SCHEMA_VERSION:
        raise SiliconError(f"{where}: schema {schema!r}, expected {SCHEMA_VERSION}")

    kind = _req(raw, "kind", where)
    if kind not in KINDS:
        raise SiliconError(f"{where}: unknown kind {kind!r}, expected one of {sorted(KINDS)}")

    availability = _req(raw, "availability", where)
    if availability not in AVAILABILITY:
        raise SiliconError(
            f"{where}: unknown availability {availability!r}, "
            f"expected one of {sorted(AVAILABILITY)}"
        )

    paths = list(_req(raw, "compute_paths", where))
    unknown = set(paths) - COMPUTE_PATHS
    if unknown:
        raise SiliconError(f"{where}: unknown compute paths {sorted(unknown)}")

    memory_model = raw.get("memory_model")
    if memory_model is not None and memory_model not in MEMORY_MODELS:
        raise SiliconError(
            f"{where}: unknown memory_model {memory_model!r}, "
            f"expected one of {sorted(MEMORY_MODELS)}"
        )

    claims: Dict[str, Optional[Claim]] = {}
    for field_name in (
        "memory_bytes", "bandwidth_bytes_per_sec",
        "npu_tops", "power_watts", "price_usd",
    ):
        value = raw.get(field_name)
        claims[field_name] = _claim(value, f"{where}.{field_name}") if value is not None else None

    return Part(
        id=_req(raw, "id", where),
        name=_req(raw, "name", where),
        vendor=_req(raw, "vendor", where),
        kind=kind,
        availability=availability,
        summary=_req(raw, "summary", where),
        compute_paths=tuple(paths),
        memory_model=memory_model,
        note=raw.get("note"),
        **claims,
    )


def load_silicon(directory: Optional[Path] = None) -> Dict[str, Part]:
    """Every part file in a directory.

    Raises on the first bad one rather than skipping it — a registry that
    silently drops entries is worse than one that will not load.
    """
    root = Path(directory) if directory else SILICON_DIR
    parts: Dict[str, Part] = {}

    for path in sorted(root.glob("*.yaml")):
        try:
            raw = yaml.safe_load(path.read_text())
        except yaml.YAMLError as exc:
            raise SiliconError(f"{path.name}: not valid YAML — {exc}") from exc
        if not isinstance(raw, dict):
            raise SiliconError(f"{path.name}: expected a mapping at the top level")

        part = parse_part(raw, path.name)
        if part.id in parts:
            raise SiliconError(f"{path.name}: duplicate part id {part.id!r}")
        parts[part.id] = part

    if not parts:
        raise SiliconError(f"{root}: no silicon files found; a registry cannot be empty")
    return parts


_cache: Optional[Dict[str, Part]] = None


def silicon() -> Dict[str, Part]:
    global _cache
    if _cache is None:
        _cache = load_silicon()
    return _cache


def reload() -> Dict[str, Part]:
    global _cache
    _cache = None
    return silicon()
