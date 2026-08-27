"""Small isolated MLX-LM worker used by :mod:`mlx_lm_driver`.

The parent resolves a pinned local snapshot and forces offline mode. This
process owns the large allocation, so completion or failure returns memory to
macOS when the process exits instead of leaving a long-lived model server.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path


RESULT_PREFIX = "SPACEPILOT_RESULT "


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--max-tokens", required=True, type=int)
    parser.add_argument("--max-kv-size", required=True, type=int)
    parser.add_argument("--temperature", required=True, type=float)
    args = parser.parse_args(argv)

    prompt = sys.stdin.read()
    if not prompt.strip():
        raise ValueError("prompt on stdin cannot be empty")

    from mlx_lm import load, stream_generate
    from mlx_lm.sample_utils import make_sampler

    started = time.perf_counter()
    load_started = time.perf_counter()
    model, tokenizer = load(args.model)
    load_seconds = time.perf_counter() - load_started

    if tokenizer.has_chat_template:
        prompt = tokenizer.apply_chat_template(
            [{"role": "user", "content": prompt}], tokenize=False,
            add_generation_prompt=True,
        )

    text_parts = []
    last = None
    for response in stream_generate(
        model, tokenizer, prompt,
        max_tokens=args.max_tokens,
        max_kv_size=args.max_kv_size,
        sampler=make_sampler(temp=args.temperature),
    ):
        text_parts.append(response.text)
        last = response

    text = "".join(text_parts)
    if not text.strip() or last is None:
        raise RuntimeError("MLX-LM produced no text")
    Path(args.output).write_text(text)
    payload = {
        "status": "completed",
        "wall_seconds": time.perf_counter() - started,
        "load_seconds": load_seconds,
        "prompt_tokens": last.prompt_tokens,
        "prompt_tps": last.prompt_tps,
        "generation_tokens": last.generation_tokens,
        "generation_tps": last.generation_tps,
        "peak_memory_gb": last.peak_memory,
    }
    print(RESULT_PREFIX + json.dumps(payload, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
