#!/usr/bin/env python3
"""Fan a disputed claim out to N independent cheap-model verifiers and grade
the answers mechanically instead of trusting them.

The one rule that matters: a verdict is worthless without a citation the
script can check for itself. Every verifier is asked for a URL and a
verbatim quoted span. The script then fetches that URL and checks, by exact
string match (whitespace-normalised only), that the span is actually on the
page. A verdict that fails this check is never counted as evidence for or
against a claim — it is reported separately as ``fabricated_citation``. This
gate exists because cheap models fabricate plausible-looking citations, and
a human skimming a JSON blob will not catch that; only fetching the page and
matching the string will.

Verifiers are prompted to refute a claim, not confirm it — "not supported"
is the default when the evidence is thin.

    python tools/verify_claims.py --claims tools/claims/disputed_claims.yaml
    python tools/verify_claims.py --claims path.yaml --n 3 --out report.json
    python tools/verify_claims.py --claims path.yaml --mock   # no network, no spend

Requires network access and provider API keys (see docs/INFERENCE.md) for a
real run. Run behind `doppler run --` so the keys are in the environment;
the script never prints a secret value.
"""

from __future__ import annotations

import argparse
import asyncio
import dataclasses
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

VERDICT_VALUES = {"supported", "refuted", "unresolved", "fabricated_citation"}

# A browser-like User-Agent. Groq and Cerebras 403 plain Python HTTP clients
# behind Cloudflare's bot signature check even with a valid key — see
# docs/INFERENCE.md "Gotcha: Cloudflare blocks Python clients". curl and a
# browser UA both pass; this reproduces the UA path instead of shelling out.
BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)


@dataclasses.dataclass(frozen=True)
class VerifierConfig:
    """One model endpoint a claim can be fanned out to.

    `model` is a litellm model string. `cost_per_1m` is (input, output) USD
    per million tokens, for indicative cost reporting only — treat as an
    estimate, not a billing-accurate figure; pull real rates from the
    provider before trusting a total near a budget decision.
    """

    name: str
    model: str
    api_key_env: str
    api_base: str | None = None
    extra_headers: dict[str, str] | None = None
    cost_per_1m: tuple[float, float] | None = None


# Ordered by how cheap/fast each provider is. Different providers, not just
# different models, so a single provider outage or bias does not correlate
# every verifier's answer for a claim.
VERIFIER_POOL: list[VerifierConfig] = [
    VerifierConfig(
        # llama-3.3-70b-versatile from docs/INFERENCE.md's "notable model
        # IDs" list is no longer served (confirmed via a live /v1/models
        # call 2026-08-23: gone from the catalogue). gpt-oss-120b is.
        name="groq-gptoss",
        model="groq/openai/gpt-oss-120b",
        api_key_env="GROQ_API_KEY",
        extra_headers={"User-Agent": BROWSER_UA},
        cost_per_1m=(0.15, 0.75),
    ),
    VerifierConfig(
        name="cerebras-gptoss",
        model="cerebras/gpt-oss-120b",
        api_key_env="CEREBRAS_API_KEY",
        extra_headers={"User-Agent": BROWSER_UA},
        cost_per_1m=(0.25, 0.69),
    ),
    VerifierConfig(
        name="gemini-flash",
        model="gemini/gemini-3.5-flash",
        api_key_env="GEMINI_PRIMARY_API_KEY",
        cost_per_1m=(0.075, 0.30),
    ),
    VerifierConfig(
        name="glm-air",
        model="openai/glm-4.5-air",
        api_key_env="GLM_API_KEY",
        api_base="https://open.bigmodel.cn/api/paas/v4",
        cost_per_1m=(0.20, 0.20),
    ),
    VerifierConfig(
        name="nvidia-nemotron",
        model="openai/nvidia/nemotron-3-ultra-550b-a55b",
        api_key_env="NVIDIA_API_KEY",
        api_base="https://integrate.api.nvidia.com/v1",
        cost_per_1m=(0.0, 0.0),
    ),
    VerifierConfig(
        name="openrouter-free",
        model="openrouter/nvidia/nemotron-3-ultra-550b-a55b:free",
        api_key_env="OPENROUTER_API_KEY",
        cost_per_1m=(0.0, 0.0),
    ),
]

