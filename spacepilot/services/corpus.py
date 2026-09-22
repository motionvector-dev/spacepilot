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


def known_variant_ids() -> List[str]:
    """Every variant id a caller may legitimately filter on.

    A registry entry with nothing measured yet is known; so is an old or
    external measurement whose variant the registry no longer describes.
    Anything else is a typo, and an empty result would hide that.
    """
    known = set(_registry_variants())
    known.update(ms.subject_id(record) for record in _load_measurements())
    return sorted(known)


def known_system_ids() -> List[str]:
    """Every system id a caller may legitimately filter on."""
    try:
        systems = ms.load_systems()
    except (OSError, ValueError) as exc:
        raise CorpusReadError(f"systems could not be read: {exc}") from exc
    known = set(systems)
    known.update(record.system_id for record in _load_measurements())
    return sorted(known)


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


UNMEASURED_REASON = "no measurements recorded yet for this system"

# What `source` means, so "unmeasured" and "policy_undecided" are never
# collapsed into the same bare `null` a caller has to guess at. Both refuse a
# run, but for different reasons a person reads differently: one clears the
# next time this model runs anywhere, the other clears only when Saurabh
# decides who pays for an external caller's inference (docs/DECISION-INBOX.md).
SOURCES = {"measured", "unmeasured", "policy_undecided"}


def throughput_estimate(records: List[ms.Measurement], system_id: str, variant_id: str) -> dict:
    """The model-selection card: a decode-speed median, not a per-request estimate.

    `decode_tokens_per_second` is a median of `record` calls that actually
    happened — never derived, never guessed. It says nothing about prompt
    processing time, which depends on the request; see `/v1/chat/completions`
    `dry_run` for the number a caller can actually refuse a run on.
    """
    summary = ms.summarise(records, system_id, variant_id, "tokens_per_second")
    samples = summary.solo_samples or summary.observed_samples
    if samples:
        median = summary.solo_median if summary.solo_samples else summary.observed_median
        return {
            "decode_tokens_per_second": median,
            "sample_count": samples,
            "cost_usd": 0.0,
            "source": "measured",
            "reason": None,
        }
    return {
        "decode_tokens_per_second": None,
        "sample_count": 0,
        "cost_usd": 0.0,
        "source": "unmeasured",
        "reason": UNMEASURED_REASON,
    }


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
