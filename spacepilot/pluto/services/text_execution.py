"""Plan and execute bounded, one-shot local text generation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional

from spacepilot.device_probe import DeviceProfile, probe_local_device
from spacepilot.pluto import measurements as ms
from spacepilot.pluto.registry import Variant, registry
from spacepilot.pluto.services.compatibility import Verdict, assess
from spacepilot.pluto.services.execution import LocalExecutionError
from spacepilot.pluto.services.model_catalog import catalog_manager
from spacepilot.pluto.services.provenance import FlownSpeed, local_speeds


VARIANT_ID = "qwen3-8-27b-4bit"
RUNTIME_ID = "mlx-lm"
MAX_SAFE_TOKENS = 256
MAX_SAFE_KV_SIZE = 4096


@dataclass(frozen=True)
class TextCandidate:
    variant: Variant
    verdict: Verdict
    speed: Optional[FlownSpeed]
    route_ready: bool
    route_detail: str

    @property
    def can_run(self) -> bool:
        return self.route_ready and self.verdict.verdict in {"fits", "tight"}


@dataclass(frozen=True)
class TextRunPlan:
    workload: str
    system: ms.System
    candidates: tuple[TextCandidate, ...]

    @property
    def selected(self) -> Optional[TextCandidate]:
        return next((candidate for candidate in self.candidates if candidate.can_run), None)


@dataclass(frozen=True)
class TextRequest:
    workload: str
    prompt: str
    output: Path
    max_tokens: int = MAX_SAFE_TOKENS
    max_kv_size: int = MAX_SAFE_KV_SIZE
    temperature: float = 0.0


@dataclass(frozen=True)
class TextRunResult:
    status: str
    variant_id: str
    output: Path
    resolved_revision: Optional[str]
    wall_seconds: float
    load_seconds: float
    generation_tps: float
    prompt_tokens: int
    generation_tokens: int
    peak_memory_gb: float
    measurement_path: Path


class TextExecutionService:
    def __init__(
        self, *, driver=None,
        profile_probe: Optional[Callable[[], DeviceProfile]] = None,
        measurement_loader: Optional[Callable[[], list]] = None,
        measurement_recorder: Optional[Callable[..., Path]] = None,
        system_writer: Optional[Callable[..., Path]] = None,
        contention_sampler: Optional[Callable[[], str]] = None,
    ) -> None:
        if driver is None:
            from spacepilot.drivers.mlx_lm_driver import MlxLmDriver
            driver = MlxLmDriver()
        self.driver = driver
        self.profile_probe = profile_probe or probe_local_device
        self.measurement_loader = measurement_loader or ms.load_measurements
        self.measurement_recorder = measurement_recorder or ms.record
        self.system_writer = system_writer or ms.write_system
        self.contention_sampler = contention_sampler or ms.sample_contention

    def plan(self, workload: str) -> TextRunPlan:
        if workload != "text":
            raise ValueError("unsupported workload; supported: text")
        profile = self.profile_probe()
        system = ms.system_from_profile(profile)
        variant = registry().variant(VARIANT_ID)
        recipe = catalog_manager.recipes.get(VARIANT_ID)
        if variant is None or recipe is None:
            raise LocalExecutionError(f"exact text route {VARIANT_ID!r} is absent")
        ready, detail = self.driver.route_status(VARIANT_ID)
        speed = next((row for row in local_speeds(
            self.measurement_loader(), system_id=system.id, variant_id=VARIANT_ID,
        ) if row.metric == "tokens_per_second"), None)
        return TextRunPlan("text", system, (
            TextCandidate(variant, assess(recipe, profile), speed, ready, detail),
        ))

    @staticmethod
    def _validate(request: TextRequest) -> None:
        if request.workload != "text":
            raise LocalExecutionError("request workload does not match the plan")
        if not request.prompt.strip():
            raise LocalExecutionError("prompt cannot be empty")
        if not 1 <= request.max_tokens <= MAX_SAFE_TOKENS:
            raise LocalExecutionError(f"max_tokens must be 1..{MAX_SAFE_TOKENS}")
        if not 1 <= request.max_kv_size <= MAX_SAFE_KV_SIZE:
            raise LocalExecutionError(f"max_kv_size must be 1..{MAX_SAFE_KV_SIZE}")
        if not 0.0 <= request.temperature <= 2.0:
            raise LocalExecutionError("temperature must be 0.0..2.0")

    def execute(self, plan: TextRunPlan, request: TextRequest) -> TextRunResult:
        self._validate(request)
        if request.workload != plan.workload:
            raise LocalExecutionError("request workload does not match the plan")
        candidate = plan.selected
        if candidate is None:
            raise LocalExecutionError("no safe local route is available")
        output = Path(request.output).expanduser().resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        before = output.stat() if output.is_file() else None
        contention_before = self.contention_sampler()
        result = self.driver.infer(
            prompt=request.prompt, out_path=str(output), variant_id=VARIANT_ID,
            max_tokens=request.max_tokens, max_kv_size=request.max_kv_size,
            temperature=request.temperature,
        )
        contention_after = self.contention_sampler()
        if result.get("status") != "completed":
            raise LocalExecutionError("MLX-LM did not report completion")
        if not output.is_file() or output.stat().st_size <= 0:
            raise LocalExecutionError("MLX-LM produced no non-empty text artifact")
        if before is not None and output.stat() == before:
            raise LocalExecutionError("MLX-LM did not produce a new text artifact")
        numeric = ("wall_seconds", "load_seconds", "generation_tps", "peak_memory_gb")
        if any(not isinstance(result.get(key), (int, float)) or result[key] <= 0 for key in numeric):
            raise LocalExecutionError("MLX-LM completed without complete measured run metadata")
        for key in ("prompt_tokens", "generation_tokens"):
            if not isinstance(result.get(key), int) or result[key] <= 0:
                raise LocalExecutionError("MLX-LM completed without real token counts")
        resolved_revision = result.get("model_revision")
        if not isinstance(resolved_revision, str) or not resolved_revision:
            resolved_revision = None
        contention = "solo" if contention_before == contention_after == "solo" else (
            "unknown" if "unknown" in {contention_before, contention_after} else "loaded")
        self.system_writer(plan.system)
        measurement_path = self.measurement_recorder(
            system=plan.system, model_id=VARIANT_ID, variant_id=VARIANT_ID,
            metric="tokens_per_second", value=float(result["generation_tps"]),
            contention=contention, runtime_id=RUNTIME_ID,
            quantisation=candidate.variant.precision,
            wall_seconds=float(result["wall_seconds"]),
            resolved_revision=resolved_revision,
            knobs={
                "max_tokens": request.max_tokens,
                "max_kv_size": request.max_kv_size,
                "temperature": request.temperature,
                "prompt_tokens": result["prompt_tokens"],
                "generation_tokens": result["generation_tokens"],
                "load_seconds": float(result["load_seconds"]),
                "peak_memory_gb": float(result["peak_memory_gb"]),
            },
            note="ordinary bounded spacepilot run text success; text artifact verified",
        )
        return TextRunResult(
            "completed", VARIANT_ID, output, resolved_revision,
            float(result["wall_seconds"]), float(result["load_seconds"]),
            float(result["generation_tps"]), result["prompt_tokens"],
            result["generation_tokens"], float(result["peak_memory_gb"]),
            measurement_path,
        )


def default_text_output() -> Path:
    import uuid
    from spacepilot.paths import outputs_dir
    return outputs_dir() / f"spacepilot-{uuid.uuid4().hex}.txt"
