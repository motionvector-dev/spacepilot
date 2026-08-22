"""Decide whether a model can run on the machine in front of us.

Two questions, kept apart on purpose:

  * Can this machine ever run it?   -> capacity, a fixed property of the hardware
  * Can it run it right now?        -> headroom, which changes as apps open and close

Conflating them is why a laptop with 32 GB gets told a 4 GB model "doesn't fit"
because a browser happened to be open.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from src.device_probe import DeviceProfile, GIB, usable_memory_bytes

# A model held at "tight" is one that fits but leaves little room. Past this
# fraction of usable memory, expect swapping under real workloads.
TIGHT_THRESHOLD = 0.80

PERMISSIVE_LICENSES = {"apache-2.0", "mit", "bsd-3-clause", "cc0-1.0"}

FOOTPRINT_BANDS = ((0.20, "tiny"), (0.40, "light"), (0.60, "medium"), (0.80, "heavy"))


@dataclass
class Verdict:
    recipe_id: str
    verdict: str            # fits | tight | wont_fit | blocked | unknown
    reason: str
    footprint: Optional[str] = None          # tiny..tight, None when unknown
    memory_use_ratio: Optional[float] = None  # working set / usable memory
    working_set_bytes: Optional[int] = None
    working_set_confidence: str = "estimated"  # measured | estimated | unknown
    usable_memory_bytes: Optional[int] = None
    deficit_bytes: Optional[int] = None
    download_bytes: Optional[int] = None
    disk_ok: Optional[bool] = None
    disk_shortfall_bytes: Optional[int] = None
    runnable_now: Optional[bool] = None
    free_shortfall_bytes: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__.copy()


def _footprint(ratio: float) -> str:
    for edge, label in FOOTPRINT_BANDS:
        if ratio <= edge:
            return label
    return "tight"


def assess(recipe, profile: DeviceProfile) -> Verdict:
    """Assess one recipe against one probed machine."""
    rid = getattr(recipe, "recipe_id", "?")
    backends = list(getattr(recipe, "backends", []) or [])
    working_set = getattr(recipe, "working_set_bytes", None)
    confidence = getattr(recipe, "working_set_confidence", "estimated")
    download = getattr(recipe, "download_bytes", None)

    v = Verdict(
        recipe_id=rid,
        verdict="unknown",
        reason="",
        working_set_bytes=working_set,
        working_set_confidence=confidence,
        download_bytes=download,
    )

    # Disk is independent of everything else, so answer it even when memory is unknown.
    free_disk = profile.disk_free_bytes
    if download is not None and free_disk is not None:
        v.disk_ok = free_disk >= download
        if not v.disk_ok:
            v.disk_shortfall_bytes = download - free_disk

    backend = profile.backend
    if backends and backend and backend not in backends:
        v.verdict = "blocked"
        v.reason = f"needs {' or '.join(backends)}; this machine runs {backend}"
        return v

    capacity = profile.accelerator_memory_bytes
    if not capacity:
        v.reason = "could not read this machine's memory, so nothing can be promised"
        return v
    if working_set is None:
        v.reason = "this model's memory footprint has not been measured"
        return v

    usable = usable_memory_bytes(profile)
    v.usable_memory_bytes = usable
    ratio = working_set / usable if usable else float("inf")
    v.memory_use_ratio = round(min(ratio, 1.0), 4)
    v.footprint = _footprint(ratio)

    if working_set > usable:
        v.verdict = "wont_fit"
        v.deficit_bytes = working_set - usable
        v.reason = f"needs {working_set / GIB:.1f} GB, {usable / GIB:.1f} GB available to models"
    elif ratio > TIGHT_THRESHOLD:
        v.verdict = "tight"
        v.reason = f"uses {ratio:.0%} of the memory available to models"
    else:
        v.verdict = "fits"
        v.reason = f"uses {ratio:.0%} of the memory available to models"

    # Right now, as distinct from ever.
    free_now = profile.memory_free_bytes
    if free_now is not None and v.verdict in ("fits", "tight"):
        v.runnable_now = free_now >= working_set
        if not v.runnable_now:
            v.free_shortfall_bytes = working_set - free_now

    return v


def assess_all(recipes: List[Any], profile: DeviceProfile) -> List[Verdict]:
    return [assess(r, profile) for r in recipes]


_RANK = {"fits": 0, "tight": 1, "unknown": 2, "wont_fit": 3, "blocked": 4}


def recommend(recipes: List[Any], profile: DeviceProfile) -> Optional[str]:
    """The one model to lead with: the most capable that comfortably fits."""
    scored = [(r, assess(r, profile)) for r in recipes]
    runnable = [
        (r, v) for r, v in scored
        if v.verdict == "fits" and v.disk_ok is not False
    ]
    if not runnable:
        return None
    # This is a video workstation, so lead with a video model when one fits;
    # the largest that does, since "most capable that is still comfortable" is
    # the useful default. Fall back to any kind only if no video model fits.
    video = [rv for rv in runnable if getattr(rv[0], "kind", None) == "video"]
    pool = video or runnable
    # Never default someone into an encumbered licence. HunyuanVideo's terms
    # exclude the EU, UK and South Korea; LTX's are revenue-capped and travel
    # downstream. Those stay in the list, just not as the suggestion.
    permissive = [
        rv for rv in pool
        if (getattr(rv[0], "license", "") or "").lower() in PERMISSIVE_LICENSES
    ]
    pool = permissive or pool
    pool.sort(key=lambda rv: rv[1].working_set_bytes or 0, reverse=True)
    return pool[0][0].recipe_id


def sort_key(verdict: Verdict) -> tuple:
    return (_RANK.get(verdict.verdict, 9), -(verdict.working_set_bytes or 0))
