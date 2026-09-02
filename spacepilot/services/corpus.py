"""Read-only views over the measured corpus for API and MCP consumers.

The corpus is deliberately read through the registry and measurement loaders,
never through a caller-supplied path.  That keeps the API useful to an agent
without turning it into a filesystem browser.
"""

from __future__ import annotations

from typing import Dict, Iterable, List, Optional

from spacepilot import measurements as ms
from spacepilot.model_registry import RegistryError, registry


class CorpusReadError(RuntimeError):
    """The shipped or local corpus could not be read truthfully."""


def _registry_variants() -> Dict[str, object]:
    try:
        return {variant.id: variant for variant in registry().variants}
    except (OSError, RegistryError, ValueError) as exc:
        raise CorpusReadError(f"model registry could not be read: {exc}") from exc


def _caveats(variant_id: str, variants: Dict[str, object]) -> List[dict]:
    variant = variants.get(variant_id)
    if variant is None:
        # An old or external measurement is still real.  Empty means no
        # registry entry describes its caveats; it never means preserved.
        return []
    return [caveat.to_dict() for caveat in variant.caveats]


def _load_measurements() -> List[ms.Measurement]:
    try:
        return ms.load_measurements()
    except (OSError, ValueError) as exc:
        raise CorpusReadError(f"measurements could not be read: {exc}") from exc


def measurement_payload() -> dict:
    """Every individual observation, with canonical variant and caveats."""
    variants = _registry_variants()
    measurements = []
    for measurement in _load_measurements():
        variant_id = ms.subject_id(measurement)
        item = measurement.to_dict()
        item["variant_id"] = variant_id
        item["provenance"] = "flown"
        item["caveats"] = _caveats(variant_id, variants)
        measurements.append(item)
    return {"measurements": measurements}


def systems_payload() -> dict:
    """System records written by the probe, with no caller-controlled path."""
    try:
        systems = ms.load_systems()
    except (OSError, ValueError) as exc:
        raise CorpusReadError(f"systems could not be read: {exc}") from exc
    return {
        "systems": [
            {"schema": ms.SCHEMA_VERSION, **system.to_dict()}
            for _id, system in sorted(systems.items())
        ]
    }


def _latest(rows: Iterable[ms.Measurement]) -> Optional[str]:
    return max((row.measured_on for row in rows), default=None)


def summary_payload(system_id: Optional[str] = None) -> dict:
    """Two-stream speed summaries, grouped by configuration and exact variant."""
    variants = _registry_variants()
    records = _load_measurements()
    groups = sorted({
        (record.system_id, ms.subject_id(record), record.metric)
        for record in records
        if system_id is None or record.system_id == system_id
    })
    summaries = []
    for group_system, variant_id, metric in groups:
        mine = [record for record in records
                if record.system_id == group_system
                and ms.subject_id(record) == variant_id
                and record.metric == metric]
        summary = ms.summarise(records, group_system, variant_id, metric).to_dict()
        summary.update({
            "variant_id": variant_id,
            "provenance": "flown",
            "solo_latest_on": _latest(record for record in mine if record.is_ok and record.is_solo),
            "observed_latest_on": _latest(record for record in mine if record.is_ok),
            "caveats": _caveats(variant_id, variants),
        })
        summaries.append(summary)
    return {"summaries": summaries}


def check_payload() -> dict:
    """The local machine's probe record and any corpus summaries for its class."""
    from spacepilot.device_probe import probe_local_device

    profile = probe_local_device()
    system = ms.system_from_profile(profile)
    return {
        "profile": profile.to_dict(),
        "system": {"schema": ms.SCHEMA_VERSION, **system.to_dict()},
        **summary_payload(system.id),
    }
