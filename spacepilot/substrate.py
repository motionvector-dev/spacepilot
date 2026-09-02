"""One execution contract with direct and daemon-backed transports.

The wire-shaped dictionaries are intentional.  ``DirectLocal`` normalises
through the same representation as ``DaemonClient``, so parity tests compare
operational facts rather than Python implementation details such as ``Path``
versus JSON strings.  A daemon transport failure is never retried locally: a
lost response may mean the run happened, and repeating it would be ambiguous.
"""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable, Mapping, Protocol

import httpx

from spacepilot.services.execution import (
    LocalExecutionService,
    RunPlan,
    RunRequest,
    RunResult,
)
from spacepilot.paths import outputs_dir


class SubstrateError(RuntimeError):
    """A substrate request failed or returned a malformed response."""


class Substrate(Protocol):
    def picture(self) -> dict[str, Any]: ...
    def plan(self, workload: str) -> dict[str, Any]: ...
    def run(self, request: RunRequest) -> dict[str, Any]: ...


def plan_to_wire(plan: RunPlan) -> dict[str, Any]:
    """The stable, JSON-safe facts a caller needs to confirm a run."""
    candidates: list[dict[str, Any]] = []
    for candidate in plan.candidates:
        speed = None
        if candidate.speed is not None:
            speed = asdict(candidate.speed)
        candidates.append({
            "variant_id": candidate.variant.id,
            "model_alias": candidate.route.model_alias,
            "verdict": candidate.verdict.verdict,
            "reason": candidate.verdict.reason,
            "route_state": candidate.route_state,
            "can_run": candidate.can_run,
            "speed": speed,
            "caveats": [asdict(caveat) for caveat in candidate.non_safe_caveats],
        })
    selected = plan.selected
    return {
        "workload": plan.workload,
        "system": plan.system.to_dict(),
        "candidates": candidates,
        "selected_variant_id": selected.variant.id if selected else None,
    }


def result_to_wire(result: RunResult) -> dict[str, Any]:
    return {
        "status": result.status,
        "variant_id": result.variant_id,
        "model_alias": result.model_alias,
        "output": str(result.output),
        "resolved_revision": result.resolved_revision,
        "wall_seconds": result.wall_seconds,
        "seconds_per_image": result.seconds_per_image,
        "measurement_path": (
            str(result.measurement_path) if result.measurement_path is not None else None
        ),
        "timing_source": result.timing_source,
    }


class DirectLocal:
    """In-process adapter over the Phase 2.5 execution service."""

    def __init__(
        self,
        service: LocalExecutionService,
        *,
        picture_supplier: Callable[[], Mapping[str, Any]] | None = None,
    ) -> None:
        self.service = service
        self.picture_supplier = picture_supplier

    def picture(self) -> dict[str, Any]:
        if self.picture_supplier is None:
            raise SubstrateError("this direct substrate has no picture supplier")
        return dict(self.picture_supplier())

    def plan(self, workload: str) -> dict[str, Any]:
        return plan_to_wire(self.service.plan(workload))

    def run(self, request: RunRequest) -> dict[str, Any]:
        # Planning and execution stay in the service.  In particular this does
        # not duplicate route selection in the daemon/API layer.
        plan = self.service.plan(request.workload)
        return result_to_wire(self.service.execute(plan, request))


class DaemonClient:
    """Synchronous HTTP-over-UDS client for the local daemon door."""

    def __init__(
        self,
        socket_path: Path | str,
        *,
        timeout: float = 30.0,
        output_root: Path | str | None = None,
    ) -> None:
        self.socket_path = Path(socket_path)
        self.timeout = timeout
        self.output_root = Path(output_root) if output_root is not None else outputs_dir()

    def _request(self, method: str, path: str, *, json: Any = None) -> dict[str, Any]:
        transport = httpx.HTTPTransport(uds=str(self.socket_path))
        try:
            with httpx.Client(
                transport=transport,
                base_url="http://spacepilot.local",
                timeout=self.timeout,
            ) as client:
                response = client.request(method, path, json=json)
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, OSError, ValueError) as exc:
            # Never fall back to DirectLocal here.  For POST /v1/run, a broken
            # response is an ambiguous outcome and a retry may execute twice.
            raise SubstrateError(f"daemon request {method} {path} failed: {exc}") from exc
        if not isinstance(payload, dict):
            raise SubstrateError(f"daemon returned a non-object for {method} {path}")
        return payload

    def picture(self) -> dict[str, Any]:
        return self._request("GET", "/v1/picture")

    def health(self) -> dict[str, Any]:
        return self._request("GET", "/healthz")

    def plan(self, workload: str) -> dict[str, Any]:
        return self._request("POST", "/v1/plan", json={"workload": workload})

    def run(self, request: RunRequest) -> dict[str, Any]:
        output = Path(request.output).expanduser()
        if output.is_absolute():
            try:
                relative = output.resolve().relative_to(self.output_root.resolve())
            except ValueError as exc:
                raise SubstrateError(
                    f"daemon output must be inside {self.output_root}: {output}"
                ) from exc
        else:
            relative = output
        if not relative.parts or any(part in {"", ".", ".."} for part in relative.parts):
            raise SubstrateError(f"daemon output is not a safe relative name: {output}")
        return self._request("POST", "/v1/run", json={
            "workload": request.workload,
            "prompt": request.prompt,
            "output_name": relative.as_posix(),
            "seed": request.seed,
        })

    def shutdown(self) -> dict[str, Any]:
        return self._request("POST", "/v1/shutdown")
