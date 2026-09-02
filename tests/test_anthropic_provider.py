"""The Anthropic provider behind `/v1/chat/completions`.

Spec: docs/design/INFERENCE-SURFACE.md, "Remote providers". The real
`anthropic` SDK is never imported here — a fake client stands in at the same
boundary `AnthropicProvider(client=...)` accepts, the same way
test_inference_surface.py mocks MLX-LM's driver rather than running weights.
CI does not install the `anthropic` package at all; every test here has to
work without it.
"""

import json

import pytest
from fastapi.testclient import TestClient

from spacepilot import measurements as ms
from spacepilot.device_probe import DeviceProfile, GIB
from spacepilot.services import anthropic_provider
from spacepilot.web_api import app, STUDIO_TOKEN

client = TestClient(app)
AUTH = {"X-SpacePilot-Token": STUDIO_TOKEN}
MODEL = anthropic_provider.MODEL_ID


def _profile():
    return DeviceProfile(
        chip="Test M1 Max", backend="metal",
        memory_total_bytes=32 * GIB, memory_free_bytes=30 * GIB,
        memory_unified=True, memory_limit_bytes=26_800_603_136,
        memory_limit_source="metal", disk_free_bytes=400 * GIB,
    )


# ------------------------------------------------------------- the fake SDK

class _Block:
    def __init__(self, text):
        self.type = "text"
        self.text = text


class _Usage:
    def __init__(self, input_tokens, output_tokens):
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens


class _StopDetails:
    def __init__(self, category):
        self.category = category


class _Message:
    """Stands in for `anthropic.types.Message`. No network, no real SDK type."""

    def __init__(self, text="Hello from Sonnet.", stop_reason="end_turn",
                 input_tokens=11, output_tokens=6, refusal_category=None):
        self.content = [_Block(text)] if text else []
        self.stop_reason = stop_reason
        self.usage = _Usage(input_tokens, output_tokens)
        self.stop_details = _StopDetails(refusal_category) if stop_reason == "refusal" else None


class _StreamCtx:
    def __init__(self, chunks, final_message):
        self._chunks = chunks
        self._final_message = final_message

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    @property
    def text_stream(self):
        return iter(self._chunks)

    def get_final_message(self):
        return self._final_message


class _Messages:
    def __init__(self, response=None, chunks=None, final_message=None, error=None):
        self._response = response
        self._chunks = chunks or []
        self._final_message = final_message
        self._error = error
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self._error:
            raise self._error
        return self._response

    def stream(self, **kwargs):
        self.calls.append(kwargs)
        if self._error:
            raise self._error
        return _StreamCtx(self._chunks, self._final_message)


class _FakeClient:
    def __init__(self, **kwargs):
        self.messages = _Messages(**kwargs)


@pytest.fixture
def anthropic_key(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-not-a-real-key")


@pytest.fixture
def no_anthropic_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)


def _wire(monkeypatch, fake_client):
    """Point the route at a fixed machine and a fake client. No network."""
    import spacepilot.api.routes.inference as inference

    monkeypatch.setattr(inference, "probe_local_device", _profile)
    monkeypatch.setattr(
        anthropic_provider, "default_provider",
        lambda: anthropic_provider.AnthropicProvider(client=fake_client),
    )
    return fake_client


# --------------------------------------------------------------- dispatch

def test_a_claude_model_dispatches_to_anthropic_not_the_local_registry(anthropic_key, monkeypatch):
    fake = _wire(monkeypatch, _FakeClient(response=_Message()))

    response = client.post("/v1/chat/completions", headers=AUTH, json={
        "model": MODEL, "messages": [{"role": "user", "content": "hi"}],
    })
    assert response.status_code == 200, response.text
    assert fake.messages.calls, "the fake Anthropic client was never called"
    assert fake.messages.calls[0]["model"] == MODEL


def test_an_unknown_claude_model_is_404_not_a_substitution(anthropic_key, monkeypatch):
    fake = _wire(monkeypatch, _FakeClient(response=_Message()))

    response = client.post("/v1/chat/completions", headers=AUTH, json={
        "model": "claude-opus-5", "messages": [{"role": "user", "content": "hi"}],
    })
    assert response.status_code == 404
    assert response.json()["detail"]["error"]["code"] == "model_not_found"
    assert not fake.messages.calls


