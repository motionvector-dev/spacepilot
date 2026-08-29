#!/usr/bin/env python3
"""
benchmark_muse30b.py
--------------------
Benchmarks bartowski/Muse-Glimmer-30B-GGUF (Released: August 10, 2026)
on Apple Silicon Metal GPU.
"""

import time
import sys

try:
    from llama_cpp import Llama
except ImportError:
    print("Error: llama-cpp-python is not installed yet.")
    sys.exit(1)

MODEL_PATH = "/private/tmp/muse_glimmer/Muse-Glimmer-30B-Q4_K_M.gguf"

def main():
    print("=" * 70)
    print("LOADING MUSE-GLIMMER-30B (GGUF Q4_K_M) INTO M1 MAX METAL GPU")
    print("=" * 70)
    
    t0 = time.time()
    llm = Llama(
        model_path=MODEL_PATH,
        n_gpu_layers=-1,      # 100% Metal GPU offloading
        n_ctx=4096,           # 4k context window
        n_batch=512,          # Prompt processing batch size
        verbose=False
    )
    print(f"[✓] Model loaded into Metal Unified Memory in {time.time() - t0:.2f}s.\n")

    prompt = "<|start|>user<|message|>Explain how Apple Silicon Unified Memory Architecture enables high-throughput tensor processing with zero PCIe bottleneck in 3 clear bullet points.<|eot|><|start|>assistant<|message|>"
    print(f"Prompt: Explain Apple Silicon Unified Memory Architecture...\n")

    t_start = time.perf_counter()
    response = llm(
        prompt,
        max_tokens=120,
        temperature=0.7,
        stop=["<|eot|>", "<|end_of_text|>"]
    )
    t_gen = time.perf_counter() - t_start

    output_text = response["choices"][0]["text"].strip()
    completion_tokens = response["usage"]["completion_tokens"]
    speed = completion_tokens / max(1e-5, t_gen)

    print("=" * 70)
    print(output_text)
    print("=" * 70)
    print(f"\n[✓] Generated {completion_tokens} tokens in {t_gen:.2f}s ({speed:.1f} tok/s) on Apple Silicon Metal!")

if __name__ == "__main__":
    main()
