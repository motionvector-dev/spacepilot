"""The OpenAI-compatible /v1 surface, the shared fit verdict, and what it records.

Spec: docs/design/INFERENCE-SURFACE.md.

Every driver is mocked and the machine is a fixture, because these are tests of
the surface's contract. A test that only passes on an Apple M1 Max would go
green on this laptop and prove nothing on the runner.
"""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from spacepilot import measurements as ms
from spacepilot.device_probe import DeviceProfile, GIB
from spacepilot.web_api import app, STUDIO_TOKEN

client = TestClient(app)
AUTH = {"X-SpacePilot-Token": STUDIO_TOKEN}

TEXT_MODEL = "qwen3-8-27b-4bit"
MOE_MODEL = "qwen1-5-moe-a2-7b-chat-4bit"
EMBED_MODEL = "qwen3-embedding-0-6b-8bit"


def _profile():
    return DeviceProfile(
        chip="Apple M1 Max",
        backend="metal",
        memory_total_bytes=32 * GIB,
        memory_free_bytes=30 * GIB,
        memory_unified=True,
        memory_limit_bytes=26_800_603_136,
        memory_limit_source="metal",
        disk_free_bytes=400 * GIB,
    )


# --------------------------------------------------------------- the verdict

def test_the_verdict_vocabulary_is_exactly_these_words():
    from spacepilot.verdict import LEVELS

    assert LEVELS == ("runs_well", "runs_slowly", "wont_fit", "unknown")


@pytest.mark.parametrize("assessed,expected", [
    ("fits", "runs_well"),
    ("tight", "runs_slowly"),
    ("wont_fit", "wont_fit"),
    # The wrong backend is a harder no than running out of memory, not a softer
    # one. Mapping it to anything but wont_fit would offer a CUDA model on a Mac.
    ("blocked", "wont_fit"),
    ("unknown", "unknown"),
])
def test_every_assessment_maps_to_one_shared_word(assessed, expected):
    from types import SimpleNamespace
    from spacepilot.verdict import level_for

    assert level_for(SimpleNamespace(verdict=assessed)) == expected


def test_headroom_is_none_rather_than_zero_when_memory_was_never_read():
    """A headroom computed against a number nobody read is not a small number."""
    from types import SimpleNamespace
    from spacepilot.verdict import _headroom

    assert _headroom(SimpleNamespace(
        usable_memory_bytes=None, working_set_bytes=1)) is None
    assert _headroom(SimpleNamespace(
        usable_memory_bytes=1, working_set_bytes=None)) is None
    assert _headroom(SimpleNamespace(
        usable_memory_bytes=10, working_set_bytes=4)) == 6


def test_a_model_larger_than_the_machine_reports_negative_headroom():
    from spacepilot.verdict import fit_verdict

    small = DeviceProfile(
        chip="Apple M1", backend="metal", memory_total_bytes=8 * GIB,
        memory_free_bytes=6 * GIB, memory_unified=True,
        memory_limit_bytes=5 * GIB, memory_limit_source="metal",
        disk_free_bytes=400 * GIB,
    )
    verdict = fit_verdict(TEXT_MODEL, small)
    assert verdict["level"] == "wont_fit"
    assert verdict["headroom_bytes"] is None or verdict["headroom_bytes"] < 0


def test_an_unknown_model_id_is_a_lookup_error_not_a_guess():
    from spacepilot.verdict import UnknownModel, fit_verdict

    with pytest.raises(UnknownModel):
        fit_verdict("no-such-variant", _profile())


