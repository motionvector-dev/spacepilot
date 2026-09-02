"""Separate FastAPI applications for the local and peer trust boundaries."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, ConfigDict

from spacepilot.daemon.log import MAX_RECORDS_PER_PAGE, LogError
from spacepilot.daemon.peer_auth import PEER_AUTH_HEADER, PeerAuthError, PeerAuthenticator
from spacepilot.core.utils import allocate_output
from spacepilot.services.execution import LocalExecutionError, RunRequest
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


class FleetInitBody(_StrictModel):
    name: str


class FleetAddBody(_StrictModel):
    selector: str


class FleetJoinBody(_StrictModel):
    author_key_id: str
    author_selector: str
    fleet_id: str | None = None


@dataclass
class FleetControl:
    """Injected local-only fleet operations; networking is not inferred here."""

    snapshot: Callable[[], Mapping[str, Any]]
    init_handler: Callable[[str], Mapping[str, Any]] | None = None
    add_handler: Callable[[str], Mapping[str, Any]] | None = None
    join_handler: Callable[[str, str, str | None], Mapping[str, Any]] | None = None

    def list(self) -> dict[str, Any]:
        return dict(self.snapshot())

    def init(self, name: str) -> dict[str, Any]:
        if self.init_handler is None:
            raise NotImplementedError("fleet init is unavailable in this daemon")
        return dict(self.init_handler(name))

    def add(self, selector: str) -> dict[str, Any]:
        if self.add_handler is None:
            raise NotImplementedError("fleet add requires an injected bootstrap transport")
        return dict(self.add_handler(selector))

    def join(self, author_key_id: str, author_selector: str,
             fleet_id: str | None = None) -> dict[str, Any]:
        if self.join_handler is None:
            raise NotImplementedError("fleet join requires an injected bootstrap transport")
        return dict(self.join_handler(author_key_id, author_selector, fleet_id))


@dataclass(frozen=True)
class PeerReads:
    self_description: Callable[[], Mapping[str, Any]]
    orders: Callable[[], Mapping[str, Any]]
    log_records: Callable[[str | None, int, int], Mapping[str, Any]]


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
    fleet: FleetControl | None = None,
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

    if fleet is not None:
        @app.post("/v1/fleet/init")
        def fleet_init(body: FleetInitBody) -> dict[str, Any]:
            try:
                return fleet.init(body.name)
            except NotImplementedError as exc:
                raise HTTPException(status_code=503, detail=str(exc)) from exc
            except (ValueError, RuntimeError) as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

        @app.post("/v1/fleet/add")
        def fleet_add(body: FleetAddBody) -> dict[str, Any]:
            try:
                return fleet.add(body.selector)
            except NotImplementedError as exc:
                raise HTTPException(status_code=503, detail=str(exc)) from exc
            except (ValueError, RuntimeError) as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

        @app.post("/v1/fleet/join")
        def fleet_join(body: FleetJoinBody) -> dict[str, Any]:
            try:
                return fleet.join(
                    body.author_key_id, body.author_selector, body.fleet_id,
                )
            except NotImplementedError as exc:
                raise HTTPException(status_code=503, detail=str(exc)) from exc
            except (ValueError, RuntimeError) as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

        @app.get("/v1/fleet")
        def fleet_list() -> dict[str, Any]:
            try:
                return fleet.list()
            except (ValueError, RuntimeError) as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

    return app


def create_peer_app(
    substrate: Substrate,
    *,
    picture_signer: Callable[[Mapping[str, Any]], Mapping[str, Any]] | None = None,
    peer_reads: PeerReads | None = None,
    peer_authenticator: PeerAuthenticator | None = None,
    allow_unauthenticated: bool = False,
) -> FastAPI:
    """Read-only tailnet door; mutation routes do not exist on this app.

    `allow_unauthenticated` exists only for the picture-only adapter tests. A
    security boundary must not open because an argument was forgotten, so the
    opt-out has to be named out loud at the call site.
    """
    app = FastAPI(
        title="SpacePilot peer daemon",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    async def authenticate(request: Request) -> None:
        if peer_authenticator is None:
            # Fail closed. This used to return — serving the signed picture to
            # any tailnet node — whenever both peer_authenticator and peer_reads
            # were absent, so a future caller that forgot one argument would
            # have silently unauthenticated the door while `daemon status` still
            # read "listening". Only an explicit opt-out opens it now.
            if allow_unauthenticated:
                return
            raise HTTPException(status_code=503, detail="peer membership authentication is unavailable")
        header = request.headers.get(PEER_AUTH_HEADER)
        if header is None:
            raise HTTPException(status_code=401, detail="missing peer authentication")
        raw_path = request.scope.get("raw_path", request.url.path.encode("ascii"))
        raw_query = request.scope.get("query_string", b"")
        client = request.client
        if client is None:
            raise HTTPException(status_code=401, detail="peer source address is unavailable")
        try:
            peer_authenticator.verify(
                header,
                method=request.method,
                path=bytes(raw_path).decode("ascii"),
                query=bytes(raw_query).decode("ascii"),
                body=await request.body(),
                source_ip=client.host,
            )
        except (PeerAuthError, UnicodeDecodeError) as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @app.get("/v1/self")
    def self_description() -> dict[str, Any]:
        if peer_reads is None:
            raise HTTPException(status_code=503, detail="fleet bootstrap is unavailable")
        try:
            return dict(peer_reads.self_description())
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @app.get("/v1/picture")
    async def picture(request: Request) -> dict[str, Any]:
        await authenticate(request)
        value = substrate.picture()
        return dict(picture_signer(value) if picture_signer is not None else value)

    @app.get("/v1/orders")
    async def orders(request: Request) -> dict[str, Any]:
        await authenticate(request)
        if peer_reads is None:
            raise HTTPException(status_code=503, detail="fleet membership is unavailable")
        try:
            return dict(peer_reads.orders())
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @app.get("/v1/log/records")
    async def log(request: Request) -> dict[str, Any]:
        await authenticate(request)
        if peer_reads is None:
            raise HTTPException(status_code=503, detail="LOG gossip is unavailable")
        items = list(request.query_params.multi_items())
        allowed = {"epoch", "sequence", "limit"}
        if any(key not in allowed for key, _ in items) or len({key for key, _ in items}) != len(items):
            raise HTTPException(status_code=400, detail="LOG query has duplicate or unknown fields")
        values = dict(items)
        epoch = values.get("epoch")
        if epoch is not None and (not epoch or len(epoch) > 128 or any(ord(ch) < 32 for ch in epoch)):
            raise HTTPException(status_code=400, detail="LOG epoch is invalid")
        if epoch is None and "sequence" in values:
            raise HTTPException(status_code=400, detail="LOG sequence requires an epoch")
        try:
            sequence_text = values.get("sequence", "-1")
            limit_text = values.get("limit", str(MAX_RECORDS_PER_PAGE))
            sequence = int(sequence_text)
            limit = int(limit_text)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="LOG sequence and limit must be integers") from exc
        if str(sequence) != sequence_text or str(limit) != limit_text:
            raise HTTPException(status_code=400, detail="LOG integers must use canonical decimal form")
        if sequence < -1 or not 1 <= limit <= MAX_RECORDS_PER_PAGE:
            raise HTTPException(status_code=400, detail="LOG cursor or limit is outside its bounded range")
        try:
            return dict(peer_reads.log_records(epoch, sequence, limit))
        except (LogError, RuntimeError) as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @app.get("/healthz")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app
