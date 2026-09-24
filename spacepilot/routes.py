"""Local execution routing: which registry variant an installed runtime serves.

`model_registry.py` answers "which weights"; `runtimes.py` answers "with what
package". Neither answers "is this exact variant wired to actually run on
this machine right now" — that needs both files plus a third fact: whether
anything in this codebase has a driver behind that runtime. A runtime can
declare `runs:` for a model with no execution path at all — `llama-cpp.yaml`
lists `deepseek-r1-distill-qwen`, but `gguf_driver.py` is a screenplay
decomposer, not a chat driver (see `docs/design/INFERENCE-SURFACE.md`, "Model
id to driver"). Trusting every runtime's `runs:` list would silently promise
a route that raises the moment anyone calls it.

So `WIRED_RUNTIMES` is the one place that says which runtimes actually have
an execution path today, and this module is the one place that turns "model
id in `runs:`, right backend" into a served/not-served answer. The `/v1`
routes, the text and embedding execution services, and the CLI all read it,
so a variant is never served by one surface and refused by another.
"""

from __future__ import annotations

from typing import List, Optional, Sequence

from spacepilot.model_registry import Variant, registry
from spacepilot.runtimes import runtimes

# The machine this project runs on today is Apple silicon; every wired
# runtime and every registry variant that can serve text or embeddings
# declares `metal`. Naming it here rather than probing `DeviceProfile` keeps
# route derivation independent of the request path — it never needs a device
# probe to answer "is this variant servable at all".
LOCAL_BACKEND = "metal"

# Runtimes with a real execution path behind them, not just a registry entry.
# mlx-lm is the only one wired to a driver `/v1/chat/completions` and
# `/v1/embeddings` actually call. Adding llama-cpp (or any runtime) here
# before `gguf_driver.py` becomes a real chat driver would make `/v1/models`
# advertise a route that 502s.
WIRED_RUNTIMES: Sequence[str] = ("mlx-lm", "coreai")


def route_for(variant_id: str, *, wired: Sequence[str] = WIRED_RUNTIMES,
              backend: str = LOCAL_BACKEND) -> Optional[str]:
    """The wired runtime id that serves this variant locally, or None.

    A variant is served by a runtime when: the runtime is in `wired` (has a
    real driver), the runtime supports `backend`, the variant itself
    declares `backend`, and the variant's model id is in the runtime's
    `runs:` list. If a future registry schema records which runtime a
    variant explicitly routes through, that field belongs here too — no
    variant carries one today, so every wired runtime naming the model in
    `runs:` is the answer.
    """
    variant = registry().variant(variant_id)
    if variant is None or backend not in variant.backends:
        return None
    all_runtimes = runtimes()
    for runtime_id in wired:
        runtime = all_runtimes.get(runtime_id)
        if runtime is None or backend not in runtime.backends:
            continue
        if variant.model_id in runtime.runs:
            return runtime_id
    return None


def served_variants(kind: str, *, wired: Sequence[str] = WIRED_RUNTIMES,
                     backend: str = LOCAL_BACKEND) -> List[Variant]:
    """Every variant of `kind` actually served locally, in a stable order.

    Order follows each wired runtime's `runs:` list, runtime by runtime —
    the registry-authored order — not variant id order. Callers that need
    "the first one" (a service's default, the CLI's default) need that to
    mean the same variant everywhere it is read.
    """
    reg = registry()
    all_runtimes = runtimes()
    out: List[Variant] = []
    for runtime_id in wired:
        runtime = all_runtimes.get(runtime_id)
        if runtime is None or backend not in runtime.backends:
            continue
        for model_id in runtime.runs:
            model = reg.model(model_id)
            if model is None or model.kind != kind:
                continue
            for variant in model.variants:
                if backend in variant.backends and variant not in out:
                    out.append(variant)
    return out


def default_variant_id(kind: str, *, wired: Sequence[str] = WIRED_RUNTIMES,
                        backend: str = LOCAL_BACKEND) -> Optional[str]:
    """The variant a caller gets when it does not name one. None if nothing is served."""
    variants = served_variants(kind, wired=wired, backend=backend)
    return variants[0].id if variants else None