def test_cli_mcp_and_the_api_print_the_same_word(monkeypatch):
    """The failure this exists to stop: three surfaces, three vocabularies.

    Before `fit_verdict` the CLI said `fits`, the MCP tool said "Optimal Local
    Execution", and the API said nothing at all.
    """
    from spacepilot.verdict import fit_verdict
    import spacepilot.api.routes.inference as inference
    import spacepilot.mcp_server as mcp_server
    import spacepilot.device_probe as device_probe

    profile = _profile()
    monkeypatch.setattr(inference, "probe_local_device", lambda: profile)
    monkeypatch.setattr(device_probe, "probe_local_device", lambda: profile)

    direct = fit_verdict(TEXT_MODEL, profile)["level"]

    api = {m["id"]: m for m in client.get("/v1/models").json()["data"]}
    assert api[TEXT_MODEL]["x_spacepilot"]["verdict"]["level"] == direct

    mcp = {m["model_id"]: m for m in mcp_server.spacepilot_recommend_models()["models"]}
    assert mcp[TEXT_MODEL]["verdict"]["level"] == direct


# --------------------------------------------------------------- /v1/models

def test_models_lists_text_and_embeddings_with_a_verdict_each(monkeypatch):
    import spacepilot.api.routes.inference as inference

    # Deterministic regardless of whether this host happens to have
    # ANTHROPIC_API_KEY set: the remote provider's own listing behaviour is
    # covered by tests/test_anthropic_provider.py, not this one.
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(inference, "probe_local_device", _profile)
    body = client.get("/v1/models").json()
    assert body["object"] == "list"
    entries = {m["id"]: m for m in body["data"]}
    assert {TEXT_MODEL, EMBED_MODEL} <= set(entries)
    for entry in body["data"]:
        extra = entry["x_spacepilot"]
        assert extra["kind"] in {"text", "embedding"}
        assert extra["verdict"]["level"] in {
            "runs_well", "runs_slowly", "wont_fit", "unknown"}
        assert set(extra["verdict"]) == {"level", "reason", "headroom_bytes"}
    assert entries[EMBED_MODEL]["x_spacepilot"]["served"] is True
    assert entries[EMBED_MODEL]["x_spacepilot"]["runtime"] == "mlx-lm"


def test_models_serves_every_mlx_lm_text_variant_not_just_the_default(monkeypatch):
    """The daemon used to hardcode one text route; both variants list served now."""
    import spacepilot.api.routes.inference as inference

    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(inference, "probe_local_device", _profile)
    entries = {m["id"]: m for m in client.get("/v1/models").json()["data"]}
    for model_id in (TEXT_MODEL, MOE_MODEL):
        extra = entries[model_id]["x_spacepilot"]
        assert extra["served"] is True
        assert extra["runtime"] == "mlx-lm"


def test_models_is_open_because_it_spends_nothing():
    assert client.get("/v1/models").status_code == 200


def test_a_variant_with_no_wired_route_says_so_rather_than_hiding(monkeypatch):
    """Listing only what we can run would make the catalogue lie the other way."""
    import spacepilot.api.routes.inference as inference

    monkeypatch.setattr(inference, "probe_local_device", _profile)
    entries = {m["id"]: m for m in client.get("/v1/models").json()["data"]}
    unwired = entries["deepseek-r1-distill-qwen-7b"]["x_spacepilot"]
    assert unwired["served"] is False
    assert unwired["runtime"] is None


def test_models_estimate_uses_measured_tokens_per_second_when_available(monkeypatch):
    """AgentWorth's archie refuses to run without a pre-run estimate; this is it."""
    import spacepilot.api.routes.inference as inference
    from spacepilot.services import corpus

    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(inference, "probe_local_device", _profile)
    system_id = ms.system_from_profile(_profile()).id
    records = [
        ms.Measurement(
            schema=1, system_id=system_id, model_id=TEXT_MODEL, variant_id=TEXT_MODEL,
            metric="tokens_per_second", value=42.0, contention="solo",
            measured_on="2026-09-01T00:00:00+00:00",
        ),
    ]
    monkeypatch.setattr(corpus.ms, "load_measurements", lambda: records)
    entries = {m["id"]: m for m in client.get("/v1/models").json()["data"]}
    assert entries[TEXT_MODEL]["x_spacepilot"]["estimate"] == {
        "decode_tokens_per_second": 42.0, "sample_count": 1, "cost_usd": 0.0,
        "source": "measured", "reason": None,
    }


