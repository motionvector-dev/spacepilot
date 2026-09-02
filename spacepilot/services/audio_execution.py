"""Plan and execute local speech synthesis and transcription.

The same contract as image execution (see `execution.py`): planning is
read-only and never loads a model, execution runs only the exact selected
route, a refusal is stated rather than papered over, and a speed record is
written only for a verified success. Kept separate from the image service
because the route shapes differ — audio routes are gated on resolvable
assets and (for whisper) an external binary, not on an mflux entry point.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional, Sequence

from spacepilot.device_probe import DeviceProfile, probe_local_device
from spacepilot import measurements as ms
from spacepilot.model_registry import Variant, registry
from spacepilot.services.compatibility import Verdict, assess
from spacepilot.services.execution import LocalExecutionError
from spacepilot.services.model_catalog import catalog_manager
from spacepilot.services.provenance import FlownSpeed, local_speeds


@dataclass(frozen=True)
class AudioRoute:
    """One exact registry variant mapped to one runtime."""

    variant_id: str
    runtime_id: str


SPEECH_ROUTES: tuple[AudioRoute, ...] = (
    AudioRoute("kokoro-82m-onnx", "kokoro-onnx"),
)

TRANSCRIBE_ROUTES: tuple[AudioRoute, ...] = (
    AudioRoute("whisper-base-en", "whisper-cpp"),
    AudioRoute("whisper-small-en", "whisper-cpp"),
)


@dataclass(frozen=True)
class AudioCandidate:
    route: AudioRoute
    variant: Variant
    verdict: Verdict
    speed: Optional[FlownSpeed]
    route_ready: bool
    route_detail: str

    @property
    def route_state(self) -> str:
        return "ready" if self.route_ready else "no route"

    @property
    def can_run(self) -> bool:
        return self.route_ready and self.verdict.verdict in {"fits", "tight"}

    @property
    def non_safe_caveats(self) -> tuple[Any, ...]:
        return tuple(c for c in self.variant.caveats if not c.is_safe)


@dataclass(frozen=True)
class AudioRunPlan:
    workload: str
    system: ms.System
    candidates: tuple[AudioCandidate, ...]

    @property
    def selected(self) -> Optional[AudioCandidate]:
        return next((c for c in self.candidates if c.can_run), None)


@dataclass(frozen=True)
class SpeechRequest:
    workload: str
    text: str
    voice: str
    output: Path
    speed: float = 1.0


@dataclass(frozen=True)
class TranscribeRequest:
    workload: str
    audio: Path
    output: Path


@dataclass(frozen=True)
class AudioRunResult:
    status: str
    variant_id: str
    output: Path
    resolved_revision: Optional[str]
    wall_seconds: float
    audio_seconds: Optional[float]
    realtime_factor: Optional[float]
    measurement_path: Optional[Path]


def _speed_for(rows, system_id: str, variant_id: str) -> Optional[FlownSpeed]:
    return next((speed for speed in local_speeds(
        rows, system_id=system_id, variant_id=variant_id,
    ) if speed.metric == "realtime_factor"), None)


def _rank(candidate: AudioCandidate) -> tuple[int, int, str]:
    if candidate.can_run:
        if candidate.speed and candidate.speed.stream == "solo":
            evidence = 0
        elif candidate.speed:
            evidence = 1
        else:
            evidence = 2
        return evidence, 0 if candidate.verdict.verdict == "fits" else 1, candidate.variant.id
    return 3, 1 if candidate.route_ready else 2, candidate.variant.id


class _AudioExecutionService:
    """Shared plan machinery; each subclass owns one workload's execution."""

    workload: str = ""
    routes: tuple[AudioRoute, ...] = ()

    def __init__(
        self,
        *,
        routes: Optional[Sequence[AudioRoute]] = None,
        profile_probe: Optional[Callable[[], DeviceProfile]] = None,
        measurement_loader: Optional[Callable[[], list]] = None,
        measurement_recorder: Optional[Callable[..., Path]] = None,
        system_writer: Optional[Callable[..., Path]] = None,
        contention_sampler: Optional[Callable[[], str]] = None,
    ) -> None:
        if routes is not None:
            self.routes = tuple(routes)
        self.profile_probe = profile_probe or probe_local_device
        self.measurement_loader = measurement_loader or ms.load_measurements
        self.measurement_recorder = measurement_recorder or ms.record
        self.system_writer = system_writer or ms.write_system
        self.contention_sampler = contention_sampler or ms.sample_contention

    def _route_readiness(self, route: AudioRoute) -> tuple[bool, str]:
        raise NotImplementedError

    def plan(self, workload: str) -> AudioRunPlan:
        if workload != self.workload:
            raise ValueError(
                f"unsupported workload {workload!r}; supported: {self.workload}")
        profile = self.profile_probe()
        system = ms.system_from_profile(profile)
        rows = self.measurement_loader()
        reg = registry()
        candidates = []
        for route in self.routes:
            variant = reg.variant(route.variant_id)
            recipe = catalog_manager.recipes.get(route.variant_id)
            if variant is None or recipe is None:
                # Routes are code, not user input; a stale exact mapping is a
                # packaging error and must never fuzzily select another id.
                raise LocalExecutionError(
                    f"exact {self.workload} route {route.variant_id!r} "
                    f"is absent from the registry")
            ready, detail = self._route_readiness(route)
            candidates.append(AudioCandidate(
                route=route,
                variant=variant,
                verdict=assess(recipe, profile),
                speed=_speed_for(rows, system.id, variant.id),
                route_ready=ready,
                route_detail=detail,
            ))
        candidates.sort(key=_rank)
        return AudioRunPlan(
            workload=workload, system=system, candidates=tuple(candidates))

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

    def _verify_new_artifact(self, output: Path, before, what: str) -> None:
        after = self._artifact_signature(output)
        if after is None or after[1] <= 0 or after == before:
            raise LocalExecutionError(
                f"{what} reported completion but produced no new non-empty "
                f"artifact at {output}")


