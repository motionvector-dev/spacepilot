"""The OpenAI-compatible `/v1` surface.

Spec: `docs/design/INFERENCE-SURFACE.md`.

Shaped like OpenAI's because every coding agent already speaks it — pointing an
existing tool at `http://localhost:8088/v1` should just work. What SpacePilot
adds rides in `x_spacepilot`, namespaced so no client parser trips on it: the
fit verdict, the machine, the runtime, the exact weights, and the run id that
joins this response to the measurement it wrote.
"""

from __future__ import annotations

import json
import time
import uuid
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from spacepilot.api.deps import require_token, update_activity
from spacepilot.device_probe import probe_local_device
from spacepilot import measurements as ms
from spacepilot.model_registry import registry
from spacepilot.services.execution import LocalExecutionError
from spacepilot.verdict import UnknownModel, fit_verdict

router = APIRouter(prefix="/v1", tags=["inference"])

# Kinds this surface serves. `vision` and the media kinds have their own routes
# and their own shapes; listing them here would imply a chat route that is not
# there.
SERVED_KINDS = {"text", "embedding"}


def _error(status: int, message: str, kind: str, code: str,
           extra: Optional[Dict[str, Any]] = None) -> HTTPException:
    """One error shape everywhere: OpenAI's, plus our verdict when we have one."""
    detail: Dict[str, Any] = {"error": {"message": message, "type": kind, "code": code}}
    if extra:
        detail["x_spacepilot"] = extra
    return HTTPException(status_code=status, detail=detail)


def _served_variants() -> Dict[str, Any]:
    """Variant id -> variant, for every kind this surface answers for."""
    return {v.id: v for v in registry().variants if v.kind in SERVED_KINDS}


def _route_for(variant_id: str) -> Optional[str]:
    """The wired execution route for a variant, or None if there is not one.

    Only two variants have one today. A variant with no route is still listed
    by `/v1/models` — it is real, it has a fit verdict, and hiding it would
    make the catalogue lie in the other direction — but it is refused at the
    POST routes rather than silently redirected to a model the caller did not
    ask for.
    """
    from spacepilot.services import embedding_execution, text_execution

    if variant_id == text_execution.VARIANT_ID:
        return "mlx-lm"
    if variant_id == embedding_execution.VARIANT_ID:
        return "mlx-lm"
    return None


@router.get("/models")
def list_models():
    """Every local text and embedding variant, with the shared fit verdict.

    Read-only and free, so it is open like `/api/measurements`.
    """
    profile = probe_local_device()
    system_id = ms.system_from_profile(profile).id
    data = []
    for variant_id, variant in sorted(_served_variants().items()):
        route = _route_for(variant_id)
        data.append({
            "id": variant_id,
            "object": "model",
            "owned_by": variant.family,
            "x_spacepilot": {
                "kind": variant.kind,
                "verdict": fit_verdict(variant_id, profile),
                "system_id": system_id,
                "runtime": route,
                "revision": variant.revision,
                "served": route is not None,
                "license": variant.license.id,
            },
        })
    return {"object": "list", "data": data}


