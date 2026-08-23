"""Tests for tools/verify_claims.py.

The one thing that must never regress: a model that fabricates a citation
gets caught mechanically, by fetching the URL and string-matching the quote,
not by trusting the model's own "supported"/"refuted" label. Everything else
in this file is secondary to that gate.
"""

import asyncio
import sys
from pathlib import Path

import pytest

PLUTO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PLUTO_ROOT))

from tools import verify_claims as vc  # noqa: E402


REAL_PAGE = """
<html><body>
<h1>Pricing</h1>
<p>Official Models cost $0.09 to $0.25 per second of
   generated video, billed per second.</p>
</body></html>
"""


def make_verdict(**overrides):
    base = dict(
        verifier="test-verifier",
        model="test/model",
        verdict="supported",
        confidence=0.8,
        url="https://example.com/pricing",
        quote="Official Models cost $0.09 to $0.25 per second",
        reasoning="because",
        prompt_tokens=10,
        completion_tokens=5,
    )
    base.update(overrides)
    return vc.Verdict(**base)


# ---------------------------------------------------------------------------
# normalize_whitespace / quote_appears_in_text
# ---------------------------------------------------------------------------


def test_normalize_whitespace_collapses_runs_and_trims():
    assert vc.normalize_whitespace("  a   b\n\tc  ") == "a b c"


def test_quote_appears_with_reflowed_whitespace():
    quote = "Official Models cost $0.09 to $0.25\nper second"
    page = "blah blah Official Models cost $0.09 to $0.25   per second more text"
    assert vc.quote_appears_in_text(quote, page) is True


def test_quote_does_not_appear_when_fabricated():
    quote = "Video generation is completely free for all users forever"
    page = "Official Models cost $0.09 to $0.25 per second of generated video"
    assert vc.quote_appears_in_text(quote, page) is False


def test_paraphrase_fails_even_though_the_meaning_matches():
    # Same fact, different words: this must NOT pass. Only exact (modulo
    # whitespace) substrings pass, on purpose.
    quote = "The price is nine to twenty-five cents for each second of video"
    page = "Official Models cost $0.09 to $0.25 per second of generated video"
    assert vc.quote_appears_in_text(quote, page) is False


def test_empty_quote_never_appears():
    assert vc.quote_appears_in_text("", "anything at all") is False
    assert vc.quote_appears_in_text("   ", "anything at all") is False


# ---------------------------------------------------------------------------
# apply_citation_gate — the mechanical fabrication check
# ---------------------------------------------------------------------------


def test_gate_passes_a_real_verbatim_quote():
    verdict = make_verdict()
    result = vc.apply_citation_gate(verdict, fetcher=lambda url: REAL_PAGE)
    assert result.verdict == "supported"
    assert result.gate_note == ""


def test_gate_passes_a_real_quote_with_reflowed_whitespace():
    verdict = make_verdict(quote="Official   Models\ncost $0.09 to $0.25 per   second")
    result = vc.apply_citation_gate(verdict, fetcher=lambda url: REAL_PAGE)
    assert result.verdict == "supported"


def test_gate_rejects_a_fabricated_quote():
    verdict = make_verdict(quote="Video generation is free of charge for everyone")
    result = vc.apply_citation_gate(verdict, fetcher=lambda url: REAL_PAGE)
    assert result.verdict == "fabricated_citation"
    assert "does not appear" in result.gate_note


def test_gate_rejects_a_paraphrased_quote():
    verdict = make_verdict(
        quote="The cost ranges from nine cents to twenty five cents a second"
    )
    result = vc.apply_citation_gate(verdict, fetcher=lambda url: REAL_PAGE)
    assert result.verdict == "fabricated_citation"


def test_gate_rejects_when_url_cannot_be_fetched():
    def broken_fetcher(url):
        raise vc.FetchError("404 for " + url)

    verdict = make_verdict()
    result = vc.apply_citation_gate(verdict, fetcher=broken_fetcher)
    assert result.verdict == "fabricated_citation"
    assert "404" in result.gate_note


def test_gate_rejects_supported_verdict_missing_a_citation():
    verdict = make_verdict(url="", quote="")
    result = vc.apply_citation_gate(verdict, fetcher=lambda url: REAL_PAGE)
    assert result.verdict == "fabricated_citation"
    assert "missing" in result.gate_note


def test_gate_passes_through_a_genuine_unresolved_with_no_citation():
    verdict = make_verdict(verdict="unresolved", url="", quote="", confidence=0.0)
    calls = []

    def fetcher(url):
        calls.append(url)
        return REAL_PAGE

    result = vc.apply_citation_gate(verdict, fetcher=fetcher)
    assert result.verdict == "unresolved"
    assert calls == []  # nothing to fetch, so nothing was fetched