REFUTE_SYSTEM_PROMPT = """You are a skeptical fact-checker. Your job is to try to
REFUTE the claim you are given, not to confirm it. Do not accept a claim just
because it sounds plausible or because you recall something like it. If you
cannot find solid, checkable evidence either way, say "unresolved" — that is
the correct default under uncertainty, not a failure.

You must answer with EXACTLY ONE JSON object, and nothing else before or
after it (no markdown fences, no commentary). The object must have these
keys:

{
  "verdict": "supported" | "refuted" | "unresolved",
  "confidence": <float 0.0-1.0>,
  "url": "<the single URL your verdict rests on, or empty string if unresolved>",
  "quote": "<a VERBATIM span copied exactly from that URL's page text that backs your verdict, or empty string if unresolved>",
  "reasoning": "<1-3 sentences>"
}

Rules:
- If verdict is "supported" or "refuted", url and quote are REQUIRED and
  quote MUST be copied verbatim from the page at that URL — not paraphrased,
  not summarized, not reconstructed from memory. A quote you cannot swear is
  character-for-character on that page should not be submitted; use
  "unresolved" instead.
- Prefer primary sources (the org's own pricing/docs/blog page) over
  secondary aggregators when they disagree.
- Keep the quote short: one sentence or a short fragment is enough to prove
  the point. Do not quote whole paragraphs.
"""


def build_user_prompt(claim_text: str, context: str | None) -> str:
    parts = [f"CLAIM TO CHECK:\n{claim_text.strip()}"]
    if context:
        parts.append(f"CONTEXT:\n{context.strip()}")
    parts.append(
        "Try to refute this claim. Return only the JSON object described in "
        "the system prompt."
    )
    return "\n\n".join(parts)


def normalize_whitespace(text: str) -> str:
    """Collapse all whitespace runs to single spaces and strip the ends.

    Models reflow line breaks and spacing when they "quote" a page, so the
    citation gate normalises whitespace before comparing. It does nothing
    else — no case-folding, no punctuation stripping, no fuzzy matching. A
    paraphrase must still fail this check.
    """
    return re.sub(r"\s+", " ", text).strip()


def quote_appears_in_text(quote: str, page_text: str) -> bool:
    if not quote or not quote.strip():
        return False
    return normalize_whitespace(quote) in normalize_whitespace(page_text)


class FetchError(Exception):
    pass