# ------------------------------------------------------- non-streaming shape

def test_non_streaming_shape_and_extensions(anthropic_key, monkeypatch):
    fake = _wire(monkeypatch, _FakeClient(response=_Message(
        text="Unified memory is one pool.", input_tokens=12, output_tokens=24)))

    response = client.post("/v1/chat/completions", headers=AUTH, json={
        "model": MODEL, "messages": [{"role": "user", "content": "What is unified memory?"}],
    })
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["object"] == "chat.completion"
    assert body["model"] == MODEL
    assert body["choices"][0]["message"]["role"] == "assistant"
    assert body["choices"][0]["message"]["content"] == "Unified memory is one pool."
    assert body["choices"][0]["finish_reason"] == "stop"
    assert body["usage"] == {"prompt_tokens": 12, "completion_tokens": 24, "total_tokens": 36}
    extra = body["x_spacepilot"]
    assert extra["verdict"] == {"level": "remote"}
    assert extra["provider"] == "anthropic"
    assert extra["runtime"] == "anthropic"
    assert extra["tokens_in"] == 12 and extra["tokens_out"] == 24
    assert extra["run_id"] and body["id"].endswith(extra["run_id"])
    assert fake.messages.calls[0]["max_tokens"] == anthropic_provider.DEFAULT_MAX_TOKENS


def test_an_explicit_max_tokens_is_honoured_over_the_default(anthropic_key, monkeypatch):
    fake = _wire(monkeypatch, _FakeClient(response=_Message()))

    client.post("/v1/chat/completions", headers=AUTH, json={
        "model": MODEL, "messages": [{"role": "user", "content": "hi"}], "max_tokens": 42,
    })
    assert fake.messages.calls[0]["max_tokens"] == 42


def test_a_system_message_is_split_out_for_the_sdk(anthropic_key, monkeypatch):
    fake = _wire(monkeypatch, _FakeClient(response=_Message()))

    client.post("/v1/chat/completions", headers=AUTH, json={
        "model": MODEL, "messages": [
            {"role": "system", "content": "Answer in one word."},
            {"role": "user", "content": "Colour of the sky?"},
        ],
    })
    sent = fake.messages.calls[0]
    assert sent["system"] == "Answer in one word."
    assert [m["role"] for m in sent["messages"]] == ["user"]


def test_an_upstream_failure_is_502(anthropic_key, monkeypatch):
    _wire(monkeypatch, _FakeClient(error=RuntimeError("connection reset")))

    response = client.post("/v1/chat/completions", headers=AUTH, json={
        "model": MODEL, "messages": [{"role": "user", "content": "hi"}],
    })
    assert response.status_code == 502
    assert "connection reset" in response.json()["detail"]["error"]["message"]


# ------------------------------------------------------------------ streaming

def test_streaming_is_sse_chunks_then_usage_then_done(anthropic_key, monkeypatch):
    _wire(monkeypatch, _FakeClient(
        chunks=["Unified ", "memory ", "is one pool."],
        final_message=_Message(text="Unified memory is one pool.",
                                input_tokens=9, output_tokens=15)))

    response = client.post("/v1/chat/completions", headers=AUTH, json={
        "model": MODEL, "messages": [{"role": "user", "content": "hello"}], "stream": True,
    })
    assert response.status_code == 200
    lines = [line for line in response.text.splitlines() if line.startswith("data: ")]
    assert lines[-1] == "data: [DONE]"
    payloads = [json.loads(line[len("data: "):]) for line in lines[:-1]]
    assert all(p["object"] == "chat.completion.chunk" for p in payloads)
    text = "".join(p["choices"][0]["delta"].get("content", "") for p in payloads)
    assert text == "Unified memory is one pool."
    assert "usage" not in payloads[0]
    assert payloads[-1]["usage"]["completion_tokens"] == 15
    assert payloads[-1]["x_spacepilot"]["tokens_out"] == 15
    assert payloads[-1]["x_spacepilot"]["verdict"] == {"level": "remote"}
    assert payloads[-1]["x_spacepilot"]["provider"] == "anthropic"
    assert payloads[-1]["choices"][0]["finish_reason"] == "stop"


# --------------------------------------------------------------------- refusal