def test_gate_does_not_mutate_the_input_verdict():
    verdict = make_verdict(quote="totally made up nonsense quote")
    vc.apply_citation_gate(verdict, fetcher=lambda url: REAL_PAGE)
    assert verdict.verdict == "supported"  # original object untouched


# ---------------------------------------------------------------------------
# parse_verdict — model output parsing
# ---------------------------------------------------------------------------


class _FakeUsage:
    prompt_tokens = 42
    completion_tokens = 7


def test_parse_verdict_extracts_json_from_plain_output():
    cfg = vc.VerifierConfig(name="v", model="m", api_key_env="X")
    raw = (
        '{"verdict": "refuted", "confidence": 0.9, "url": "https://x.test/a", '
        '"quote": "the actual text", "reasoning": "checked it"}'
    )
    verdict = vc.parse_verdict(cfg, raw, _FakeUsage())
    assert verdict.verdict == "refuted"
    assert verdict.confidence == 0.9
    assert verdict.prompt_tokens == 42
    assert verdict.completion_tokens == 7


def test_parse_verdict_strips_markdown_fences():
    cfg = vc.VerifierConfig(name="v", model="m", api_key_env="X")
    raw = '```json\n{"verdict": "supported", "confidence": 1.0, "url": "u", "quote": "q", "reasoning": "r"}\n```'
    verdict = vc.parse_verdict(cfg, raw, _FakeUsage())
    assert verdict.verdict == "supported"


def test_parse_verdict_clamps_out_of_range_confidence():
    cfg = vc.VerifierConfig(name="v", model="m", api_key_env="X")
    raw = '{"verdict": "unresolved", "confidence": 5.0, "url": "", "quote": "", "reasoning": "r"}'
    verdict = vc.parse_verdict(cfg, raw, _FakeUsage())
    assert verdict.confidence == 1.0


def test_parse_verdict_rejects_invalid_verdict_label():
    cfg = vc.VerifierConfig(name="v", model="m", api_key_env="X")
    raw = '{"verdict": "maybe", "confidence": 0.5, "url": "", "quote": "", "reasoning": "r"}'
    with pytest.raises(ValueError):
        vc.parse_verdict(cfg, raw, _FakeUsage())


def test_parse_verdict_raises_on_non_json_garbage():
    cfg = vc.VerifierConfig(name="v", model="m", api_key_env="X")
    with pytest.raises(ValueError):
        vc.parse_verdict(cfg, "the model just chatted instead of answering", _FakeUsage())


# ---------------------------------------------------------------------------
# aggregate_claim
# ---------------------------------------------------------------------------


def test_aggregate_majority_supported():
    claim = {"id": "c1", "text": "x"}
    verdicts = [
        make_verdict(verifier="a", verdict="supported"),
        make_verdict(verifier="b", verdict="supported"),
        make_verdict(verifier="c", verdict="refuted"),
    ]
    result = vc.aggregate_claim(claim, verdicts)
    assert result["final_call"] == "supported"
    assert result["counts"] == {
        "supported": 2,
        "refuted": 1,
        "unresolved": 0,
        "fabricated_citation": 0,
    }
    assert len(result["surviving_citations"]) == 3


def test_aggregate_tie_is_unresolved():
    claim = {"id": "c1", "text": "x"}
    verdicts = [
        make_verdict(verifier="a", verdict="supported"),
        make_verdict(verifier="b", verdict="refuted"),
    ]
    result = vc.aggregate_claim(claim, verdicts)
    assert result["final_call"] == "unresolved"


def test_aggregate_fabricated_citations_are_not_evidence_either_way():
    claim = {"id": "c1", "text": "x"}
    verdicts = [
        make_verdict(verifier="a", verdict="supported"),
        make_verdict(verifier="b", verdict="fabricated_citation"),
        make_verdict(verifier="c", verdict="fabricated_citation"),
    ]
    result = vc.aggregate_claim(claim, verdicts)
    # 1 supported vs 0 refuted still wins, even though 2 of 3 verifiers
    # answered — the fabricated ones are excluded, not counted as refuting.
    assert result["final_call"] == "supported"
    assert result["counts"]["fabricated_citation"] == 2
    # and their citations must not survive into the trusted list
    assert len(result["surviving_citations"]) == 1


def test_aggregate_all_unresolved_stays_unresolved():
    claim = {"id": "c1", "text": "x"}
    verdicts = [make_verdict(verifier="a", verdict="unresolved", url="", quote="")]
    result = vc.aggregate_claim(claim, verdicts)
    assert result["final_call"] == "unresolved"


# ---------------------------------------------------------------------------
# load_claims
# ---------------------------------------------------------------------------


