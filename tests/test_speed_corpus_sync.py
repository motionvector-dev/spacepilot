"""A model-file `speed:` entry that overlaps the measurement corpus is derived data.

The model registry carries hand-written speed blocks; the corpus carries what a
machine actually did. When both describe the same variant, metric and system,
the hand-written number has no independent authority — it is a copy, and a copy
that drifts is a lie with a citation. kokoro.yaml said 4.6 "measured
2026-08-22" while the corpus's newer record said 4.021 on 2026-08-23; this test
exists so that drift cannot recur silently.

Only `source: measured` entries are checked. Declared and vendor claims (CUDA
figures quoted from a model card) are cited third-party statements, not our
observations, and have nothing in the corpus to agree with.
"""

import datetime as dt
import math
from pathlib import Path

from spacepilot.pluto.measurements import (
    _slug,
    load_measurements,
    load_systems,
    subject_id,
)
from spacepilot.pluto.registry import load_registry

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "spacepilot" / "registry"


def _matching_system_id(device: str, system_ids) -> str | None:
    """Map a speed entry's device prose onto a corpus system id.

    The corpus names machines by id (`apple-m1-max-32gb`); the model file
    carries prose (`Apple M1 Max 32GB`). Slugging the prose reproduces the id
    when the prose includes memory, and a prefix of it when it names only the
    chip — the same slug the id was built from.
    """
    slug = _slug(device)
    for sid in system_ids:
        if sid == slug or sid.startswith(slug + "-"):
            return sid
    return None


def test_measured_speed_entries_match_the_corpus():
    """For every corpus-overlapping measured entry: value and date must agree.

    "Agree" means equal to the LATEST ok record for that system+variant+metric,
    not the median: the corpus is append-only and a re-run supersedes the run
    before it, so the number a model file quotes must be the most recent
    observation — a median would let a stale hand-copied value keep passing as
    long as an old sample anchored it. The entry's date must not predate the
    record it claims to summarise.
    """
    registry = load_registry(REGISTRY / "models")
    measurements = [m for m in load_measurements(REGISTRY / "measurements") if m.is_ok]
    systems = load_systems(REGISTRY / "systems")

    assert measurements, "corpus walk was vacuous: no ok measurement records found"

    latest = {}
    for m in measurements:
        key = (m.system_id, subject_id(m), m.metric)
        held = latest.get(key)
        if held is None or m.measured_on > held.measured_on:
            latest[key] = m

    checked = 0
    problems = []
    for variant in registry.variants:
        for entry in variant.speed:
            if entry.source != "measured":
                continue
            sid = _matching_system_id(entry.device, systems)
            if sid is None:
                continue
            record = latest.get((sid, variant.id, entry.metric))
            if record is None:
                continue
            checked += 1
            where = f"{variant.id} speed ({entry.device}, {entry.metric})"
            if not math.isclose(entry.value, record.value, rel_tol=1e-9):
                problems.append(
                    f"{where}: model file says {entry.value}, corpus's latest "
                    f"record says {record.value} ({record.measured_on}) — the "
                    f"entry is derived data and must be copied, not remembered"
                )
            if entry.measured_on:
                entry_date = dt.date.fromisoformat(entry.measured_on)
                record_date = dt.datetime.fromisoformat(record.measured_on).date()
                if entry_date < record_date:
                    problems.append(
                        f"{where}: dated {entry_date} but the record it must "
                        f"reflect was measured {record_date}"
                    )
    assert not problems, "\n".join(problems)
    assert checked, (
        "model-file walk was vacuous: no measured speed entry overlapped the "
        "corpus — kokoro-82m-onnx on apple-m1-max-32gb is expected to"
    )