def test_models_estimate_is_unmeasured_with_a_reason_when_nothing_recorded_yet(monkeypatch):
    """A caller that refuses to run on anything but 'measured' should refuse here."""
    import spacepilot.api.routes.inference as inference
    from spacepilot.services import corpus

    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(inference, "probe_local_device", _profile)
    monkeypatch.setattr(corpus.ms, "load_measurements", list)
    entries = {m["id"]: m for m in client.get("/v1/models").json()["data"]}
    assert entries[TEXT_MODEL]["x_spacepilot"]["estimate"] == {
        "decode_tokens_per_second": None, "sample_count": 0, "cost_usd": 0.0,
        "source": "unmeasured", "reason": "no measurements recorded yet for this system",
    }


def test_remote_model_estimate_defers_the_pricing_decision(monkeypatch):
    """Local runs are free; what an external caller pays for Claude is not decided.

    This must never quietly become 0.0 — that would tell a caller Claude calls
    are free, which is exactly the unresolved DECISION-INBOX question. And it
    must never read as "unmeasured" — that would say "run it once and this
    clears," when the real blocker is a policy decision, not a missing sample.
    """
    import spacepilot.api.routes.inference as inference
    from spacepilot.services import anthropic_provider, corpus

    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-not-a-real-key")
    monkeypatch.setattr(inference, "probe_local_device", _profile)
    monkeypatch.setattr(corpus.ms, "load_measurements", list)
    entries = {m["id"]: m for m in client.get("/v1/models").json()["data"]}
    estimate = entries[anthropic_provider.MODEL_ID]["x_spacepilot"]["estimate"]
    assert estimate["cost_usd"] is None
    assert estimate["decode_tokens_per_second"] is None
    assert estimate["source"] == "policy_undecided"
    assert "DECISION-INBOX" in estimate["reason"]


# ------------------------------------------------------- dry_run pre-run estimate

def test_dry_run_local_counts_real_prompt_tokens_and_uses_both_medians(monkeypatch):
    """archie's actual ask: seconds a caller can refuse a run on, from one call."""
    import spacepilot.api.routes.inference as inference
    from spacepilot.services import corpus

    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(inference, "probe_local_device", _profile)
    system_id = ms.system_from_profile(_profile()).id
    records = [
        ms.Measurement(
            schema=1, system_id=system_id, model_id=TEXT_MODEL, variant_id=TEXT_MODEL,
            metric="prompt_tokens_per_second", value=1000.0, contention="solo",
            measured_on="2026-09-01T00:00:00+00:00",
        ),
        ms.Measurement(
            schema=1, system_id=system_id, model_id=TEXT_MODEL, variant_id=TEXT_MODEL,
            metric="tokens_per_second", value=50.0, contention="solo",
            measured_on="2026-09-01T00:00:00+00:00",
        ),
    ]
    monkeypatch.setattr(corpus.ms, "load_measurements", lambda: records)
    from spacepilot.drivers.mlx_lm_driver import MlxLmDriver
    monkeypatch.setattr(MlxLmDriver, "count_prompt_tokens", lambda self, messages, variant_id=None: 1000)

    body = {"model": TEXT_MODEL, "messages": [{"role": "user", "content": "hi"}],
            "max_tokens": 100, "x_spacepilot": {"dry_run": True}}
    response = client.post("/v1/chat/completions", json=body, headers=AUTH)
    assert response.status_code == 200
    payload = response.json()
    assert payload["object"] == "chat.completion.dry_run"
    estimate = payload["x_spacepilot"]["estimate"]
    assert estimate["prompt_tokens"] == 1000
    assert estimate["max_completion_tokens"] == 100
    # 1000 prompt tokens / 1000 tps + 100 max tokens / 50 tps = 1 + 2 = 3
    assert estimate["seconds"] == pytest.approx(3.0)
    assert estimate["cost_usd"] == 0.0
    assert estimate["source"] == "measured"
    assert estimate["sample_count"] == 1


