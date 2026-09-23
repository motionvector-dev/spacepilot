"""Render a Qwen chat prompt to raw token ids. No model weights.

transformers is a gpu-worker optional dep, so it is imported lazily inside
render(): the module has to import cleanly on a bare wheel install
(test_wheel_install walks every shipped module). Every from_pretrained call
carries an explicit revision — the repo-wide pinning gate
(test_model_revisions) and bandit B615 both reject unpinned downloads.
"""

from __future__ import annotations

import argparse
import json
import sys

# The only checkpoint this tokenizer has been checked against. The Core AI
# export and every gate in docs/design/coreai-qwen35-9b-port.md ran at this
# revision; do not move it without rerunning those gates.
QWEN35_9B_TOKENIZER_REVISION = "c202236235762e1c871ad0ccb60c8ee5ba337b9a"


def render(
    tokenizer_dir: str,
    messages: list,
    *,
    thinking: bool,
    revision: str = QWEN35_9B_TOKENIZER_REVISION,
) -> dict:
    from transformers import AutoTokenizer

    tok = AutoTokenizer.from_pretrained(tokenizer_dir, revision=revision)
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
    parser.add_argument("--revision", default=QWEN35_9B_TOKENIZER_REVISION)
    args = parser.parse_args(argv)
    payload = json.loads(sys.stdin.read() or "{}")
    messages = payload.get("messages")
    if not messages:
        prompt = payload.get("prompt", "")
        messages = [{"role": "user", "content": prompt}]
    out = render(
        args.tokenizer, messages,
        thinking=args.thinking == "on", revision=args.revision,
    )
    json.dump(out, sys.stdout)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
