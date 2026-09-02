"""Plan and execute bounded local embedding through one exact MLX route.

Shaped like :mod:`spacepilot.services.text_execution` on purpose: same plan
then execute, same fit assessment, same verified-artifact rule, same
measurement written afterwards. An embedding run that left no record would be
the one workload whose cost nobody could join.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional

from spacepilot.device_probe import DeviceProfile, probe_local_device
from spacepilot import measurements as ms
from spacepilot.model_registry import Variant, registry
from spacepilot.routes import default_variant_id, served_variants
from spacepilot.services.compatibility import Verdict, assess
from spacepilot.services.execution import LocalExecutionError
from spacepilot.services.model_catalog import catalog_manager


# Deprecated: kept as an alias of the default served embedding variant for
# one release, for any caller or test that still imports it directly. New
# code should read `spacepilot.routes.served_variants("embedding")` (or pass
# no `variant_id` to `EmbeddingExecutionService.plan`, which does the same
# lookup).
VARIANT_ID = "qwen3-embedding-0-6b-8bit"
RUNTIME_ID = "mlx-lm"
MAX_SAFE_TOKENS = 2048
MAX_SAFE_INPUTS = 64


@dataclass(frozen=True)
class EmbeddingCandidate:
    variant: Variant
    verdict: Verdict
    route_ready: bool
    route_detail: str

    @property
    def can_run(self) -> bool:
        return self.route_ready and self.verdict.verdict in {"fits", "tight"}


@dataclass(frozen=True)
class EmbeddingRunPlan:
    workload: str
    system: ms.System
    candidates: tuple[EmbeddingCandidate, ...]

    @property
    def selected(self) -> Optional[EmbeddingCandidate]:
        return next((c for c in self.candidates if c.can_run), None)


@dataclass(frozen=True)
class EmbeddingRequest:
    inputs: tuple[str, ...]
    output: Path
    max_tokens: int = MAX_SAFE_TOKENS
    run_id: Optional[str] = None


@dataclass(frozen=True)
class EmbeddingRunResult:
    status: str
    variant_id: str
    output: Path
    resolved_revision: Optional[str]
    vectors: tuple[tuple[float, ...], ...]
    dimensions: int
    tokens_in: int
    wall_seconds: float
    load_seconds: float
    peak_memory_gb: float
    measurement_path: Path
    run_id: str


class EmbeddingExecutionService:
    def __init__(
        self, *, driver=None,
        profile_probe: Optional[Callable[[], DeviceProfile]] = None,
        measurement_recorder: Optional[Callable[..., Path]] = None,
        system_writer: Optional[Callable[..., Path]] = None,
        contention_sampler: Optional[Callable[[], str]] = None,
    ) -> None:
        if driver is None:
            from spacepilot.drivers.mlx_embed_driver import MlxEmbedDriver
            driver = MlxEmbedDriver()
        self.driver = driver
        self.profile_probe = profile_probe or probe_local_device
        self.measurement_recorder = measurement_recorder or ms.record
        self.system_writer = system_writer or ms.write_system
        self.contention_sampler = contention_sampler or ms.sample_contention

    def plan(self, variant_id: Optional[str] = None) -> EmbeddingRunPlan:
        resolved_variant_id = variant_id or default_variant_id("embedding")
        if resolved_variant_id is None:
            raise LocalExecutionError("no embedding variant is served locally")
        profile = self.profile_probe()
        system = ms.system_from_profile(profile)
        variant = registry().variant(resolved_variant_id)
        recipe = catalog_manager.recipes.get(resolved_variant_id)
        if variant is None or recipe is None:
            raise LocalExecutionError(f"exact embedding route {resolved_variant_id!r} is absent")
        ready, detail = self.driver.route_status(resolved_variant_id)
        return EmbeddingRunPlan("embedding", system, (
            EmbeddingCandidate(variant, assess(recipe, profile), ready, detail),
        ))

    @staticmethod
    def _validate(request: EmbeddingRequest) -> None:
        if not request.inputs:
            raise LocalExecutionError("inputs cannot be empty")
        if len(request.inputs) > MAX_SAFE_INPUTS:
            raise LocalExecutionError(f"at most {MAX_SAFE_INPUTS} inputs per call")
        if any(not text.strip() for text in request.inputs):
            raise LocalExecutionError("every input must be a non-empty string")
        if not 1 <= request.max_tokens <= MAX_SAFE_TOKENS:
            raise LocalExecutionError(f"max_tokens must be 1..{MAX_SAFE_TOKENS}")

    def execute(self, plan: EmbeddingRunPlan, request: EmbeddingRequest) -> EmbeddingRunResult:
        self._validate(request)
        candidate = plan.selected
        if candidate is None:
            raise LocalExecutionError("no safe local route is available")
        variant_id = candidate.variant.id
        output = Path(request.output).expanduser().resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        contention_before = self.contention_sampler()
        result = self.driver.infer(
            inputs=list(request.inputs), out_path=str(output),
            variant_id=variant_id, max_tokens=request.max_tokens,
        )
        contention_after = self.contention_sampler()
        if result.get("status") != "completed":
            raise LocalExecutionError("MLX embedding did not report completion")
        if not output.is_file() or output.stat().st_size <= 0:
            raise LocalExecutionError("MLX embedding produced no non-empty artifact")
        payload = json.loads(output.read_text())
        vectors = payload.get("vectors")
        if not isinstance(vectors, list) or len(vectors) != len(request.inputs):
            raise LocalExecutionError("MLX embedding returned the wrong number of vectors")
        for key in ("wall_seconds", "load_seconds", "peak_memory_gb"):
            if not isinstance(result.get(key), (int, float)) or result[key] <= 0:
                raise LocalExecutionError("MLX embedding completed without measured run metadata")
        tokens_in = result.get("tokens_in")
        if not isinstance(tokens_in, int) or tokens_in <= 0:
            raise LocalExecutionError("MLX embedding completed without a real token count")
        resolved_revision = result.get("model_revision")
        if not isinstance(resolved_revision, str) or not resolved_revision:
            resolved_revision = None
        contention = "solo" if contention_before == contention_after == "solo" else (
            "unknown" if "unknown" in {contention_before, contention_after} else "loaded")
        run_id = request.run_id or uuid.uuid4().hex
        wall_seconds = float(result["wall_seconds"])
        self.system_writer(plan.system)
        measurement_path = self.measurement_recorder(
            system=plan.system, model_id=variant_id, variant_id=variant_id,
            # Embedding consumes tokens rather than producing them, so the rate
            # is input tokens over wall time. Same metric name as generation
            # because it is the same unit; `tokens_out: 0` is what tells the two
            # apart in the corpus.
            metric="tokens_per_second", value=tokens_in / wall_seconds,
            contention=contention, runtime_id=RUNTIME_ID,
            quantisation=candidate.variant.precision,
            wall_seconds=wall_seconds,
            resolved_revision=resolved_revision,
            run_id=run_id, tokens_in=tokens_in, tokens_out=0,
            knobs={
                "max_tokens": request.max_tokens,
                "inputs": len(request.inputs),
                "dimensions": payload.get("dimensions"),
                "load_seconds": float(result["load_seconds"]),
                "peak_memory_gb": float(result["peak_memory_gb"]),
            },
            note="ordinary bounded spacepilot embedding success; vectors verified",
        )
        return EmbeddingRunResult(
            "completed", variant_id, output, resolved_revision,
            tuple(tuple(float(x) for x in v) for v in vectors),
            int(payload.get("dimensions") or len(vectors[0])),
            tokens_in, wall_seconds, float(result["load_seconds"]),
            float(result["peak_memory_gb"]), measurement_path, run_id,
        )


def default_embedding_output() -> Path:
    from spacepilot.paths import outputs_dir
    return outputs_dir() / f"spacepilot-embed-{uuid.uuid4().hex}.json"


def embedding_variants() -> List[str]:
    """Registry variants actually served locally. One, today."""
    return [v.id for v in served_variants("embedding")]