def test_dry_run_local_is_unmeasured_when_weights_are_not_cached(monkeypatch):
    import spacepilot.api.routes.inference as inference
    from spacepilot.services import corpus
    from spacepilot.drivers.mlx_lm_driver import MlxLmDriver

    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(inference, "probe_local_device", _profile)
    monkeypatch.setattr(corpus.ms, "load_measurements", list)
    monkeypatch.setattr(MlxLmDriver, "count_prompt_tokens", lambda self, messages, variant_id=None: None)

    body = {"model": TEXT_MODEL, "messages": [{"role": "user", "content": "hi"}],
            "x_spacepilot": {"dry_run": True}}
    estimate = client.post("/v1/chat/completions", json=body, headers=AUTH
                           ).json()["x_spacepilot"]["estimate"]
    assert estimate["prompt_tokens"] is None
    assert estimate["seconds"] is None
    assert estimate["source"] == "unmeasured"
    assert estimate["reason"] == "weights are not cached locally yet"


def test_dry_run_spends_no_generation_no_measurement_is_recorded(monkeypatch):
    """A caller pricing out a call before running it must not itself cost anything."""
    import spacepilot.api.routes.inference as inference
    from spacepilot.services import corpus
    from spacepilot.drivers.mlx_lm_driver import MlxLmDriver

    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(inference, "probe_local_device", _profile)
    monkeypatch.setattr(corpus.ms, "load_measurements", list)
    monkeypatch.setattr(MlxLmDriver, "count_prompt_tokens", lambda self, messages, variant_id=None: 10)
    recorded = []
    monkeypatch.setattr(corpus.ms, "record", lambda **kw: recorded.append(kw))

    body = {"model": TEXT_MODEL, "messages": [{"role": "user", "content": "hi"}],
            "x_spacepilot": {"dry_run": True}}
    client.post("/v1/chat/completions", json=body, headers=AUTH)
    assert recorded == []


def test_dry_run_remote_refuses_on_policy_not_measurement(monkeypatch):
    """Claude's dry run must never imply 'run it once and it clears' — it can't."""
    import spacepilot.api.routes.inference as inference
    from spacepilot.services import anthropic_provider

    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-not-a-real-key")
    monkeypatch.setattr(inference, "probe_local_device", _profile)

    body = {"model": anthropic_provider.MODEL_ID,
            "messages": [{"role": "user", "content": "hi"}],
            "x_spacepilot": {"dry_run": True}}
    payload = client.post("/v1/chat/completions", json=body, headers=AUTH).json()
    estimate = payload["x_spacepilot"]["estimate"]
    assert estimate["source"] == "policy_undecided"
    assert estimate["cost_usd"] is None
    assert estimate["seconds"] is None
    assert "DECISION-INBOX" in estimate["reason"]


def test_an_unknown_dry_run_field_is_refused_rather_than_ignored():
    body = {"model": TEXT_MODEL, "messages": [{"role": "user", "content": "hi"}],
            "x_spacepilot": {"dry_run": True, "top_p": 0.9}}
    response = client.post("/v1/chat/completions", json=body, headers=AUTH)
    assert response.status_code == 422


# ------------------------------------------------------------ chat and embed

class _TextDriver:
    """Stands in for the MLX subprocess. Same payload, no weights."""

    def __init__(self, text="Unified memory is one pool.\n"):
        self.text = text
        self.calls = []

    def route_status(self, variant_id):
        return True, "ready — pinned cache via mlx-lm"

    def _payload(self):
        return {
            "status": "completed",
            "model_revision": "3e6447f082e89cc7f0bc6e5441afd38dfce760ff",
            "wall_seconds": 12.0, "load_seconds": 8.0,
            "prompt_tokens": 12, "prompt_tps": 40.0,
            "generation_tokens": 24, "generation_tps": 6.5,
            "peak_memory_gb": 18.25,
        }

    def infer(self, **kwargs):
        self.calls.append(kwargs)
        Path(kwargs["out_path"]).write_text(self.text)
        return self._payload()

    def stream(self, **kwargs):
        self.calls.append(kwargs)
        for word in self.text.split(" "):
            yield {"type": "chunk", "text": word + " "}
        Path(kwargs["out_path"]).write_text(self.text)
        yield {"type": "result", "result": self._payload()}


