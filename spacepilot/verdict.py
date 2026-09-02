"""One fit verdict, in one function, said the same way everywhere.

Three surfaces answer "does this model run here": `spacepilot models`, the MCP
tool `spacepilot_recommend_models`, and now `GET /v1/models`. Until this
existed they answered in three vocabularies — `fits`/`tight`, "Optimal Local
Execution", and nothing at all — so a user comparing the CLI against the
cockpit had no way to tell whether they disagreed or merely spoke differently.

The words are chosen for someone who is not going to read the memory
arithmetic: `runs_well`, `runs_slowly`, `wont_fit`.

`unknown` is the fourth value and it is not a fourth verdict. It is what comes
back when nothing measured this machine's memory or this model's footprint.
Folding that into one of the three would report a guess as a grading, which is
exactly what `docs/design/CONCEPT.md` forbids.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from spacepilot.device_probe import DeviceProfile

RUNS_WELL = "runs_well"
RUNS_SLOWLY = "runs_slowly"
WONT_FIT = "wont_fit"
UNKNOWN = "unknown"

#: The verdict vocabulary. The first three are verdicts; `unknown` is the
#: absence of one. Anything rendering these strings should render all four.
LEVELS = (RUNS_WELL, RUNS_SLOWLY, WONT_FIT, UNKNOWN)

# `blocked` means the wrong backend — a CUDA-only model on a Mac. That is a
# harder no than running out of memory, not a softer one.
_FROM_ASSESS = {
    "fits": RUNS_WELL,
    "tight": RUNS_SLOWLY,
    "wont_fit": WONT_FIT,
    "blocked": WONT_FIT,
    "unknown": UNKNOWN,
}


class UnknownModel(LookupError):
    """No registry variant by that id."""


def level_for(assessment) -> str:
    """Translate one `services.compatibility.Verdict` into the shared word."""
    return _FROM_ASSESS.get(assessment.verdict, UNKNOWN)


def _headroom(assessment) -> Optional[int]:
    """Usable memory minus working set. Negative when the model is too big.

    None when either side is unmeasured — a headroom computed against a memory
    figure nobody read is a number with no referent.
    """
    usable = assessment.usable_memory_bytes
    working_set = assessment.working_set_bytes
    if usable is None or working_set is None:
        return None
    return int(usable) - int(working_set)


def fit_verdict(model_id: str, system: DeviceProfile) -> Dict[str, Any]:
    """Grade one registry variant against one probed machine.

    `model_id` is a variant id (`qwen3-8-27b-4bit`), because a measurement and
    a fit verdict both describe exact weights, never a family.
    """
    from spacepilot.services.compatibility import assess
    from spacepilot.services.model_catalog import catalog_manager

    recipe = catalog_manager.recipes.get(model_id)
    if recipe is None:
        raise UnknownModel(model_id)
    assessment = assess(recipe, system)
    return {
        "level": level_for(assessment),
        "reason": assessment.reason,
        "headroom_bytes": _headroom(assessment),
    }
