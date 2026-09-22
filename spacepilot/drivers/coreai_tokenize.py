"""Render a Qwen chat prompt to raw token ids. No model weights."""

from __future__ import annotations

import argparse
import json
import sys

from transformers import AutoTokenizer


def render(tokenizer_dir: str, messages: list, *, thinking: bool) -> dict:
    tok = AutoTokenizer.from_pretrained(tokenizer_dir)
    text = tok.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True,
        enable_thinking=thinking,
    )
    ids = tok.apply_chat_template(
        messages, tokenize=True, add_generation_prompt=True,
        enable_thinking=thinking,
    )
    if not isinstance(ids, list):
        ids = ids["input_ids"]
    if ids and isinstance(ids[0], (list, tuple)):
        ids = ids[0]
    return {"rendered": text, "tokens": [int(i) for i in ids]}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tokenizer", required=True)
    parser.add_argument("--thinking", choices=("off", "on"), default="off")
    args = parser.parse_args(argv)
    payload = json.loads(sys.stdin.read() or "{}")
    messages = payload.get("messages")
    if not messages:
        prompt = payload.get("prompt", "")
        messages = [{"role": "user", "content": prompt}]
    out = render(args.tokenizer, messages, thinking=args.thinking == "on")
    json.dump(out, sys.stdout)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
