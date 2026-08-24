"""Render registry facts and local measurements without blurring how we know them.

The registry can contain useful paper claims before a machine has flown a
workload.  That does not make an estimate a number we may show as if it had
been measured.  This module is the single, deliberately small translation
layer used by CLI surfaces: rendering modes may change layout, never these
labels or the facts behind them.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional

from spacepilot.pluto.measurements import Measurement, summarise, subject_id
from spacepilot.pluto.registry import Fact, Speed


@dataclass(frozen=True)
class FactProvenance:
    state: str                  # flown | on paper | unflown
    source: str
    checked: Optional[str]
    value: Optional[float]


@dataclass(frozen=True)
class FlownSpeed:
    metric: str
    value: float
    stream: str                 # solo | observed
    samples: int
    latest_on: Optional[str]


def fact_provenance(fact: Fact) -> FactProvenance:
    """Classify a registry number according to the product vocabulary.

    Hub API metadata is a verifiable third-party declaration, not a benchmark
    performed on this machine, so it remains ``on paper``.  Estimates retain
    their source but deliberately omit their value from rendering callers.
    """
    if fact.source == "measured":
        return FactProvenance("flown", fact.source, fact.checked, fact.value)
    if fact.source in {"declared", "huggingface-api"}:
        return FactProvenance("on paper", fact.source, fact.checked, fact.value)
    return FactProvenance("unflown", fact.source, fact.checked, None)


def speed_provenance(speed: Speed) -> FactProvenance:
    """Apply the same labels to a registry ``speed:`` entry."""
    return fact_provenance(Fact(speed.value, speed.source, speed.measured_on, speed.note))


def local_speeds(
    measurements: Iterable[Measurement], *, system_id: str, variant_id: str,
) -> List[FlownSpeed]:
    """Summaries for exactly this system configuration and registry variant.

    A solo median is the clean performance ceiling.  When only non-solo runs
    exist, the observed median is still flown, but its stream is explicit so
    nobody reads a loaded-box result as the idle number.
    """
    mine = [m for m in measurements
            if m.system_id == system_id and subject_id(m) == variant_id]
    out: List[FlownSpeed] = []
    for metric in sorted({m.metric for m in mine}):
        summary = summarise(mine, system_id, variant_id, metric)
        solo_rows = [m for m in mine if m.metric == metric and m.is_ok and m.is_solo]
        observed_rows = [m for m in mine if m.metric == metric and m.is_ok]
        if summary.solo_median is not None:
            rows = solo_rows
            value = summary.solo_median
            stream = "solo"
            samples = summary.solo_samples
        elif summary.observed_median is not None:
            rows = observed_rows
            value = summary.observed_median
            stream = "observed"
            samples = summary.observed_samples
        else:
            continue
        latest = max((m.measured_on for m in rows), default=None)
        out.append(FlownSpeed(metric, value, stream, samples, latest))
    return out


def primary_speed(speeds: Iterable[FlownSpeed]) -> Optional[FlownSpeed]:
    """Choose a concise row label without calling load time generation speed."""
    items = list(speeds)
    if not items:
        return None
    items.sort(key=lambda s: (s.metric == "load_seconds", s.metric, s.stream != "solo"))
    return items[0]


def format_metric(metric: str, value: float) -> str:
    """A number with its unit; every supported measurement metric is explicit."""
    if metric == "realtime_factor":
        return f"{value:.1f}× realtime"
    if metric == "tokens_per_second":
        return f"{value:.1f} tokens/s"
    if metric == "seconds_per_image":
        return f"{value:.1f} s/image"
    if metric == "seconds_per_second_of_video":
        return f"{value:.1f} s/s video"
    if metric == "load_seconds":
        return f"{value:.1f} s load"
    return f"{value:.3g} {metric}"


def format_fact(fact: Fact, value_text: str) -> str:
    """Render a non-speed registry fact without ever printing an estimate."""
    evidence = fact_provenance(fact)
    if evidence.state == "unflown":
        return "unflown · estimated"
    date = evidence.checked or "date unrecorded"
    return f"{value_text} · {evidence.state} · {evidence.source} · checked {date}"


def format_local_speed(speed: Optional[FlownSpeed]) -> str:
    if speed is None:
        return "unflown"
    date = speed.latest_on or "date unrecorded"
    return (f"flown {format_metric(speed.metric, speed.value)} · {speed.stream} · "
            f"{speed.samples} sample{'s' if speed.samples != 1 else ''} · latest {date}")
