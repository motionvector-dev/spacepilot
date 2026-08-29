#!/usr/bin/env python3
import time
from mlx_lm import load, generate

print("[*] Loading Qwen2.5-32B into Unified Memory...")
t0 = time.time()
m, tok = load("mlx-community/Qwen2.5-32B-Instruct-4bit")
print(f"[✓] Loaded in {time.time() - t0:.2f}s.\n")

prompt = "Explain how Apple Silicon Unified Memory Architecture handles high-bandwidth GPU tensor transfers in 3 concise bullet points."
print(f"Prompt: {prompt}\n")

t_gen_start = time.perf_counter()
output = generate(m, tok, prompt=prompt, max_tokens=120, verbose=False)
t_gen = time.perf_counter() - t_gen_start

print("=" * 70)
print(output.strip())
print("=" * 70)
print(f"Decode Speed: {120 / t_gen:.1f} tok/s | Total Generation Time: {t_gen:.2f}s")