def test_a_refusal_maps_to_the_spec_error_shape(anthropic_key, monkeypatch):
    _wire(monkeypatch, _FakeClient(response=_Message(
        text="", stop_reason="refusal", refusal_category="cyber",
        input_tokens=8, output_tokens=0)))

    response = client.post("/v1/chat/completions", headers=AUTH, json={
        "model": MODEL, "messages": [{"role": "user", "content": "hi"}],
    })
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["error"]["type"] == "refusal"
    assert detail["error"]["code"] == "refusal"
    assert "cyber" in detail["error"]["message"]


def test_a_refusal_while_streaming_lands_in_band_then_done(anthropic_key, monkeypatch):
    _wire(monkeypatch, _FakeClient(
        chunks=[], final_message=_Message(text="", stop_reason="refusal",
                                           refusal_category="bio")))

    response = client.post("/v1/chat/completions", headers=AUTH, json={
        "model": MODEL, "messages": [{"role": "user", "content": "hi"}], "stream": True,
    })
    assert response.status_code == 200
    lines = [line for line in response.text.splitlines() if line.startswith("data: ")]
    assert lines[-1] == "data: [DONE]"
    payloads = [json.loads(line[len("data: "):]) for line in lines[:-1]]
    assert payloads[-1]["error"]["type"] == "refusal"
    assert "bio" in payloads[-1]["error"]["message"]


# ------------------------------------------------------------------ unconfigured

def test_no_key_is_503_with_provider_unconfigured(no_anthropic_key, monkeypatch):
    import spacepilot.api.routes.inference as inference

    monkeypatch.setattr(inference, "probe_local_device", _profile)
    response = client.post("/v1/chat/completions", headers=AUTH, json={
        "model": MODEL, "messages": [{"role": "user", "content": "hi"}],
    })
    assert response.status_code == 503
    assert response.json()["detail"]["error"]["code"] == "provider_unconfigured"


# ------------------------------------------------------------------- /v1/models

def test_models_lists_claude_only_when_the_key_is_present(anthropic_key, monkeypatch):
    import spacepilot.api.routes.inference as inference

    monkeypatch.setattr(inference, "probe_local_device", _profile)
    body = client.get("/v1/models").json()
    entries = {m["id"]: m for m in body["data"]}
    assert MODEL in entries
    extra = entries[MODEL]["x_spacepilot"]
    assert extra["kind"] == "text"
    assert extra["verdict"]["level"] == "remote"
    assert extra["served"] is True
    assert extra["runtime"] == "anthropic"
    assert entries[MODEL]["owned_by"] == "anthropic"


def test_models_hides_claude_when_the_key_is_absent(no_anthropic_key, monkeypatch):
    import spacepilot.api.routes.inference as inference

    monkeypatch.setattr(inference, "probe_local_device", _profile)
    body = client.get("/v1/models").json()
    assert MODEL not in {m["id"] for m in body["data"]}


# ---------------------------------------------------------------------- token

def test_the_token_gate_still_applies_to_claude_requests(anthropic_key):
    body = {"model": MODEL, "messages": [{"role": "user", "content": "hi"}]}
    assert client.post("/v1/chat/completions", json=body).status_code == 401
    assert client.post(
        "/v1/chat/completions", json=body, headers={"X-SpacePilot-Token": "wrong"},
    ).status_code == 401


# --------------------------------------------------------------------- record

def test_every_anthropic_call_writes_one_measurement(anthropic_key, monkeypatch):
    fake = _wire(monkeypatch, _FakeClient(response=_Message(input_tokens=7, output_tokens=13)))

    recorded = []
    real_record = ms.record

    def _capture(**fields):
        recorded.append(fields)
        return real_record(**fields)

    monkeypatch.setattr(ms, "record", _capture)

    response = client.post("/v1/chat/completions", headers=AUTH, json={
        "model": MODEL, "messages": [{"role": "user", "content": "hi"}],
    })
    assert response.status_code == 200
    assert len(recorded) == 1
    record = recorded[0]
    assert record["metric"] == "tokens_per_second"
    assert record["runtime_id"] == "anthropic"
    assert record["tokens_in"] == 7 and record["tokens_out"] == 13
    assert record["run_id"] == response.json()["x_spacepilot"]["run_id"]
    assert fake.messages.calls  # the call that produced the counts above