def fetch_url(url: str, timeout: float = 20.0) -> str:
    """Fetch a URL and return its page text for the citation gate.

    Deliberately dumb: no JS rendering, no readability extraction beyond
    stripping tags. The gate only needs to know whether the quoted span is
    present in what the server actually sent; a script tag or nav chrome
    surrounding it does not matter.
    """
    req = urllib.request.Request(url, headers={"User-Agent": BROWSER_UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        raise FetchError(f"could not fetch {url}: {exc}") from exc
    charset = "utf-8"
    try:
        charset = resp.headers.get_content_charset() or "utf-8"
    except Exception:
        pass
    html = raw.decode(charset, errors="replace")
    text = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", html)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = _unescape_html_entities(text)
    return text


def _unescape_html_entities(text: str) -> str:
    import html as _html

    return _html.unescape(text)


@dataclasses.dataclass
class Verdict:
    verifier: str
    model: str
    verdict: str
    confidence: float
    url: str
    quote: str
    reasoning: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    gate_note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


def _extract_json_object(raw: str) -> dict[str, Any]:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-zA-Z]*\n?", "", raw)
        raw = re.sub(r"```$", "", raw).strip()
    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError("no JSON object found in model output")
    return json.loads(raw[start : end + 1])


def parse_verdict(verifier: VerifierConfig, raw_content: str, usage: Any) -> Verdict:
    obj = _extract_json_object(raw_content)
    verdict = str(obj.get("verdict", "")).strip().lower()
    if verdict not in {"supported", "refuted", "unresolved"}:
        raise ValueError(f"model returned an invalid verdict: {verdict!r}")
    try:
        confidence = float(obj.get("confidence", 0.0))
    except (TypeError, ValueError):
        confidence = 0.0
    confidence = max(0.0, min(1.0, confidence))
    prompt_tokens = getattr(usage, "prompt_tokens", 0) or 0
    completion_tokens = getattr(usage, "completion_tokens", 0) or 0
    return Verdict(
        verifier=verifier.name,
        model=verifier.model,
        verdict=verdict,
        confidence=confidence,
        url=str(obj.get("url", "") or ""),
        quote=str(obj.get("quote", "") or ""),
        reasoning=str(obj.get("reasoning", "") or ""),
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
    )


def apply_citation_gate(verdict: Verdict, fetcher=fetch_url) -> Verdict:
    """Mechanically check a verdict's citation. Mutates nothing; returns the
    (possibly downgraded) verdict to keep this a pure, testable function.

    A verdict of "unresolved" with no citation passes through untouched —
    there is nothing to check. A verdict of "supported"/"refuted" MUST carry
    a checkable citation; missing one, an unfetchable URL, or a quote that
    is not actually on the page all downgrade it to "fabricated_citation".
    """
    if verdict.verdict == "unresolved" and not verdict.url and not verdict.quote:
        return verdict

    if not verdict.url.strip() or not verdict.quote.strip():
        return dataclasses.replace(
            verdict,
            verdict="fabricated_citation",
            gate_note="missing url or quote for a supported/refuted verdict",
        )

    try:
        page_text = fetcher(verdict.url)
    except FetchError as exc:
        return dataclasses.replace(
            verdict, verdict="fabricated_citation", gate_note=str(exc)
        )

    if quote_appears_in_text(verdict.quote, page_text):
        return verdict

    return dataclasses.replace(
        verdict,
        verdict="fabricated_citation",
        gate_note="quote does not appear (verbatim, whitespace-normalised) on the fetched page",
    )


async def call_verifier(
    verifier: VerifierConfig, claim_text: str, context: str | None, mock: bool = False
) -> Verdict:
    if mock:
        return Verdict(
            verifier=verifier.name,
            model=verifier.model,
            verdict="unresolved",
            confidence=0.0,
            url="",
            quote="",
            reasoning="mock mode: no call made",
        )

    import litellm

    api_key = os.environ.get(verifier.api_key_env)
    if not api_key:
        raise RuntimeError(f"{verifier.api_key_env} not set in environment")

    kwargs: dict[str, Any] = dict(
        model=verifier.model,
        api_key=api_key,
        messages=[
            {"role": "system", "content": REFUTE_SYSTEM_PROMPT},
            {"role": "user", "content": build_user_prompt(claim_text, context)},
        ],
        timeout=60,
        temperature=0.0,
    )
    if verifier.api_base:
        kwargs["api_base"] = verifier.api_base
    if verifier.extra_headers:
        kwargs["extra_headers"] = verifier.extra_headers

    response = await litellm.acompletion(**kwargs)
    content = response.choices[0].message.content or ""
    usage = getattr(response, "usage", None)
    return parse_verdict(verifier, content, usage)


@dataclasses.dataclass
class ProviderFailure:
    verifier: str
    model: str
    error: str


async def run_claim(
    claim: dict[str, Any],
    verifiers: list[VerifierConfig],
    mock: bool = False,
) -> tuple[list[Verdict], list[ProviderFailure]]:
    async def _one(v: VerifierConfig):
        try:
            verdict = await call_verifier(v, claim["text"], claim.get("context"), mock=mock)
            return apply_citation_gate(verdict), None
        except Exception as exc:  # noqa: BLE001 - a bad provider must not kill the run
            return None, ProviderFailure(verifier=v.name, model=v.model, error=str(exc))

    results = await asyncio.gather(*[_one(v) for v in verifiers])
    verdicts = [v for v, f in results if v is not None]
    failures = [f for v, f in results if f is not None]
    return verdicts, failures


def aggregate_claim(claim: dict[str, Any], verdicts: list[Verdict]) -> dict[str, Any]:
    supported = [v for v in verdicts if v.verdict == "supported"]
    refuted = [v for v in verdicts if v.verdict == "refuted"]
    unresolved = [v for v in verdicts if v.verdict == "unresolved"]
    fabricated = [v for v in verdicts if v.verdict == "fabricated_citation"]

    if len(supported) > len(refuted):
        final_call = "supported"
    elif len(refuted) > len(supported):
        final_call = "refuted"
    else:
        final_call = "unresolved"

    surviving_citations = [
        {"verifier": v.verifier, "url": v.url, "quote": v.quote}
        for v in supported + refuted
    ]

    return {
        "id": claim["id"],
        "text": claim["text"],
        "final_call": final_call,
        "counts": {
            "supported": len(supported),
            "refuted": len(refuted),
            "unresolved": len(unresolved),
            "fabricated_citation": len(fabricated),
        },
        "surviving_citations": surviving_citations,
        "verdicts": [v.to_dict() for v in verdicts],
    }


def estimate_cost(verifiers_by_name: dict[str, VerifierConfig], verdicts: list[Verdict]) -> dict[str, Any]:
    total_prompt = sum(v.prompt_tokens for v in verdicts)
    total_completion = sum(v.completion_tokens for v in verdicts)
    total_cost = 0.0
    priced = True
    by_verifier: dict[str, dict[str, Any]] = {}
    for v in verdicts:
        cfg = verifiers_by_name.get(v.verifier)
        entry = by_verifier.setdefault(
            v.verifier,
            {"model": v.model, "prompt_tokens": 0, "completion_tokens": 0, "cost_usd": 0.0},
        )
        entry["prompt_tokens"] += v.prompt_tokens
        entry["completion_tokens"] += v.completion_tokens
        if cfg and cfg.cost_per_1m:
            in_rate, out_rate = cfg.cost_per_1m
            call_cost = (v.prompt_tokens / 1_000_000) * in_rate + (
                v.completion_tokens / 1_000_000
            ) * out_rate
            entry["cost_usd"] += call_cost
            total_cost += call_cost
        else:
            priced = False
    return {
        "total_prompt_tokens": total_prompt,
        "total_completion_tokens": total_completion,
        "estimated_cost_usd": round(total_cost, 6),
        "cost_is_complete_estimate": priced,
        "by_verifier": by_verifier,
    }


def load_claims(path: Path) -> list[dict[str, Any]]:
    text = path.read_text()
    if path.suffix.lower() in {".yaml", ".yml"}:
        import yaml

        data = yaml.safe_load(text)
    else:
        data = json.loads(text)
    claims = data["claims"] if isinstance(data, dict) else data
    for c in claims:
        if "id" not in c or "text" not in c:
            raise ValueError(f"claim missing required 'id'/'text': {c!r}")
    return claims


def select_verifiers(n: int) -> list[VerifierConfig]:
    if n <= 0:
        raise ValueError("n must be positive")
    pool = VERIFIER_POOL
    if n <= len(pool):
        return pool[:n]
    # More verifiers than distinct providers: cycle, still using every
    # provider before repeating any of them.
    return [pool[i % len(pool)] for i in range(n)]


async def run_all(
    claims: list[dict[str, Any]], n: int, mock: bool = False
) -> dict[str, Any]:
    verifiers = select_verifiers(n)
    verifiers_by_name = {v.name: v for v in verifiers}
    started = time.time()

    results = []
    all_failures: list[ProviderFailure] = []
    all_verdicts: list[Verdict] = []
    for claim in claims:
        verdicts, failures = await run_claim(claim, verifiers, mock=mock)
        all_verdicts.extend(verdicts)
        all_failures.extend(failures)
        results.append(aggregate_claim(claim, verdicts))

    return {
        "claims": results,
        "provider_failures": [dataclasses.asdict(f) for f in all_failures],
        "cost": estimate_cost(verifiers_by_name, all_verdicts),
        "elapsed_seconds": round(time.time() - started, 2),
        "verifiers_used": [v.name for v in verifiers],
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--claims", type=Path, default=ROOT / "tools" / "claims" / "disputed_claims.yaml")
    ap.add_argument("--n", type=int, default=3, help="independent verifiers per claim")
    ap.add_argument("--out", type=Path, default=None, help="write the JSON report here")
    ap.add_argument("--mock", action="store_true", help="no network calls; verify plumbing only")
    args = ap.parse_args(argv)

    claims = load_claims(args.claims)
    report = asyncio.run(run_all(claims, args.n, mock=args.mock))

    out_text = json.dumps(report, indent=2)
    if args.out:
        args.out.write_text(out_text + "\n")
        print(f"wrote {args.out}", file=sys.stderr)
    else:
        print(out_text)

    for failure in report["provider_failures"]:
        print(f"[provider failure] {failure['verifier']} ({failure['model']}): {failure['error']}", file=sys.stderr)

    for claim in report["claims"]:
        print(
            f"{claim['id']}: {claim['final_call']} "
            f"(supported={claim['counts']['supported']} refuted={claim['counts']['refuted']} "
            f"unresolved={claim['counts']['unresolved']} fabricated={claim['counts']['fabricated_citation']})",
            file=sys.stderr,
        )

    print(
        f"cost: ~${report['cost']['estimated_cost_usd']} "
        f"({report['cost']['total_prompt_tokens']} prompt / "
        f"{report['cost']['total_completion_tokens']} completion tokens)"
        + ("" if report["cost"]["cost_is_complete_estimate"] else " [partial: some models unpriced]"),
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
