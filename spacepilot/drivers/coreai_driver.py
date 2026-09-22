"""One-shot Core AI text via the patched-or-upstream llm-runner binary.

The runner receives raw token ids. Qwen3.5's own `--prompt` path applies
the chat template and turns thinking on when the flag is omitted, so this
driver renders `enable_thinking` itself and never passes `--prompt`.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Dict, Optional

from spacepilot.drivers.mlx_lm_driver import MlxLmSubprocessError

_PROMPT = re.compile(
    r"Prompt:\s+([\d.]+)ms,\s+(\d+)\s+tokens,\s+([\d.]+)\s+tokens/sec")
_GEN = re.compile(
    r"Generation:\s+([\d.]+)ms,\s+(\d+)\s+tokens,\s+([\d.]+)\s+tokens/sec")
_LOAD = re.compile(r"done in ([\d.]+)s")
_TOTAL = re.compile(r"Total:\s+([\d.]+)s")


def _config() -> dict:
    try:
        from spacepilot.cli import load_config
        return load_config()
    except Exception:
        return {}


class CoreAIDriver:
    """Same infer/stream/route_status shape as the MLX driver."""

    runtime_id = "coreai"

    def __init__(
        self,
        *,
        runner_bin: Optional[str] = None,
        bundle_dir: Optional[str] = None,
        python_bin: Optional[str] = None,
        variant_id: str = "qwen3.5-9b-coreai-int8hu",
    ) -> None:
        cfg = _config()
        self.runner_bin = (
            runner_bin
            or os.environ.get("SPACEPILOT_LLM_RUNNER")
            or cfg.get("llm_runner_bin")
            or ""
        )
        self.bundle_dir = (
            bundle_dir
            or os.environ.get("SPACEPILOT_COREAI_BUNDLE")
            or cfg.get("coreai_bundle")
            or ""
        )
        self.python_bin = python_bin or os.environ.get("SPACEPILOT_PYTHON") or cfg.get("python_bin") or "python3"
        self.variant_id = variant_id

    def route_status(self, variant_id: Optional[str] = None) -> tuple[bool, str]:
        runner = Path(self.runner_bin)
        bundle = Path(self.bundle_dir)
        if not runner.is_file() or not os.access(runner, os.X_OK):
            return False, "no route — llm-runner binary is not set or not executable"
        if not (bundle / "metadata.json").is_file():
            return False, "no route — Core AI bundle metadata.json is missing"
        aimodels = list(bundle.glob("*.aimodel"))
        if not aimodels:
            return False, "no route — Core AI bundle has no .aimodel"
        return True, f"ready — {bundle.name} via llm-runner"

    def _tokenize(self, prompt: str, messages: Optional[list], thinking: bool) -> dict:
        tokenizer = str(Path(self.bundle_dir) / "tokenizer")
        cmd = [
            self.python_bin, "-m", "spacepilot.drivers.coreai_tokenize",
            "--tokenizer", tokenizer,
            "--thinking", "on" if thinking else "off",
        ]
        body = json.dumps({
            "prompt": prompt,
            "messages": messages,
        })
        proc = subprocess.run(cmd, input=body, capture_output=True, text=True)
        if proc.returncode != 0:
            tail = (proc.stderr or proc.stdout or "")[-2000:]
            raise MlxLmSubprocessError(f"tokenizer exited {proc.returncode}: {tail}")
        try:
            return json.loads(proc.stdout)
        except json.JSONDecodeError as exc:
            raise MlxLmSubprocessError("tokenizer returned malformed json") from exc

    def _command(self, token_file: str, max_tokens: int, temperature: float) -> list[str]:
        cmd = [
            self.runner_bin,
            "--model", self.bundle_dir,
            "--raw-tokens", token_file,
            "--apply-chat-template", "false",
            "--max-tokens", str(max_tokens),
            "--inference-engine-variant", "coreai-pipelined",
            "--chunk-threshold", "1",
            "--warmup", "off",
        ]
        if temperature == 0:
            cmd.extend(["--sampling-strategy", "greedy"])
        else:
            cmd.extend(["--sampling-strategy", "temperature", "--temperature", str(temperature)])
        return cmd

    @staticmethod
    def _parse(stdout: str, peak_memory_gb: float, load_seconds: float) -> Dict[str, Any]:
        prompt = _PROMPT.search(stdout)
        gen = _GEN.search(stdout)
        total = _TOTAL.search(stdout)
        if not prompt or not gen or not total:
            raise MlxLmSubprocessError("llm-runner completed without a performance summary")
        answer_at = stdout.find("Generating...")
        summary_at = stdout.find("Performance Summary")
        if answer_at < 0 or summary_at < 0 or summary_at <= answer_at:
            raise MlxLmSubprocessError("llm-runner completed without an answer")
        text = stdout[answer_at + len("Generating..."):summary_at].strip()
        load = _LOAD.search(stdout)
        if load:
            load_seconds = float(load.group(1))
        return {
            "status": "completed",
            "text": text,
            "wall_seconds": float(total.group(1)),
            "load_seconds": load_seconds if load_seconds > 0 else 0.001,
            "generation_tps": float(gen.group(3)),
            "prompt_tps": float(prompt.group(3)),
            "prompt_tokens": int(prompt.group(2)),
            "generation_tokens": int(gen.group(2)),
            "peak_memory_gb": peak_memory_gb if peak_memory_gb > 0 else 0.001,
            "runtime_id": "coreai",
        }

    def _run(self, cmd: list[str], env: dict) -> tuple[subprocess.CompletedProcess, float]:
        peak = {"rss": 0}

        def watch(pid: int) -> None:
            while True:
                try:
                    raw = subprocess.check_output(
                        ["ps", "-o", "rss=", "-p", str(pid)], text=True,
                    ).strip()
                except subprocess.CalledProcessError:
                    return
                if not raw:
                    return
                peak["rss"] = max(peak["rss"], int(raw.split()[0]))
                time.sleep(0.2)

        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env,
        )
        thread = threading.Thread(target=watch, args=(proc.pid,), daemon=True)
        thread.start()
        out, err = proc.communicate()
        thread.join(timeout=1)
        done = subprocess.CompletedProcess(cmd, proc.returncode or 0, out, err)
        return done, peak["rss"] / (1024 * 1024)

    def infer(
        self,
        prompt: str,
        out_path: str,
        max_tokens: int,
        max_kv_size: int,
        temperature: float,
        variant_id: Optional[str] = None,
        timeout: Optional[float] = None,
        messages: Optional[list] = None,
        thinking: bool = False,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        del variant_id, max_kv_size, timeout, kwargs
        rendered = self._tokenize(prompt, messages, thinking)
        if not thinking and "<think>" in rendered["rendered"]:
            closed = rendered["rendered"].rsplit("<think>", 1)[-1]
            if "</think>" not in closed:
                raise MlxLmSubprocessError(
                    "chat template left an unclosed think block with thinking off")
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as handle:
            json.dump({"tokens": rendered["tokens"]}, handle)
            token_file = handle.name
        env = os.environ.copy()
        env["COREAI_CHUNK_THRESHOLD"] = "1"
        cmd = self._command(token_file, max_tokens, temperature)
        try:
            proc, peak_gb = self._run(cmd, env)
        finally:
            Path(token_file).unlink(missing_ok=True)
        if proc.returncode != 0:
            tail = (proc.stderr or proc.stdout or "")[-3000:]
            raise MlxLmSubprocessError(f"llm-runner exited {proc.returncode}: {tail}")
        result = self._parse(proc.stdout or "", peak_gb, load_seconds=0.001)
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        Path(out_path).write_text(result["text"])
        result["rendered_prompt"] = rendered["rendered"]
        result["command"] = cmd
        return result

    def stream(self, prompt: str, out_path: str, max_tokens: int, max_kv_size: int,
               temperature: float, variant_id: Optional[str] = None,
               messages: Optional[list] = None, thinking: bool = False, **kwargs: Any):
        result = self.infer(
            prompt, out_path, max_tokens, max_kv_size, temperature,
            variant_id=variant_id, messages=messages, thinking=thinking, **kwargs,
        )
        # llm-runner prints the answer in one piece. One chunk, after the run.
        yield {"type": "chunk", "text": result["text"]}
        yield {"type": "result", "result": result}