def test_load_claims_from_yaml(tmp_path):
    p = tmp_path / "claims.yaml"
    p.write_text(
        "claims:\n"
        "  - id: a\n"
        "    text: claim a\n"
        "  - id: b\n"
        "    text: claim b\n"
        "    context: some context\n"
    )
    claims = vc.load_claims(p)
    assert [c["id"] for c in claims] == ["a", "b"]
    assert claims[1]["context"] == "some context"


def test_load_claims_from_json(tmp_path):
    p = tmp_path / "claims.json"
    p.write_text('{"claims": [{"id": "a", "text": "claim a"}]}')
    claims = vc.load_claims(p)
    assert claims == [{"id": "a", "text": "claim a"}]


def test_load_claims_rejects_missing_fields(tmp_path):
    p = tmp_path / "claims.yaml"
    p.write_text("claims:\n  - id: a\n")
    with pytest.raises(ValueError):
        vc.load_claims(p)


def test_seed_claims_file_loads_and_has_five_entries():
    claims = vc.load_claims(PLUTO_ROOT / "tools" / "claims" / "disputed_claims.yaml")
    assert len(claims) == 5
    ids = {c["id"] for c in claims}
    assert "darkbloom-provider-earnings" in ids
    assert "replicate-video-pricing" in ids
    assert "h100-hourly-rate" in ids
    assert "salad-scale-claims" in ids
    assert "qualcomm-npu-latency" in ids


# ---------------------------------------------------------------------------
# select_verifiers
# ---------------------------------------------------------------------------


def test_select_verifiers_uses_distinct_providers_first():
    verifiers = vc.select_verifiers(3)
    assert len(verifiers) == 3
    assert len({v.name for v in verifiers}) == 3


def test_select_verifiers_cycles_when_n_exceeds_pool():
    n = len(vc.VERIFIER_POOL) + 2
    verifiers = vc.select_verifiers(n)
    assert len(verifiers) == n
    assert verifiers[0].name == verifiers[len(vc.VERIFIER_POOL)].name


def test_select_verifiers_rejects_non_positive_n():
    with pytest.raises(ValueError):
        vc.select_verifiers(0)


# ---------------------------------------------------------------------------
# run_claim — graceful failure: one bad provider must not kill the run
# ---------------------------------------------------------------------------


def test_run_claim_survives_a_provider_exception(monkeypatch):
    good = vc.VerifierConfig(name="good", model="m1", api_key_env="X1")
    bad = vc.VerifierConfig(name="bad", model="m2", api_key_env="X2")

    async def fake_call_verifier(verifier, claim_text, context, mock=False):
        if verifier.name == "bad":
            raise RuntimeError("HTTP 403, error code: 1010")
        return make_verdict(verifier="good")

    monkeypatch.setattr(vc, "call_verifier", fake_call_verifier)
    monkeypatch.setattr(vc, "apply_citation_gate", lambda v, fetcher=None: v)

    claim = {"id": "c1", "text": "x"}
    verdicts, failures = asyncio.run(vc.run_claim(claim, [good, bad]))

    assert len(verdicts) == 1
    assert verdicts[0].verifier == "good"
    assert len(failures) == 1
    assert failures[0].verifier == "bad"
    assert "403" in failures[0].error


def test_run_claim_all_providers_failing_returns_empty_not_a_crash(monkeypatch):
    bad1 = vc.VerifierConfig(name="bad1", model="m1", api_key_env="X1")
    bad2 = vc.VerifierConfig(name="bad2", model="m2", api_key_env="X2")

    async def always_fails(verifier, claim_text, context, mock=False):
        raise RuntimeError("timeout")

    monkeypatch.setattr(vc, "call_verifier", always_fails)

    claim = {"id": "c1", "text": "x"}
    verdicts, failures = asyncio.run(vc.run_claim(claim, [bad1, bad2]))
    assert verdicts == []
    assert len(failures) == 2


# ---------------------------------------------------------------------------
# cost accounting
# ---------------------------------------------------------------------------


def test_estimate_cost_sums_tokens_and_dollars():
    cfg = vc.VerifierConfig(
        name="v", model="m", api_key_env="X", cost_per_1m=(1.0, 2.0)
    )
    verdicts = [
        make_verdict(verifier="v", prompt_tokens=1_000_000, completion_tokens=500_000),
        make_verdict(verifier="v", prompt_tokens=1_000_000, completion_tokens=500_000),
    ]
    cost = vc.estimate_cost({"v": cfg}, verdicts)
    assert cost["total_prompt_tokens"] == 2_000_000
    assert cost["total_completion_tokens"] == 1_000_000
    # 2 * (1M * $1/1M + 0.5M * $2/1M) = 2 * (1.0 + 1.0) = 4.0
    assert cost["estimated_cost_usd"] == 4.0
    assert cost["cost_is_complete_estimate"] is True


