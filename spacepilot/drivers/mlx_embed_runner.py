"""Small isolated MLX embedding worker used by :mod:`mlx_embed_driver`.

Same shape as :mod:`mlx_lm_runner`: the parent resolves a pinned local snapshot
and forces offline mode, and this process owns the large allocation so macOS
gets the memory back when it exits.

Qwen3-Embedding is a Qwen3 causal model with no LM head in play. `mlx_lm.load`
returns it, `model.model(tokens)` returns the final normed hidden states, and
the embedding is the last token's state, L2 normalised — which is the pooling
Qwen3-Embedding was trained with. No separate embeddings package is involved.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path


RESULT_PREFIX = "SPACEPILOT_RESULT "


def _read_request() -> list[str]:
    raw = sys.stdin.read()
    payload = json.loads(raw) if raw.strip() else {}
    inputs = payload.get("inputs")
    if not isinstance(inputs, list) or not inputs:
        raise ValueError("request needs a non-empty 'inputs' list")
    for item in inputs:
        if not isinstance(item, str) or not item.strip():
            raise ValueError("every input must be a non-empty string")
    return inputs


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--max-tokens", required=True, type=int)
    args = parser.parse_args(argv)

    inputs = _read_request()

    import mlx.core as mx
    from mlx_lm import load

    started = time.perf_counter()
    load_started = time.perf_counter()
    model, tokenizer = load(args.model)
    load_seconds = time.perf_counter() - load_started

    vectors = []
    tokens_in = 0
    for text in inputs:
        ids = tokenizer.encode(text)[: args.max_tokens]
        # Last-token pooling only means anything if the last token is the one
        # the model was trained to pool on.
        if not ids or ids[-1] != tokenizer.eos_token_id:
            ids = ids + [tokenizer.eos_token_id]
        tokens_in += len(ids)
        hidden = model.model(mx.array([ids]))
        vector = hidden[0, -1, :]
        norm = mx.linalg.norm(vector)
        vector = vector / norm
        mx.eval(vector)
        vectors.append([float(x) for x in vector.tolist()])

    dimensions = len(vectors[0])
    if any(len(v) != dimensions for v in vectors):
        raise RuntimeError("the model returned vectors of differing width")

    Path(args.output).write_text(json.dumps(
        {"dimensions": dimensions, "vectors": vectors}, separators=(",", ":")))
    wall_seconds = time.perf_counter() - started
    payload = {
        "status": "completed",
        "wall_seconds": wall_seconds,
        "load_seconds": load_seconds,
        "tokens_in": tokens_in,
        "dimensions": dimensions,
        "count": len(vectors),
        "peak_memory_gb": mx.get_peak_memory() / (1024 ** 3),
    }
    print(RESULT_PREFIX + json.dumps(payload, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
