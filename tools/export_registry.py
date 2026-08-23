#!/usr/bin/env python3
"""Freeze the registry into static JSON for the public page.

The public page has no server behind it, so it cannot ask the compatibility
engine anything — it has to carry the data and re-apply the rule in the browser.
That means the rule exists in two languages, which is exactly how two answers
start disagreeing.

So the *constants* travel with the data. The JS reads the thresholds from here
rather than repeating them as literals, and a change to the reserve fraction or
the footprint bands moves both at once.

    python tools/export_registry.py [--out web/registry.json]
"""

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from spacepilot.device_probe import (  # noqa: E402
    MEMORY_RESERVE_FLOOR_BYTES, MEMORY_RESERVE_FRACTION,
)
from spacepilot.pluto.measurements import (  # noqa: E402
    load_measurements, load_systems, summarise,
)
from spacepilot.pluto.registry import load_registry  # noqa: E402
from spacepilot.pluto.services.compatibility import (  # noqa: E402
    FOOTPRINT_BANDS, PERMISSIVE_LICENSES, TIGHT_THRESHOLD,
)

# Fitted on one measured M1 Max, where it lands within 7 KB of what Metal
# reports. One machine is not a validation, so the page holds it at low
# confidence and says the exact figure needs the local app.
METAL_WORKING_SET_FRACTION = 0.78


def attach_measurements(models: list) -> int:
    """Fold the measurement store into the variants it describes.

    The public page used to carry only each variant's `speed:` block, which is
    curated prose — cited, declared, or estimated. Runs recorded by `pluto
    measure` land in `registry/measurements/` instead, keyed by system and
    metric, and nothing joined the two. So a variant could have a real timing
    on disk and still publish as having no speed data at all, which is what
    happened to every FLUX.2 Klein variant.

    Summaries stay two-streamed. `solo` is what the machine can do; `observed`
    includes runs that met a busy box. Collapsing them into one number is how a
    ceiling quietly disappears under load, so they travel separately and each
    carries its own sample count.
    """
    rows = load_measurements()
    if not rows:
        return 0

    # A record names the variant it ran; older ones only carry model_id, which
    # for those was set to the variant id.
    keyed: dict = {}
    for m in rows:
        keyed.setdefault(m.variant_id or m.model_id, []).append(m)

    attached = 0
    for model in models:
        for variant in model["variants"]:
            mine = keyed.get(variant["id"])
            if not mine:
                continue
            pairs = sorted({(m.system_id, m.metric) for m in mine})
            variant["measurements"] = [
                summarise(mine, system_id, variant["id"], metric).to_dict()
                for system_id, metric in pairs
            ]
            attached += 1
    return attached

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="web/registry.json")
    args = ap.parse_args()

    reg = load_registry()
    payload = {
        "generated": dt.date.today().isoformat(),
        "rules": {
            "memory_reserve_fraction": MEMORY_RESERVE_FRACTION,
            "memory_reserve_floor_bytes": MEMORY_RESERVE_FLOOR_BYTES,
            "metal_working_set_fraction": METAL_WORKING_SET_FRACTION,
            "tight_threshold": TIGHT_THRESHOLD,
            "footprint_bands": [[edge, label] for edge, label in FOOTPRINT_BANDS],
            "permissive_licenses": sorted(PERMISSIVE_LICENSES),
        },
        "models": [m.to_dict() for m in reg.models.values()],
    }
    measured_variants = attach_measurements(payload["models"])
    payload["systems"] = [s.to_dict() for s in load_systems().values()]

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=1, sort_keys=False) + "\n")

    variants = sum(len(m["variants"]) for m in payload["models"])
    measured = sum(1 for m in payload["models"] for v in m["variants"]
                   if any(s["source"] == "measured" for s in v["speed"]))
    print(f"{out}  {len(payload['models'])} models, {variants} variants, "
          f"{measured} with a cited speed, {measured_variants} with measured runs "
          f"({out.stat().st_size / 1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
