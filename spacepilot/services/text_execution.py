"""Plan and execute bounded, one-shot local text generation."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional

from spacepilot.device_probe import DeviceProfile, probe_local_device
from spacepilot import measurements as ms
from spacepilot.model_registry import Variant, registry
from spacepilot.routes import default_variant_id
from spacepilot.services.compatibility import Verdict, assess
from spacepilot.services.execution import LocalExecutionError
from spacepilot.services.model_catalog import catalog_manager
from spacepilot.services.provenance import FlownSpeed, local_speeds


# Deprecated: kept as an alias of the default served text variant for one
# release, for any caller or test that still imports it directly. New code
# should read `spacepilot.routes.served_variants("text")` (or pass no
# `variant_id` to `TextExecutionService.plan`, which does the same lookup) —
# the daemon now serves every text variant the mlx-lm runtime declares it
# runs, not only this one.
VARIANT_ID = "qwen3-8-27b-4bit"
RUNTIME_ID = "mlx-lm"
MAX_SAFE_TOKENS = 256
MAX_SAFE_KV_SIZE = 4096


def stopped_inside_think(text: str) -> bool:
    """True when a ``<think>`` block is still open at the end of the text.

    A closed think followed by an answer is a real reply. An unclosed one
    means the token cap died inside the trace and the sentence never came.
    """
    start = text.rfind("<think>")
    if start < 0:
        return False
    return text.find("</think>", start) < 0


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
    # Off unless the caller asks. Passed to chat templates that accept
    # enable_thinking. A template that ignores it can still emit <think>.
    thinking: bool = False
    # Supplied by a caller that already told someone else this id — the /v1
    # routes do, so the response and the record name the same run. Minted here
    # when absent.
    run_id: Optional[str] = None
    # A real chat turn list, when the caller has one. The CLI does not; it
    # sends `prompt` and the runner wraps it as a single user message.
    messages: Optional[tuple] = None


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
    run_id: Optional[str] = None


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

    def plan(self, workload: str, variant_id: Optional[str] = None) -> TextRunPlan:
        if workload != "text":
            raise ValueError("unsupported workload; supported: text")
        resolved_variant_id = variant_id or default_variant_id("text")
        if resolved_variant_id is None:
            raise LocalExecutionError("no text variant is served locally")
        profile = self.profile_probe()
        system = ms.system_from_profile(profile)
        variant = registry().variant(resolved_variant_id)
        recipe = catalog_manager.recipes.get(resolved_variant_id)
        if variant is None or recipe is None:
            raise LocalExecutionError(f"exact text route {resolved_variant_id!r} is absent")
        ready, detail = self.driver.route_status(resolved_variant_id)
        speed = next((row for row in local_speeds(
            self.measurement_loader(), system_id=system.id, variant_id=resolved_variant_id,
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
        candidate, output, before, contention_before = self._start(plan, request)
        result = self.driver.infer(
            prompt=request.prompt, out_path=str(output), variant_id=candidate.variant.id,
            max_tokens=request.max_tokens, max_kv_size=request.max_kv_size,
            temperature=request.temperature, thinking=request.thinking,
            messages=list(request.messages) if request.messages else None,
        )
        return self._finish(plan, request, candidate, output, before,
                            contention_before, result)

    def execute_stream(self, plan: TextRunPlan, request: TextRequest):
        """Generate incrementally, then record exactly what the run did.

        Yields ``("chunk", text)`` for each delta the driver produces and
        finally ``("result", TextRunResult)``. The text is real streaming from
        the runner, not a completed answer cut into pieces — a caller timing
        first-token latency would otherwise be measuring a lie.
        """
        candidate, output, before, contention_before = self._start(plan, request)
        result = None
        for event in self.driver.stream(
            prompt=request.prompt, out_path=str(output), variant_id=candidate.variant.id,
            max_tokens=request.max_tokens, max_kv_size=request.max_kv_size,
            temperature=request.temperature, thinking=request.thinking,
            messages=list(request.messages) if request.messages else None,
        ):
            if event.get("type") == "chunk":
                yield "chunk", event.get("text", "")
            elif event.get("type") == "result":
                result = event.get("result")
        if result is None:
            raise LocalExecutionError("MLX-LM streamed no structured result")
        yield "result", self._finish(plan, request, candidate, output, before,
                                     contention_before, result)

    def _start(self, plan: TextRunPlan, request: TextRequest):
        self._validate(request)
        if request.workload != plan.workload:
            raise LocalExecutionError("request workload does not match the plan")
        candidate = plan.selected
        if candidate is None:
            raise LocalExecutionError("no safe local route is available")
        output = Path(request.output).expanduser().resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        before = output.stat() if output.is_file() else None
        return candidate, output, before, self.contention_sampler()

    def _finish(self, plan, request, candidate, output, before,
                contention_before, result) -> TextRunResult:
        contention_after = self.contention_sampler()
        if result.get("status") != "completed":
            raise LocalExecutionError("MLX-LM did not report completion")
        if not output.is_file() or output.stat().st_size <= 0:
            raise LocalExecutionError("MLX-LM produced no non-empty text artifact")
        if before is not None and output.stat() == before:
            raise LocalExecutionError("MLX-LM did not produce a new text artifact")
        text = output.read_text()
        unfinished = stopped_inside_think(text)
        numeric = ("wall_seconds", "load_seconds", "generation_tps", "prompt_tps",
                   "peak_memory_gb")
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
        run_id = request.run_id or uuid.uuid4().hex
        variant_id = candidate.variant.id
        self.system_writer(plan.system)
        knobs = {
            "max_tokens": request.max_tokens,
            "max_kv_size": request.max_kv_size,
            "temperature": request.temperature,
            "thinking": "on" if request.thinking else "off",
            "prompt_tokens": result["prompt_tokens"],
            "generation_tokens": result["generation_tokens"],
            "load_seconds": float(result["load_seconds"]),
            "peak_memory_gb": float(result["peak_memory_gb"]),
            "generation_tps": float(result["generation_tps"]),
        }
        if unfinished:
            # The speed is real and is stored. It is not an answer, so the
            # row is failed and stays out of the speed summary.
            self.measurement_recorder(
                system=plan.system, model_id=variant_id, variant_id=variant_id,
                metric="tokens_per_second", value=float(result["wall_seconds"]),
                contention=contention, runtime_id=RUNTIME_ID,
                quantisation=candidate.variant.precision,
                wall_seconds=float(result["wall_seconds"]),
                resolved_revision=resolved_revision,
                run_id=run_id, status="failed",
                tokens_in=result["prompt_tokens"],
                tokens_out=result["generation_tokens"],
                knobs=knobs,
                note="generation stopped inside an unclosed think block; not an answer",
            )
            raise LocalExecutionError(
                "generation stopped inside an unclosed <think> block; "
                "the token cap ended before an answer")
        measurement_path = self.measurement_recorder(
            system=plan.system, model_id=variant_id, variant_id=variant_id,
            metric="tokens_per_second", value=float(result["generation_tps"]),
            contention=contention, runtime_id=RUNTIME_ID,
            quantisation=candidate.variant.precision,
            wall_seconds=float(result["wall_seconds"]),
            resolved_revision=resolved_revision,
            run_id=run_id,
            tokens_in=result["prompt_tokens"],
            tokens_out=result["generation_tokens"],
            knobs=knobs,
            note="ordinary bounded spacepilot run text success; text artifact verified",
        )
        # A second row, same run_id: prefill and decode are different phases
        # with different costs (see /v1/chat/completions dry_run), and each
        # needs its own median rather than being averaged into one number.
        self.measurement_recorder(
            system=plan.system, model_id=variant_id, variant_id=variant_id,
            metric="prompt_tokens_per_second", value=float(result["prompt_tps"]),
            contention=contention, runtime_id=RUNTIME_ID,
            quantisation=candidate.variant.precision,
            wall_seconds=float(result["wall_seconds"]),
            resolved_revision=resolved_revision,
            run_id=run_id,
            tokens_in=result["prompt_tokens"],
            tokens_out=result["generation_tokens"],
            knobs=knobs,
            note="ordinary bounded spacepilot run text success; text artifact verified",
        )
        return TextRunResult(
            "completed", variant_id, output, resolved_revision,
            float(result["wall_seconds"]), float(result["load_seconds"]),
            float(result["generation_tps"]), result["prompt_tokens"],
            result["generation_tokens"], float(result["peak_memory_gb"]),
            measurement_path, run_id,
        )


def default_text_output() -> Path:
    from spacepilot.paths import outputs_dir
    return outputs_dir() / f"spacepilot-{uuid.uuid4().hex}.txt"