class _EmbedDriver:
    def __init__(self, dimensions=4):
        self.dimensions = dimensions
        self.calls = []

    def route_status(self, variant_id):
        return True, "ready — pinned cache via mlx-lm"

    def infer(self, **kwargs):
        self.calls.append(kwargs)
        vectors = [[1.0] + [0.0] * (self.dimensions - 1) for _ in kwargs["inputs"]]
        Path(kwargs["out_path"]).write_text(json.dumps(
            {"dimensions": self.dimensions, "vectors": vectors}))
        return {
            "status": "completed", "model_revision": "407ad2329cd307027",
            "wall_seconds": 1.0, "load_seconds": 0.8,
            "tokens_in": 7 * len(kwargs["inputs"]),
            "dimensions": self.dimensions, "count": len(kwargs["inputs"]),
            "peak_memory_gb": 0.62,
        }


@pytest.fixture
def wired(monkeypatch, tmp_path):
    """Both routes, on a fixed machine, with mocked drivers and a captured record."""
    import spacepilot.api.routes.inference as inference
    import spacepilot.services.embedding_execution as embed
    import spacepilot.services.text_execution as text

    recorded = []
    profile = _profile()
    monkeypatch.setattr(inference, "probe_local_device", lambda: profile)

    text_driver = _TextDriver()
    embed_driver = _EmbedDriver()

    # Bind the real classes before patching: the factories below look their
    # names up at call time, so reading them through the module afterwards
    # would find the factory and recurse.
    real_text = text.TextExecutionService
    real_embed = embed.EmbeddingExecutionService

    def _record(**fields):
        recorded.append(fields)
        return tmp_path / "measurement.yaml"

    def _text_service():
        return real_text(
            driver=text_driver, profile_probe=lambda: profile,
            measurement_loader=lambda: [], measurement_recorder=_record,
            system_writer=lambda *a, **kw: tmp_path / "system.yaml",
            contention_sampler=lambda: "solo",
        )

    def _embed_service():
        return real_embed(
            driver=embed_driver, profile_probe=lambda: profile,
            measurement_recorder=_record,
            system_writer=lambda *a, **kw: tmp_path / "system.yaml",
            contention_sampler=lambda: "solo",
        )

    monkeypatch.setattr(text, "TextExecutionService", _text_service)
    monkeypatch.setattr(embed, "EmbeddingExecutionService", _embed_service)
    return {"recorded": recorded, "text": text_driver, "embed": embed_driver}


def test_chat_completion_returns_the_openai_shape_plus_our_extensions(wired):
    response = client.post("/v1/chat/completions", headers=AUTH, json={
        "model": TEXT_MODEL,
        "messages": [{"role": "user", "content": "What is unified memory?"}],
        "max_tokens": 64,
    })
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["object"] == "chat.completion"
    assert body["model"] == TEXT_MODEL
    assert body["choices"][0]["message"]["role"] == "assistant"
    assert body["choices"][0]["message"]["content"].startswith("Unified memory")
    assert body["usage"] == {
        "prompt_tokens": 12, "completion_tokens": 24, "total_tokens": 36}
    extra = body["x_spacepilot"]
    assert extra["runtime"] == "mlx-lm"
    assert extra["system_id"] == "apple-m1-max-32gb"
    assert extra["revision"] == "3e6447f082e89cc7f0bc6e5441afd38dfce760ff"
    assert extra["tokens_in"] == 12 and extra["tokens_out"] == 24
    assert extra["wall_seconds"] == 12.0
    assert extra["verdict"]["level"] in {"runs_well", "runs_slowly"}
    assert extra["run_id"] and body["id"].endswith(extra["run_id"])


def test_chat_completion_serves_the_moe_variant_through_the_same_route(wired):
    """Not just the default text model — every mlx-lm text variant answers."""
    response = client.post("/v1/chat/completions", headers=AUTH, json={
        "model": MOE_MODEL,
        "messages": [{"role": "user", "content": "What is unified memory?"}],
        "max_tokens": 64,
    })
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["model"] == MOE_MODEL
    assert body["x_spacepilot"]["runtime"] == "mlx-lm"
    assert wired["text"].calls[0]["variant_id"] == MOE_MODEL
    assert wired["recorded"][0]["variant_id"] == MOE_MODEL