class Message(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: Literal["system", "user", "assistant"]
    content: str


class ChatCompletionRequest(BaseModel):
    # Unknown fields are refused rather than dropped: a caller that sends
    # `top_p` and gets a 200 will believe it took effect.
    model_config = ConfigDict(extra="forbid")
    model: str
    messages: List[Message] = Field(min_length=1)
    max_tokens: int = 256
    temperature: float = 0.0
    stream: bool = False


class EmbeddingsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    model: str
    input: str | List[str]


def _resolve(model_id: str, profile) -> tuple[str, Dict[str, Any]]:
    """Map a requested model to a served variant, or refuse with the reason."""
    variants = _served_variants()
    if model_id not in variants:
        raise _error(404, f"no model {model_id!r}; see GET /v1/models",
                     "invalid_request_error", "model_not_found")
    try:
        verdict = fit_verdict(model_id, profile)
    except UnknownModel:
        raise _error(404, f"no model {model_id!r}; see GET /v1/models",
                     "invalid_request_error", "model_not_found")
    if verdict["level"] == "wont_fit":
        raise _error(409, f"{model_id} will not run on this machine: {verdict['reason']}",
                     "insufficient_capacity", "wont_fit", {"verdict": verdict})
    if _route_for(model_id) is None:
        raise _error(409, f"{model_id} has no wired local route yet; "
                          f"see GET /v1/models for the ones that do",
                     "insufficient_capacity", "no_route", {"verdict": verdict})
    return model_id, verdict


def _extensions(verdict, system_id, revision, run_id, tokens_in, tokens_out,
                wall_seconds) -> Dict[str, Any]:
    return {
        "verdict": verdict,
        "system_id": system_id,
        "runtime": "mlx-lm",
        "revision": revision,
        "run_id": run_id,
        # None, never a guess. A token count derived from characters would read
        # as a measurement while being arithmetic on a string.
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "wall_seconds": wall_seconds,
    }


def _plan_text(model_id: str, verdict):
    from spacepilot.services.text_execution import TextExecutionService

    service = TextExecutionService()
    plan = service.plan("text")
    if plan.selected is None:
        detail = plan.candidates[0].route_detail if plan.candidates else "no candidate"
        raise _error(409, f"{model_id} is not runnable here: {detail}",
                     "insufficient_capacity", "no_route", {"verdict": verdict})
    return service, plan


@router.post("/chat/completions")
def chat_completions(body: ChatCompletionRequest, _: None = Depends(require_token)):
    from spacepilot.services.text_execution import TextRequest, default_text_output

    update_activity()
    profile = probe_local_device()
    model_id, verdict = _resolve(body.model, profile)
    service, plan = _plan_text(model_id, verdict)

    run_id = uuid.uuid4().hex
    messages = tuple(m.model_dump() for m in body.messages)
    request = TextRequest(
        workload="text", prompt=body.messages[-1].content,
        output=default_text_output(), max_tokens=body.max_tokens,
        temperature=body.temperature, run_id=run_id, messages=messages,
    )
    created = int(time.time())

    if body.stream:
        return StreamingResponse(
            _stream_chat(service, plan, request, model_id, verdict,
                         plan.system.id, run_id, created),
            media_type="text/event-stream",
        )

    try:
        result = service.execute(plan, request)
    except LocalExecutionError as exc:
        raise _error(502, str(exc), "driver_error", "execution_failed",
                     {"verdict": verdict, "run_id": run_id})
    except Exception as exc:  # driver subprocess failures carry their own message
        raise _error(502, str(exc), "driver_error", "driver_failed",
                     {"verdict": verdict, "run_id": run_id})

    return {
        "id": f"chatcmpl-{run_id}",
        "object": "chat.completion",
        "created": created,
        "model": model_id,
        "choices": [{
            "index": 0,
            "message": {"role": "assistant", "content": result.output.read_text()},
            "finish_reason": "stop",
        }],
        "usage": {
            "prompt_tokens": result.prompt_tokens,
            "completion_tokens": result.generation_tokens,
            "total_tokens": result.prompt_tokens + result.generation_tokens,
        },
        "x_spacepilot": _extensions(
            verdict, plan.system.id, result.resolved_revision, result.run_id,
            result.prompt_tokens, result.generation_tokens, result.wall_seconds,
        ),
    }


def _sse(payload: Dict[str, Any]) -> str:
    return "data: " + json.dumps(payload, separators=(",", ":")) + "\n\n"


def _stream_chat(service, plan, request, model_id, verdict, system_id, run_id, created):
    """SSE chunks as the driver produces them, then usage, then `[DONE]`.

    Usage and the extensions block ride on the last chunk because the numbers
    do not exist until generation finishes. Emitting them early would mean
    inventing them.
    """
    head = {"id": f"chatcmpl-{run_id}", "object": "chat.completion.chunk",
            "created": created, "model": model_id}
    yield _sse({**head, "choices": [
        {"index": 0, "delta": {"role": "assistant"}, "finish_reason": None}]})
    try:
        for kind, value in service.execute_stream(plan, request):
            if kind == "chunk":
                yield _sse({**head, "choices": [
                    {"index": 0, "delta": {"content": value}, "finish_reason": None}]})
            else:
                yield _sse({
                    **head,
                    "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
                    "usage": {
                        "prompt_tokens": value.prompt_tokens,
                        "completion_tokens": value.generation_tokens,
                        "total_tokens": value.prompt_tokens + value.generation_tokens,
                    },
                    "x_spacepilot": _extensions(
                        verdict, system_id, value.resolved_revision, value.run_id,
                        value.prompt_tokens, value.generation_tokens, value.wall_seconds),
                })
    except Exception as exc:
        # The stream has already returned 200, so the failure has to travel in
        # band. Silence would read to a client as a short but successful answer.
        yield _sse({"error": {"message": str(exc), "type": "driver_error",
                              "code": "execution_failed"},
                    "x_spacepilot": {"run_id": run_id}})
    yield "data: [DONE]\n\n"


@router.post("/embeddings")
def embeddings(body: EmbeddingsRequest, _: None = Depends(require_token)):
    from spacepilot.services.embedding_execution import (
        EmbeddingExecutionService, EmbeddingRequest, default_embedding_output,
    )

    update_activity()
    profile = probe_local_device()
    model_id, verdict = _resolve(body.model, profile)
    inputs = tuple([body.input] if isinstance(body.input, str) else body.input)

    service = EmbeddingExecutionService()
    plan = service.plan()
    if plan.selected is None:
        detail = plan.candidates[0].route_detail if plan.candidates else "no candidate"
        raise _error(409, f"{model_id} is not runnable here: {detail}",
                     "insufficient_capacity", "no_route", {"verdict": verdict})

    run_id = uuid.uuid4().hex
    try:
        result = service.execute(plan, EmbeddingRequest(
            inputs=inputs, output=default_embedding_output(), run_id=run_id,
        ))
    except LocalExecutionError as exc:
        raise _error(400 if "input" in str(exc) else 502, str(exc),
                     "driver_error", "execution_failed",
                     {"verdict": verdict, "run_id": run_id})
    except Exception as exc:
        raise _error(502, str(exc), "driver_error", "driver_failed",
                     {"verdict": verdict, "run_id": run_id})

    return {
        "object": "list",
        "model": model_id,
        "data": [
            {"object": "embedding", "index": i, "embedding": list(vector)}
            for i, vector in enumerate(result.vectors)
        ],
        # Embedding produces no tokens, so completion_tokens is 0 and means it.
        "usage": {"prompt_tokens": result.tokens_in, "total_tokens": result.tokens_in},
        "x_spacepilot": {
            **_extensions(verdict, plan.system.id, result.resolved_revision,
                          result.run_id, result.tokens_in, 0, result.wall_seconds),
            "dimensions": result.dimensions,
        },
    }