def test_estimate_cost_flags_incomplete_pricing():
    cfg = vc.VerifierConfig(name="v", model="m", api_key_env="X", cost_per_1m=None)
    verdicts = [make_verdict(verifier="v")]
    cost = vc.estimate_cost({"v": cfg}, verdicts)
    assert cost["cost_is_complete_estimate"] is False


# ---------------------------------------------------------------------------
# mock mode end-to-end (no network, no spend) — proves the pipeline wires up
# ---------------------------------------------------------------------------


def test_mock_mode_runs_end_to_end_with_no_network():
    claims = [{"id": "c1", "text": "some claim"}]
    report = asyncio.run(vc.run_all(claims, n=2, mock=True))
    assert report["claims"][0]["id"] == "c1"
    assert report["claims"][0]["final_call"] == "unresolved"
    assert report["provider_failures"] == []
    assert report["cost"]["estimated_cost_usd"] == 0.0


# --- routing: proxy vs direct -------------------------------------------------

def test_proxy_pool_spreads_across_different_upstreams():
    """Routing every verifier through one proxy is pointless if they all land on
    the same upstream — a shared outage or bias would correlate every verdict."""
    from tools.verify_claims import PROXY_POOL

    models = [v.model for v in PROXY_POOL]
    assert len(models) == len(set(models)), "duplicate model in the proxy pool"
    assert all(v.api_base and v.api_base.endswith("/v1") for v in PROXY_POOL)
    assert all(v.api_key_env == "LITELLM_MASTER_KEY" for v in PROXY_POOL)


def test_go_routes_sort_last_because_of_the_weekly_quota():
    """opencode go bills weekly, so a go- route can be listed and still refuse.
    With the default n it must never be reached before a non-quota provider."""
    from tools.verify_claims import PROXY_POOL, select_verifiers

    go = [i for i, v in enumerate(PROXY_POOL) if "go-" in v.model]
    assert go, "expected at least one go- route in the pool"
    assert min(go) >= 3, "a quota-limited route sorted into the default n=3"
    assert not any("go-" in v.model for v in select_verifiers(3, via="proxy"))


def test_via_selects_the_pool_explicitly():
    from tools.verify_claims import PROXY_POOL, VERIFIER_POOL, select_verifiers

    assert select_verifiers(2, via="proxy") == PROXY_POOL[:2]
    assert select_verifiers(2, via="direct") == VERIFIER_POOL[:2]
    with pytest.raises(ValueError, match="via must be"):
        select_verifiers(2, via="carrier-pigeon")
    # "auto" is not a pool — it must be resolved before selection.
    with pytest.raises(ValueError, match="via must be"):
        select_verifiers(2, via="auto")


def test_a_running_proxy_answers_401_and_that_counts_as_up():
    """401 is health, not failure. Reading it as failure costs an hour."""
    import urllib.error

    from tools import verify_claims as vc

    def four_oh_one(url, timeout=None):
        raise urllib.error.HTTPError(url, 401, "Unauthorized", {}, None)

    def refused(url, timeout=None):
        raise ConnectionRefusedError()

    import urllib.request
    orig = urllib.request.urlopen
    try:
        urllib.request.urlopen = four_oh_one
        assert vc.proxy_is_up() is True
        urllib.request.urlopen = refused
        assert vc.proxy_is_up() is False
    finally:
        urllib.request.urlopen = orig


def test_free_pool_is_free_and_spread_across_upstreams():
    """A run on this pool must cost nothing, and must not put every verifier on
    one upstream — five free models from one lab correlate their mistakes."""
    from tools.verify_claims import FREE_POOL, select_verifiers

    assert all(v.cost_per_1m == (0.0, 0.0) for v in FREE_POOL)
    assert all(v.api_key_env == "OPENROUTER_API_KEY" for v in FREE_POOL)
    models = [v.model for v in FREE_POOL]
    assert len(models) == len(set(models))
    labs = {m.split("/")[1] for m in models}
    assert len(labs) >= 4, f"free pool leans on too few upstreams: {labs}"
    assert select_verifiers(3, via="free") == FREE_POOL[:3]


def test_a_stealth_model_is_never_the_only_route():
    """Stealth models are pre-releases under an alias — they change or vanish
    without notice, so a run must not depend on one."""
    from tools.verify_claims import FREE_POOL

    stealth = [v for v in FREE_POOL if "stealth/" in v.model]
    assert stealth, "expected a stealth route in the free pool"
    assert len(FREE_POOL) - len(stealth) >= 3, "too few non-stealth fallbacks"