def test_the_whole_message_list_reaches_the_driver(wired):
    """Flattening a chat to its last turn drops the system prompt silently."""
    client.post("/v1/chat/completions", headers=AUTH, json={
        "model": TEXT_MODEL,
        "messages": [
            {"role": "system", "content": "Answer in one word."},
            {"role": "user", "content": "Colour of the sky?"},
        ],
    })
    sent = wired["text"].calls[0]["messages"]
    assert [m["role"] for m in sent] == ["system", "user"]
    assert sent[0]["content"] == "Answer in one word."


def test_streaming_is_sse_chunks_then_usage_then_done(wired):
    response = client.post("/v1/chat/completions", headers=AUTH, json={
        "model": TEXT_MODEL,
        "messages": [{"role": "user", "content": "hello"}],
        "stream": True,
    })
    assert response.status_code == 200
    lines = [line for line in response.text.splitlines() if line.startswith("data: ")]
    assert lines[-1] == "data: [DONE]"
    payloads = [json.loads(line[len("data: "):]) for line in lines[:-1]]
    assert all(p["object"] == "chat.completion.chunk" for p in payloads)
    text = "".join(p["choices"][0]["delta"].get("content", "") for p in payloads)
    assert text.startswith("Unified memory")
    # Usage exists only once generation finishes, so it rides the last chunk.
    assert "usage" not in payloads[0]
    assert payloads[-1]["usage"]["completion_tokens"] == 24
    assert payloads[-1]["x_spacepilot"]["tokens_out"] == 24
    assert payloads[-1]["choices"][0]["finish_reason"] == "stop"


def test_embeddings_returns_one_vector_per_input(wired):
    response = client.post("/v1/embeddings", headers=AUTH, json={
        "model": EMBED_MODEL, "input": ["first text", "second text"],
    })
    assert response.status_code == 200, response.text
    body = response.json()
    assert [row["index"] for row in body["data"]] == [0, 1]
    assert len(body["data"][0]["embedding"]) == 4
    assert body["usage"]["prompt_tokens"] == 14
    assert body["x_spacepilot"]["dimensions"] == 4
    assert body["x_spacepilot"]["tokens_out"] == 0


def test_embeddings_accepts_a_bare_string(wired):
    response = client.post("/v1/embeddings", headers=AUTH, json={
        "model": EMBED_MODEL, "input": "one text",
    })
    assert response.status_code == 200
    assert len(response.json()["data"]) == 1


# ------------------------------------------------------------------- refusals

def test_an_unknown_model_is_404_not_a_substitution(wired):
    response = client.post("/v1/chat/completions", headers=AUTH, json={
        "model": "gpt-4o", "messages": [{"role": "user", "content": "hi"}],
    })
    assert response.status_code == 404
    assert response.json()["detail"]["error"]["code"] == "model_not_found"


def test_a_model_with_no_route_is_409_and_carries_the_verdict(wired):
    response = client.post("/v1/chat/completions", headers=AUTH, json={
        "model": "deepseek-r1-distill-qwen-7b",
        "messages": [{"role": "user", "content": "hi"}],
    })
    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["error"]["code"] == "no_route"
    assert detail["x_spacepilot"]["verdict"]["level"] in {
        "runs_well", "runs_slowly", "wont_fit", "unknown"}


def test_a_model_too_big_for_the_machine_is_409_with_the_reason(monkeypatch, wired):
    import spacepilot.api.routes.inference as inference

    monkeypatch.setattr(inference, "probe_local_device", lambda: DeviceProfile(
        chip="Apple M1", backend="metal", memory_total_bytes=8 * GIB,
        memory_free_bytes=6 * GIB, memory_unified=True,
        memory_limit_bytes=5 * GIB, memory_limit_source="metal",
        disk_free_bytes=400 * GIB,
    ))
    response = client.post("/v1/chat/completions", headers=AUTH, json={
        "model": TEXT_MODEL, "messages": [{"role": "user", "content": "hi"}],
    })
    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["error"]["code"] == "wont_fit"
    assert detail["x_spacepilot"]["verdict"]["level"] == "wont_fit"
    assert detail["error"]["message"].count(":") >= 1