class SpeechExecutionService(_AudioExecutionService):
    """Kokoro ONNX speech synthesis behind the run plan/confirm/execute gate."""

    workload = "speech"
    routes = SPEECH_ROUTES

    def __init__(self, *, driver=None, **kwargs) -> None:
        super().__init__(**kwargs)
        if driver is None:
            from spacepilot.drivers.kokoro_driver import KokoroDriver
            driver = KokoroDriver()
        self.driver = driver

    def _route_readiness(self, route: AudioRoute) -> tuple[bool, str]:
        if hasattr(self.driver, "runtime_ready"):
            ready, detail = self.driver.runtime_ready()
            if not ready:
                py_bin = getattr(self.driver, "python_bin", "the configured interpreter")
                return False, (
                    f"no route — kokoro-onnx is unavailable in {py_bin}: {detail}; "
                    f"set SPACEPILOT_PYTHON or run 'spacepilot runtimes install kokoro-onnx'")
        try:
            model, voices = self.driver.asset_paths()
        except (FileNotFoundError, ValueError) as exc:
            return False, f"no route — {exc}"
        if not model or not voices:
            return False, (
                f"no route — Kokoro ONNX weights are not cached; run "
                f"`spacepilot recipes download {route.variant_id}` or set "
                f"SPACEPILOT_KOKORO_MODEL and SPACEPILOT_KOKORO_VOICES")
        return True, f"ready — {Path(model).name} via {route.runtime_id}"

    def execute(self, plan: AudioRunPlan, request: SpeechRequest) -> AudioRunResult:
        if request.workload != plan.workload or request.workload != "speech":
            raise LocalExecutionError("request workload does not match the plan")
        if not request.text or not request.text.strip():
            raise LocalExecutionError("text cannot be empty")
        from spacepilot.drivers.kokoro_driver import KokoroDriver
        if not KokoroDriver.is_valid_voice(request.voice):
            names = ", ".join(v["id"] for v in KokoroDriver.get_voice_catalogue())
            # The driver would silently substitute af_heart; a run that
            # synthesizes a different voice than asked is a fabrication.
            raise LocalExecutionError(
                f"unknown voice {request.voice!r}; catalogue: {names}")
        candidate = plan.selected
        if candidate is None:
            raise LocalExecutionError("no safe local route is available")

        output = Path(request.output).expanduser().resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        before = self._artifact_signature(output)
        contention_before = self.contention_sampler()
        result = self.driver.infer(
            text=request.text,
            voice=request.voice,
            speed=request.speed,
            out_path=str(output),
        )
        contention_after = self.contention_sampler()

        if result.get("status") != "completed":
            raise LocalExecutionError("kokoro did not report completion")
        self._verify_new_artifact(output, before, "kokoro")

        wall = result.get("elapsed_sec")
        if not isinstance(wall, (int, float)) or wall <= 0:
            raise LocalExecutionError(
                "kokoro completed without a real wall-clock duration")
        audio_seconds = result.get("duration_sec")
        if not isinstance(audio_seconds, (int, float)) or audio_seconds <= 0:
            raise LocalExecutionError(
                "kokoro completed but reported no audible duration")
        realtime_factor = float(audio_seconds) / float(wall)
        resolved_revision = result.get("model_revision")
        if not isinstance(resolved_revision, str) or not resolved_revision.strip():
            resolved_revision = None

        self.system_writer(plan.system)
        measurement_path = self.measurement_recorder(
            system=plan.system,
            model_id=candidate.variant.id,
            variant_id=candidate.variant.id,
            metric="realtime_factor",
            value=realtime_factor,
            contention=self._combined_contention(contention_before, contention_after),
            runtime_id=candidate.route.runtime_id,
            quantisation="fp32",
            wall_seconds=float(wall),
            resolved_revision=resolved_revision,
            knobs={
                "voice": request.voice,
                "speed": request.speed,
                "lang": "en-us",
                "audio_seconds": float(audio_seconds),
            },
            note="ordinary spacepilot run speech success; output artifact verified",
        )
        return AudioRunResult(
            status="completed",
            variant_id=candidate.variant.id,
            output=output,
            resolved_revision=resolved_revision,
            wall_seconds=float(wall),
            audio_seconds=float(audio_seconds),
            realtime_factor=realtime_factor,
            measurement_path=measurement_path,
        )


