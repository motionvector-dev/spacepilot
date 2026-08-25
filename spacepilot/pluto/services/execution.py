"""Plan and execute a real local workload without coupling it to the CLI.

The objects in this module are deliberately transport-neutral.  Phase 4 can
put the same service behind DirectLocal and DaemonClient; the CLI in this
phase is only one caller.  Planning never downloads or starts a runtime.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, Optional, Sequence

from spacepilot.device_probe import DeviceProfile, probe_local_device
from spacepilot.drivers.mflux_driver import MfluxDriver, command_for_alias
from spacepilot.pluto import measurements as ms
from spacepilot.pluto.measurements import Measurement
from spacepilot.pluto.registry import Variant, registry
from spacepilot.pluto.services.compatibility import Verdict, assess
from spacepilot.pluto.services.model_catalog import catalog_manager
from spacepilot.pluto.services.provenance import FlownSpeed, local_speeds


@dataclass(frozen=True)
class ImageRoute:
    """One exact registry artifact mapped to one verified mflux alias."""

    variant_id: str
    model_alias: str
    quantize: int = 4
    steps: int = 4
    width: int = 512
    height: int = 512


IMAGE_ROUTES: tuple[ImageRoute, ...] = (
    ImageRoute("flux-schnell-4bit", "schnell"),
    ImageRoute("flux2-klein-4b-4bit", "flux2-klein-4b"),
)


@dataclass(frozen=True)
class LocalCandidate:
    route: ImageRoute
    variant: Variant
    verdict: Verdict
    speed: Optional[FlownSpeed]
    executable: Path
    executable_ready: bool

    @property
    def route_state(self) -> str:
        return "ready" if self.executable_ready else "no route"

    @property
    def can_run(self) -> bool:
        # Capacity is the routing boundary. Current headroom and download disk
        # are still rendered as caveats, but do not rewrite a fits/tight fact:
        # this path is offline and may already have the weights cached.
        return (
            self.executable_ready
            and self.verdict.verdict in {"fits", "tight"}
        )

    @property
    def non_safe_caveats(self) -> tuple[Any, ...]:
        return tuple(c for c in self.variant.caveats if not c.is_safe)


@dataclass(frozen=True)
class RunPlan:
    workload: str
    system: ms.System
    candidates: tuple[LocalCandidate, ...]

    @property
    def selected(self) -> Optional[LocalCandidate]:
        return next((candidate for candidate in self.candidates if candidate.can_run), None)


@dataclass(frozen=True)
class RunRequest:
    workload: str
    prompt: str
    output: Path
    seed: Optional[int] = None


@dataclass(frozen=True)
class RunResult:
    status: str
    variant_id: str
    model_alias: str
    output: Path
    resolved_revision: Optional[str]
    wall_seconds: float
    seconds_per_image: Optional[float]
    measurement_path: Optional[Path]
    timing_source: Optional[str]


class LocalExecutionError(RuntimeError):
    """A local route could not produce a verified artifact."""


def _image_speed(rows: Iterable[Measurement], system_id: str,
                 variant_id: str) -> Optional[FlownSpeed]:
    return next((speed for speed in local_speeds(
        rows, system_id=system_id, variant_id=variant_id,
    ) if speed.metric == "seconds_per_image"), None)


def _candidate_rank(candidate: LocalCandidate) -> tuple[int, int, int, str]:
    """Flown solo, flown observed, then unflown fits/tight; unsafe rows follow."""
    if candidate.can_run:
        if candidate.speed and candidate.speed.stream == "solo":
            evidence = 0
        elif candidate.speed:
            evidence = 1
        else:
            evidence = 2
        fit = 0 if candidate.verdict.verdict == "fits" else 1
        # Within an evidence/fit tier prefer the smaller known working set.
        footprint = candidate.verdict.working_set_bytes or 2**63
        return evidence, fit, footprint, candidate.variant.id

    unsafe = {
        "unknown": 0,
        "wont_fit": 1,
        "blocked": 2,
    }.get(candidate.verdict.verdict, 3)
    # A known compatibility refusal is more useful than a missing executable,
    # but neither can accidentally become the selected row.
    route = 1 if candidate.executable_ready else 2
    return 3, unsafe, route, candidate.variant.id


class LocalExecutionService:
    """Read-only planning plus confirmed execution for this machine."""

    def __init__(
        self,
        *,
        driver: Optional[MfluxDriver] = None,
        routes: Sequence[ImageRoute] = IMAGE_ROUTES,
        profile_probe: Optional[Callable[[], DeviceProfile]] = None,
        measurement_loader: Optional[Callable[[], list[Measurement]]] = None,
        measurement_recorder: Optional[Callable[..., Path]] = None,
        system_writer: Optional[Callable[..., Path]] = None,
        contention_sampler: Optional[Callable[[], str]] = None,
    ) -> None:
        self.driver = driver or MfluxDriver()
        self.routes = tuple(routes)
        self.profile_probe = profile_probe or probe_local_device
        self.measurement_loader = measurement_loader or ms.load_measurements
        self.measurement_recorder = measurement_recorder or ms.record
        self.system_writer = system_writer or ms.write_system
        self.contention_sampler = contention_sampler or ms.sample_contention

    def plan(self, workload: str) -> RunPlan:
        if workload != "image":
            raise ValueError(f"unsupported workload {workload!r}; supported: image")

        profile = self.profile_probe()
        system = ms.system_from_profile(profile)
        measurements = self.measurement_loader()
        reg = registry()
        candidates = []
        for route in self.routes:
            variant = reg.variant(route.variant_id)
            recipe = catalog_manager.recipes.get(route.variant_id)
            if variant is None or recipe is None:
                # IMAGE_ROUTES is code, not user input.  A stale exact mapping
                # is a packaging error and must never fuzzily select another id.
                raise LocalExecutionError(
                    f"exact image route {route.variant_id!r} is absent from the registry"
                )
            executable = Path(self.driver.bin_dir) / command_for_alias(route.model_alias)
            executable_ready = executable.is_file() and os.access(executable, os.X_OK)
            candidates.append(LocalCandidate(
                route=route,
                variant=variant,
                verdict=assess(recipe, profile),
                speed=_image_speed(measurements, system.id, variant.id),
                executable=executable,
                executable_ready=executable_ready,
            ))
        candidates.sort(key=_candidate_rank)
        return RunPlan(workload=workload, system=system, candidates=tuple(candidates))

    def execute(self, plan: RunPlan, request: RunRequest) -> RunResult:
        """Run the selected exact route and record only a verified success."""
        if request.workload != plan.workload or request.workload != "image":
            raise LocalExecutionError("request workload does not match the plan")
        if not request.prompt or not request.prompt.strip():
            raise LocalExecutionError("prompt cannot be empty")
        candidate = plan.selected
        if candidate is None:
            raise LocalExecutionError("no safe local route is available")

        # The executable may disappear or lose its mode after planning.
        if not candidate.executable.is_file() or not os.access(candidate.executable, os.X_OK):
            raise LocalExecutionError(f"mflux executable is not executable: {candidate.executable}")

        output = Path(request.output).expanduser().resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        before = self._artifact_signature(output)
        contention_before = self.contention_sampler()
        result = self.driver.infer(
            prompt=request.prompt,
            model=candidate.route.model_alias,
            quantize=candidate.route.quantize,
            steps=candidate.route.steps,
            seed=request.seed,
            height=candidate.route.height,
            width=candidate.route.width,
            out_path=str(output),
            # A normal run is not implicit permission to fetch tens of GB.
            env={"HF_HUB_OFFLINE": "1"},
        )
        contention_after = self.contention_sampler()

        if result.get("status") != "completed":
            raise LocalExecutionError("mflux did not report completion")
        after = self._artifact_signature(output)
        if after is None or after[1] <= 0 or after == before:
            raise LocalExecutionError(
                f"mflux reported completion but produced no new non-empty artifact at {output}"
            )

        wall = result.get("wall_seconds")
        if not isinstance(wall, (int, float)) or wall < 0:
            raise LocalExecutionError("mflux completed without a real wall-clock duration")
        generated = result.get("generate_seconds")
        seconds_per_image = (
            float(generated) if isinstance(generated, (int, float)) and generated >= 0 else None
        )
        resolved_revision = result.get("model_revision")
        if not isinstance(resolved_revision, str) or not resolved_revision.strip():
            # mflux owns its weight cache and currently does not expose the
            # snapshot it opened.  None is explicit unknown, not the registry
            # pin copied onto unobserved bytes.
            resolved_revision = None

        self.system_writer(plan.system)
        measurement_path = None
        if seconds_per_image is not None:
            contention = self._combined_contention(contention_before, contention_after)
            measurement_path = self.measurement_recorder(
                system=plan.system,
                model_id=candidate.variant.id,
                variant_id=candidate.variant.id,
                metric="seconds_per_image",
                value=seconds_per_image,
                contention=contention,
                runtime_id="mflux",
                quantisation=f"int{candidate.route.quantize}",
                backend="metal",
                wall_seconds=float(wall),
                resolved_revision=resolved_revision,
                knobs={
                    "model_alias": candidate.route.model_alias,
                    "quantisation": f"int{candidate.route.quantize}",
                    "steps": candidate.route.steps,
                    "width": candidate.route.width,
                    "height": candidate.route.height,
                    **({"seed": request.seed} if request.seed is not None else {}),
                },
                note="ordinary spacepilot run image success; output artifact verified",
            )

        return RunResult(
            status="completed",
            variant_id=candidate.variant.id,
            model_alias=candidate.route.model_alias,
            output=output,
            resolved_revision=resolved_revision,
            wall_seconds=float(wall),
            seconds_per_image=seconds_per_image,
            measurement_path=measurement_path,
            timing_source=result.get("timing_source"),
        )

    @staticmethod
    def _artifact_signature(path: Path) -> Optional[tuple[int, int, int]]:
        try:
            stat = path.stat()
        except (FileNotFoundError, OSError):
            return None
        if not path.is_file():
            return None
        return stat.st_ino, stat.st_size, stat.st_mtime_ns

    @staticmethod
    def _combined_contention(before: str, after: str) -> str:
        if before == after == "solo":
            return "solo"
        if "unknown" in {before, after}:
            return "unknown"
        return "loaded"


def default_image_output() -> Path:
    """A collision-resistant local output path, resolved only at invocation."""
    import uuid
    from spacepilot.paths import outputs_dir

    return outputs_dir() / f"spacepilot-{uuid.uuid4().hex}.png"