def test_an_unknown_knob_is_refused_rather_than_ignored(wired):
    """A caller that sends top_p and gets a 200 believes it took effect."""
    response = client.post("/v1/chat/completions", headers=AUTH, json={
        "model": TEXT_MODEL, "messages": [{"role": "user", "content": "hi"}],
        "top_p": 0.1,
    })
    assert response.status_code == 422


def test_both_post_routes_need_the_token():
    for path, body in [
        ("/v1/chat/completions",
         {"model": TEXT_MODEL, "messages": [{"role": "user", "content": "hi"}]}),
        ("/v1/embeddings", {"model": EMBED_MODEL, "input": "hi"}),
    ]:
        assert client.post(path, json=body).status_code == 401
        assert client.post(
            path, json=body, headers={"X-SpacePilot-Token": "wrong"}
        ).status_code == 401


# --------------------------------------------------------------- the record

def test_every_served_call_records_run_id_and_both_token_counts(wired):
    client.post("/v1/chat/completions", headers=AUTH, json={
        "model": TEXT_MODEL, "messages": [{"role": "user", "content": "hi"}],
    })
    client.post("/v1/embeddings", headers=AUTH, json={
        "model": EMBED_MODEL, "input": "hi",
    })
    # Two rows per chat completion now: decode speed and prefill speed are
    # different phases with different costs, so each gets its own median.
    assert len(wired["recorded"]) == 3
    chat_decode, chat_prefill, embed = wired["recorded"]
    assert chat_decode["metric"] == "tokens_per_second"
    assert chat_decode["run_id"] and chat_decode["tokens_in"] == 12 and chat_decode["tokens_out"] == 24
    assert chat_prefill["metric"] == "prompt_tokens_per_second"
    assert chat_prefill["run_id"] == chat_decode["run_id"]
    assert embed["metric"] == "tokens_per_second"
    # Embedding consumes tokens and produces none. Zero, not null: the driver
    # counted, and the answer was zero.
    assert embed["run_id"] and embed["tokens_in"] == 7 and embed["tokens_out"] == 0


def test_the_response_and_the_record_name_the_same_run(wired):
    body = client.post("/v1/chat/completions", headers=AUTH, json={
        "model": TEXT_MODEL, "messages": [{"role": "user", "content": "hi"}],
    }).json()
    assert wired["recorded"][0]["run_id"] == body["x_spacepilot"]["run_id"]


def test_the_new_measurement_fields_survive_a_write_and_a_read(tmp_path):
    # A fake id on purpose, not "apple-m1-max-32gb": this already writes under
    # an explicit root=tmp_path, but a real-looking id here is a landmine for
    # whoever next simplifies this test and drops that root=.
    system = ms.System(id="spacepilot-test-fixture", backend="metal")
    path = ms.record(
        system=system, model_id=TEXT_MODEL, variant_id=TEXT_MODEL,
        metric="tokens_per_second", value=6.5, contention="solo",
        root=tmp_path, run_id="abc123", tokens_in=12, tokens_out=24,
    )
    [loaded] = ms.load_measurements(root=tmp_path)
    assert loaded.run_id == "abc123"
    assert loaded.tokens_in == 12 and loaded.tokens_out == 24
    assert path.exists()


def test_a_record_without_the_new_fields_still_parses():
    """Every measurement written before today has to keep counting."""
    older = ms.parse_measurement({
        "schema": ms.SCHEMA_VERSION, "system_id": "s", "model_id": "m",
        "metric": "tokens_per_second", "value": 1.0, "contention": "solo",
        "measured_on": "2026-08-01T00:00:00+00:00",
    }, "in-memory")
    assert older.run_id is None
    assert older.tokens_in is None and older.tokens_out is None
