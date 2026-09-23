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
CHUNK_PREFIX = "SPACEPILOT_CHUNK "


def apply_chat(tokenizer, messages, *, thinking: bool) -> str:
    """Render the chat template. Thinking is off unless the caller asks.

    Templates that take ``enable_thinking`` (Qwen, MiMo, Gemma) honor it.
    A template that rejects the argument is rendered without it. LFM2.5 is
    one of those: the weights still open ``<think>`` on their own.
    """
    plain = dict(tokenize=False, add_generation_prompt=True)
    try:
        return tokenizer.apply_chat_template(
            messages, enable_thinking=thinking, **plain)
    except TypeError:
        return tokenizer.apply_chat_template(messages, **plain)
    except Exception as exc:
        if "enable_thinking" not in str(exc):
            raise
        return tokenizer.apply_chat_template(messages, **plain)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--max-tokens", required=True, type=int)
    parser.add_argument("--max-kv-size", required=True, type=int)
    parser.add_argument("--temperature", required=True, type=float)
    parser.add_argument("--thinking", choices=("off", "on"), default="off")
    parser.add_argument("--stream", action="store_true")
    parser.add_argument("--messages", action="store_true")
    args = parser.parse_args(argv)

    raw = sys.stdin.read()
    if not raw.strip():
        raise ValueError("prompt on stdin cannot be empty")
    # A chat request arrives as a real message list so the chat template sees
    # the roles. Flattening it to one user turn would silently discard the
    # system prompt, which is the part a coding agent depends on most.
    messages = None
    if args.messages:
        messages = json.loads(raw)["messages"]
        if not messages:
            raise ValueError("messages cannot be empty")
        prompt = messages[-1].get("content", "")
    else:
        prompt = raw

    from mlx_lm import load, stream_generate
    from mlx_lm.sample_utils import make_sampler

    started = time.perf_counter()
    load_started = time.perf_counter()
    model, tokenizer = load(args.model)
    load_seconds = time.perf_counter() - load_started

    if tokenizer.has_chat_template:
        prompt = apply_chat(
            tokenizer, messages or [{"role": "user", "content": prompt}],
            thinking=args.thinking == "on",
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
        if args.stream and response.text:
            # Flushed per token: the parent forwards these as SSE, and a
            # buffered pipe would turn real streaming into one late burst.
            print(CHUNK_PREFIX + json.dumps({"text": response.text},
                                            separators=(",", ":")), flush=True)

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
