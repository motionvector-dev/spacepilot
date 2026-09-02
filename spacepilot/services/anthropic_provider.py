"""Anthropic Claude as a second, remote backend behind `/v1/chat/completions`.

Spec: `docs/design/INFERENCE-SURFACE.md`, "Remote providers". This is the
ladder's third rung arriving early: while the local rungs (`mlx-lm`, later
gguf/CoreAI) run on this machine and earn a fit verdict, a `claude-*` model
never runs here, so it skips `fit_verdict` entirely and reports
`x_spacepilot.verdict = {"level": "remote"}` instead of a guess dressed up as
one.

The official `anthropic` SDK is imported lazily, inside `_get_client`, never
at module level. It ships behind the `cloud` extra in `pyproject.toml` and is
not installed in CI — CI mocks the client boundary (`AnthropicProvider(client=...)`)
and never exercises the real import, the same way the local drivers are
mocked rather than run.

The API key is read from `ANTHROPIC_API_KEY` at request time via the SDK's own
environment resolution. It is never stored on this object, never logged, and
never placed in an error body — only `str(exc)` from the SDK's own exception
travels back, and the SDK does not echo the key into its messages.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any, Dict, Iterator, List, Optional, Tuple

MODEL_ID = "claude-sonnet-5"
RUNTIME_ID = "anthropic"

# The SDK truncates non-streaming requests it estimates will run past the
# read timeout; streaming has no such ceiling. ~16000 keeps a bounded chat
# turn comfortably under that without inviting mid-thought truncation from a
# too-low cap. See claude-api skill, "Common Pitfalls" -> max_tokens defaults.
DEFAULT_MAX_TOKENS = 16000


class AnthropicProviderError(RuntimeError):
    """The Anthropic call could not be made or did not complete.

    The message is always built from the SDK's own exception text or an
    internal invariant ("no key"); it never carries the key itself.
    """


def api_key_present() -> bool:
    """Whether this machine can even attempt a claude-* call right now.

    `GET /v1/models` uses this to decide whether to list the model at all —
    an offline machine must never advertise a model it cannot serve.
    """
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


@dataclass(frozen=True)
class AnthropicResult:
    content: str
    finish_reason: str  # "stop" or "refusal"
    tokens_in: int
    tokens_out: int
    wall_seconds: float
    refusal_category: Optional[str] = None


def _split_system(messages) -> Tuple[Optional[str], List[Dict[str, str]]]:
    """Anthropic takes the system prompt out-of-band; OpenAI's shape does not.

    A caller may send more than one `system` message (the local route accepts
    it too); they concatenate in order rather than the last one winning
    silently.
    """
    system: Optional[str] = None
    turns: List[Dict[str, str]] = []
    for message in messages:
        role = message["role"] if isinstance(message, dict) else message.role
        content = message["content"] if isinstance(message, dict) else message.content
        if role == "system":
            system = content if system is None else f"{system}\n{content}"
            continue
        turns.append({"role": role, "content": content})
    return system, turns


def _to_result(response, wall_seconds: float) -> AnthropicResult:
    text = "".join(
        block.text for block in response.content if getattr(block, "type", None) == "text"
    )
    refusal_category = None
    if response.stop_reason == "refusal":
        finish_reason = "refusal"
        details = getattr(response, "stop_details", None)
        refusal_category = getattr(details, "category", None) if details else None
    else:
        finish_reason = "stop"
    usage = response.usage
    return AnthropicResult(
        content=text,
        finish_reason=finish_reason,
        tokens_in=usage.input_tokens,
        tokens_out=usage.output_tokens,
        wall_seconds=wall_seconds,
        refusal_category=refusal_category,
    )


class AnthropicProvider:
    """Wraps `anthropic.Anthropic()`. Inject `client` in tests; never mocked here."""

    def __init__(self, *, client: Any = None) -> None:
        self._client = client

    def _get_client(self):
        if self._client is not None:
            return self._client
        if not api_key_present():
            raise AnthropicProviderError("ANTHROPIC_API_KEY is not set")
        import anthropic  # optional dependency; see module docstring

        self._client = anthropic.Anthropic()
        return self._client

    def complete(self, *, messages, max_tokens: int, temperature: float) -> AnthropicResult:
        """One bounded, non-streaming turn. Adaptive thinking is left implicit —
        omitting `thinking` on Sonnet 5 already runs it."""
        client = self._get_client()
        system, turns = _split_system(messages)
        kwargs: Dict[str, Any] = dict(
            model=MODEL_ID, max_tokens=max_tokens, temperature=temperature, messages=turns,
        )
        if system:
            kwargs["system"] = system
        started = time.perf_counter()
        try:
            response = client.messages.create(**kwargs)
        except Exception as exc:  # the SDK's own exception; never the key
            raise AnthropicProviderError(str(exc)) from exc
        return _to_result(response, time.perf_counter() - started)

    def stream_complete(
        self, *, messages, max_tokens: int, temperature: float,
    ) -> Iterator[Tuple[str, Any]]:
        """Yields `("chunk", text)` per delta, then `("result", AnthropicResult)`.

        Uses `.text_stream` for the deltas and `.get_final_message()` for the
        completed message — the SDK helper the claude-api skill recommends
        over hand-parsing raw stream events.
        """
        client = self._get_client()
        system, turns = _split_system(messages)
        kwargs: Dict[str, Any] = dict(
            model=MODEL_ID, max_tokens=max_tokens, temperature=temperature, messages=turns,
        )
        if system:
            kwargs["system"] = system
        started = time.perf_counter()
        try:
            with client.messages.stream(**kwargs) as stream:
                for text in stream.text_stream:
                    yield "chunk", text
                response = stream.get_final_message()
        except Exception as exc:
            raise AnthropicProviderError(str(exc)) from exc
        yield "result", _to_result(response, time.perf_counter() - started)


def default_provider() -> AnthropicProvider:
    """The seam the route calls through. Tests monkeypatch this, not the SDK."""
    return AnthropicProvider()
