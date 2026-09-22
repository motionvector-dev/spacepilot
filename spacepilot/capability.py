"""One shape for "we have not built this", used by every gated subsystem.

Two different failures kept getting the same shape, or three shapes for one
failure. The rule, so neither happens again:

* **Bad input** — you named an id that does not exist. The caller is wrong.
  The answer is an error plus the valid set, so the caller knows what to say
  instead (`error` + `known`).
* **Good input, absent capability** — the caller is right and the system is
  incomplete. The answer is a success plus a capability block: `absent()`
  below. Collapsing this into the first would make "you typo'd" and "we have
  not built it" the same shape.

A refusal and the capability block state the same fact, so they are built from
the same text: `refuse()` raises what `absent()` describes.
"""

from typing import Any, Dict, NoReturn


def absent(name: str, gated: str, detail: str) -> Dict[str, Any]:
    """The capability block a listing carries when the capability is missing.

    `implemented: False` is the field to branch on; `gated` is the date it was
    gated, which is how a reader tells a deliberate gate from a broken read.
    """
    return {"name": name, "implemented": False, "gated": gated, "detail": detail}


def refuse(capability: Dict[str, Any]) -> NoReturn:
    """Refuse a call into an absent capability, in its own words."""
    raise NotImplementedError(capability["detail"])
