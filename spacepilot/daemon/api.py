"""Separate FastAPI applications for the local and peer trust boundaries."""

from __future__ import annotations

from typing import Any, Callable, Mapping

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict

from spacepilot.pluto.core.utils import allocate_output
from spacepilot.pluto.services.execution import LocalExecutionError, RunRequest
from spacepilot.substrate import Substrate


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PlanBody(_StrictModel):
    workload: str


class RunBody(_StrictModel):
    workload: str
    prompt: str
    output_name: str
    seed: int | None = None


def _picture_route(
    app: FastAPI,
    substrate: Substrate,
    transform: Callable[[Mapping[str, Any]], Mapping[str, Any]] | None = None,
) -> None:
    @app.get("/v1/picture")
    def picture() -> dict[str, Any]:
        value = substrate.picture()
        return dict(transform(value) if transform is not None else value)


def create_local_app(
    substrate: Substrate,
    *,
    shutdown: Callable[[], None] | None = None,
    health_supplier: Callable[[], Mapping[str, Any]] | None = None,
) -> FastAPI:
    """Full local door.  Filesystem permissions on the UDS authenticate it."""
    app = FastAPI(title="SpacePilot local daemon", docs_url=None, redoc_url=None)
    _picture_route(app, substrate)

    @app.get("/healthz")
    def health() -> dict[str, Any]:
        extra = dict(health_supplier()) if health_supplier is not None else {}
        return {"status": "ok", **extra}

    @app.post("/v1/plan")
    def plan(body: PlanBody) -> dict[str, Any]:
        try:
            return substrate.plan(body.workload)
        except (ValueError, LocalExecutionError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/v1/run")
    def run(body: RunBody) -> dict[str, Any]:
        # This is a request-derived filesystem path, so it must cross the same
        # containment boundary as every Studio request.  allocate_output is the
        # new-file counterpart of resolve_output.
        output = allocate_output(body.output_name)
        try:
            return substrate.run(RunRequest(
                workload=body.workload,
                prompt=body.prompt,
                output=output,
                seed=body.seed,
            ))
        except (ValueError, LocalExecutionError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    if shutdown is not None:
        @app.post("/v1/shutdown")
        def request_shutdown() -> dict[str, str]:
            shutdown()
            return {"status": "stopping"}

    return app


def create_peer_app(
    substrate: Substrate,
    *,
    picture_signer: Callable[[Mapping[str, Any]], Mapping[str, Any]] | None = None,
) -> FastAPI:
    """Read-only tailnet door; mutation routes do not exist on this app."""
    app = FastAPI(
        title="SpacePilot peer daemon",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    _picture_route(app, substrate, picture_signer)

    @app.get("/healthz")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app