class TranscribeExecutionService(_AudioExecutionService):
    """whisper.cpp transcription behind the run plan/confirm/execute gate."""

    workload = "transcribe"
    routes = TRANSCRIBE_ROUTES

    def __init__(self, *, driver=None, **kwargs) -> None:
        super().__init__(**kwargs)
        if driver is None:
            from spacepilot.drivers.whisper_cpp_driver import WhisperCppDriver
            driver = WhisperCppDriver()
        self.driver = driver

    def _route_readiness(self, route: AudioRoute) -> tuple[bool, str]:
        exe = self.driver.executable()
        if exe is None:
            return False, (
                "no route — whisper-cli not found or not executable; install "
                "whisper-cpp or set SPACEPILOT_WHISPER_BIN")
        try:
            model = self.driver.asset_path(route.variant_id)
        except FileNotFoundError as exc:
            return False, f"no route — {exc}"
        if model is None:
            return False, (
                f"no route — whisper weights are not cached; run "
                f"`spacepilot recipes download {route.variant_id}` or set "
                f"SPACEPILOT_WHISPER_MODEL")
        return True, f"ready — {Path(model).name} via {Path(exe).name}"

    def execute(self, plan: AudioRunPlan, request: TranscribeRequest) -> AudioRunResult:
        if request.workload != plan.workload or request.workload != "transcribe":
            raise LocalExecutionError("request workload does not match the plan")
        audio = Path(request.audio).expanduser().resolve()
        if not audio.is_file() or audio.stat().st_size == 0:
            raise LocalExecutionError(f"audio file is missing or empty: {audio}")
        candidate = plan.selected
        if candidate is None:
            raise LocalExecutionError("no safe local route is available")

        output = Path(request.output).expanduser().resolve()
        if output.suffix != ".txt":
            output = output.with_name(output.name + ".txt")
        output.parent.mkdir(parents=True, exist_ok=True)
        before = self._artifact_signature(output)
        contention_before = self.contention_sampler()
        result = self.driver.infer(
            audio_path=str(audio), out_path=str(output),
            variant_id=candidate.route.variant_id,
        )
        contention_after = self.contention_sampler()

        if result.get("status") != "completed":
            raise LocalExecutionError("whisper-cli did not report completion")
        self._verify_new_artifact(output, before, "whisper-cli")

        wall = result.get("wall_seconds")
        if not isinstance(wall, (int, float)) or wall <= 0:
            raise LocalExecutionError(
                "whisper-cli completed without a real wall-clock duration")
        audio_seconds = result.get("audio_seconds")
        if not isinstance(audio_seconds, (int, float)) or audio_seconds <= 0:
            audio_seconds = None
        resolved_revision = result.get("model_revision")
        if not isinstance(resolved_revision, str) or not resolved_revision.strip():
            resolved_revision = None

        self.system_writer(plan.system)
        measurement_path = None
        realtime_factor = None
        if audio_seconds is not None:
            realtime_factor = float(audio_seconds) / float(wall)
            measurement_path = self.measurement_recorder(
                system=plan.system,
                model_id=candidate.variant.id,
                variant_id=candidate.variant.id,
                metric="realtime_factor",
                value=realtime_factor,
                contention=self._combined_contention(
                    contention_before, contention_after),
                runtime_id=candidate.route.runtime_id,
                quantisation=candidate.variant.precision,
                wall_seconds=float(wall),
                resolved_revision=resolved_revision,
                knobs={
                    "weights": result.get("weights"),
                    "audio_seconds": float(audio_seconds),
                },
                note="ordinary spacepilot run transcribe success; "
                     "transcript artifact verified",
            )
        return AudioRunResult(
            status="completed",
            variant_id=candidate.variant.id,
            output=output,
            resolved_revision=resolved_revision,
            wall_seconds=float(wall),
            audio_seconds=float(audio_seconds) if audio_seconds is not None else None,
            realtime_factor=realtime_factor,
            measurement_path=measurement_path,
        )


def default_speech_output() -> Path:
    import uuid
    from spacepilot.paths import outputs_dir
    return outputs_dir() / f"spacepilot-{uuid.uuid4().hex}.wav"


def default_transcript_output() -> Path:
    import uuid
    from spacepilot.paths import outputs_dir
    return outputs_dir() / f"spacepilot-{uuid.uuid4().hex}.txt"
