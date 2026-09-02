# Technical Specification: Core AI Provider Backend & Heterogeneous Runtime Engine

> **Status, 2026-09-03: concept sketch, unverified.** The `coreaid` daemon, the
> socket, the hot-swap and speculative-decoding figures below do not exist in
> apple/coreai-models or anywhere checked. What that repo actually provides:
> `.aimodel` exports for Qwen3, Phi, Mistral, Gemma and others via
> `uv run coreai.llm.export`, and a Swift runtime, `CoreAILanguageModel`, used
> through `FoundationModels.LanguageModelSession`. Current authority is
> `INFERENCE-SURFACE.md`; the CoreAI rung lands Swift-side in SpaceBar first.


- **Document ID**: `SP-DESIGN-044`
- **Target Path**: `docs/design/macos-coreai-provider-backend-runtime.md`
- **Status**: `PROPOSED / IMPLEMENTATION-READY`
- **Author**: Saurabh Nandwana (SpacePilot Architect)
- **Reference**: Apple Core AI Developer Toolchain (`coreai-torch`, `coreai-opt`, `coreai-build`, `coreai-models`)

---

## 1. Executive Summary

SpacePilot treats hardware compute as a pluggable execution substrate. While **`cuda`** (NVIDIA TensorRT/vLLM) and **`rocm`** (AMD HIP) power hyperscale data centers, and **`mlx`** provides dynamic eager evaluation for multi-node diffusion/research, **`coreai`** serves as the **Apple Silicon on-device production serving engine**.

This specification defines the architecture, CLI ergonomics, compilation pipeline, Unix domain socket IPC, and multi-LoRA hot-swapping mechanics for the **`coreai`** execution provider in SpacePilot.

```
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│                           SPACEPILOT COMPUTE PROVIDER TAXONOMY                                  │
├───────────────┬─────────────────────────┬──────────────────────┬────────────────────────────────┤
│ PROVIDER ID   │ TARGET HARDWARE         │ ENGINE BACKEND       │ PRIMARY WORKLOAD               │
├───────────────┼─────────────────────────┼──────────────────────┼────────────────────────────────┤
│ `cuda`        │ NVIDIA (H100 / RTX 4090)│ TensorRT-LLM / vLLM  │ Large 70B+ FP8 batch serving   │
│ `rocm`        │ AMD (MI300X / Radeon)   │ ROCm PyTorch / vLLM  │ High-VRAM cloud cluster scale  │
│ `mlx`         │ Apple Silicon (Metal)   │ MLX Lazy Dynamic     │ FLUX, Wan 2.1 Video, TB5 Mesh  │
│ `coreml`      │ Apple Silicon (ANE/GPU) │ Static MIL Bytecode  │ Classical Vision/Audio (YOLO)  │
│ `coreai`      │ **Apple Silicon (Hetero)│ **.aimodelc Runtime**│ **LLMs, <10ms LoRA, 2-5W ANE** │
└───────────────┴─────────────────────────┴──────────────────────┴────────────────────────────────┘
```

---

## 2. Core AI Provider Architecture

The `coreai` provider dynamically partitions foundation model workloads across Apple Silicon's heterogeneous compute blocks without memory copying:

```
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│                             COREAI PROVIDER INTERNAL ARCHITECTURE                               │
├─────────────────────────────────────────────────────────────────────────────────────────────────┤
│                                  SpacePilot Dispatcher / API                                    │
│                                               │                                                 │
│                        Unix Domain Socket (`/tmp/spacepilot-coreai.sock`)                       │
│                                               │                                                 │
│ ┌─────────────────────────────────────────────▼───────────────────────────────────────────────┐ │
│ │                                  CoreAI Native Daemon (`coreaid`)                           │ │
│ │                                                                                             │ │
│ │  ┌─────────────────────────┐  ┌─────────────────────────┐  ┌─────────────────────────────┐  │ │
│ │  │ Paged KV Cache Manager  │  │ Dynamic LoRA Hot-Swap   │  │ Speculative Decoding Engine │  │ │
│ │  │ (Non-contiguous blocks) │  │ (<10ms delta weights)   │  │ (1B Draft on ANE -> 30B GPU)│  │ │
│ │  └────────────┬────────────┘  └────────────┬────────────┘  └──────────────┬──────────────┘  │ │
│ └───────────────┼────────────────────────────┼──────────────────────────────┼─────────────────┘ │
│                 │                            │                              │                   │
│ ┌───────────────▼────────────────────────────▼──────────────────────────────▼─────────────────┐ │
│ │                             Apple Silicon Zero-Copy Unified Memory (UMA)                     │ │
│ │                                                                                             │ │
│ │    ┌──────────────────────────────┐                ┌───────────────────────────────────┐    │ │
│ │    │ 32-Core Metal GPU            │                │ 16-Core Apple Neural Engine (NPU) │    │ │
│ │    │ • Prompt Prefill (>180 tok/s)│ ◄────────────► │ • Token Decode (~2–5W low power)  │    │ │
│ │    │ • FlashAttention-Metal       │                │ • Systolic Matrix Operations      │    │ │
│ │    └──────────────────────────────┘                └───────────────────────────────────┘    │ │
│ └─────────────────────────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. CLI Ergonomics & User Commands

SpacePilot users interact with the `coreai` backend through standard lifecycle verbs:

### 3.1 `spacepilot ship` (Export & Ahead-Of-Time Compile)
Compiles PyTorch weights into target-specialized `.aimodelc` assets:

```bash
# Export and compile a foundation model for local Apple Silicon execution
spacepilot ship \
  --model "meta-llama/Llama-3.1-8B-Instruct" \
  --provider coreai \
  --quantize int4_palettized \
  --target apple-m1-max \
  --output ./models/llama8b.aimodelc
```

### 3.2 `spacepilot dock` (Mount Runtime Daemon)
Docks the model into memory with background Neural Engine execution:

```bash
# Docks the Core AI daemon and exposes local OpenAI-compatible REST + UDS endpoints
spacepilot dock \
  --provider coreai \
  --model ./models/llama8b.aimodelc \
  --draft-model ./models/llama1b-draft.aimodelc \
  --port 8088 \
  --paged-kv
```

### 3.3 `spacepilot run` (Dispatched Inference)
Dispatches generation requests with dynamic LoRA adapter routing:

```bash
# Runs generation with instant LoRA adapter activation
spacepilot run \
  --provider coreai \
  --prompt "Generate motion design vector manifest" \
  --lora "saas-ui-motion" \
  --max-tokens 512 \
  --temperature 0.2
```

---

## 4. Recipe & Manifest Schema (`spacepilot.yaml`)

SpacePilot execution manifests natively define the `coreai` execution runtime:

```yaml
schema_version: "2026.1"
name: "motionvector-ondevice-pipeline"

model:
  name: "Qwen/Qwen2.5-14B-Instruct"
  source: "huggingface"
  quantization: "int4_palettized"
  format: "aimodelc"

runtime:
  provider: "coreai" # Target Execution Provider
  compute_units: "all" # .all (ANE + GPU + CPU) | .cpuAndNeuralEngine
  speculative_decoding:
    enabled: true
    draft_model: "Qwen/Qwen2.5-1.5B-Instruct.aimodelc"
    speculation_depth: 5

  memory:
    paged_kv_cache: true
    max_context_length: 8192
    vram_budget_gb: 18.0

  hot_swap_loras:
    - id: "saas-ui"
      path: "./loras/saas_ui.lora"
    - id: "fintech-charts"
      path: "./loras/fintech_charts.lora"
    - id: "3d-motion"
      path: "./loras/3d_motion.lora"
```

---

## 5. Model Packaging & Compilation Pipeline

The `coreai` backend translates PyTorch weights into optimized `.aimodelc` assets through a 4-stage pipeline:

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│ 1. PyTorch   │ ──► │ 2. ATen      │ ──► │ 3. Core AI   │ ──► │ 4. AOT       │
│ torch.export │     │ Decompose    │     │ coreai-torch │     │ coreai-build │
└──────────────┘     └──────────────┘     └──────────────┘     └──────────────┘
 (Graph Capture)      (Decomp Table)       (.aimodel Bundle)    (.aimodelc Bin)
```

```python
# Internal SpacePilot CoreAI Compiler Plugin (spacepilot/compiler/coreai.py)
import torch
from coreai_torch import TorchConverter, get_decomp_table
from coreai_opt import palettize_weights, PalettizationConfig

def compile_model_for_coreai(model_path: str, target_chip: str, output_path: str):
    """Captures, quantizes, and packages PyTorch weights into .aimodelc."""
    
    # 1. Load & Trace Model
    model = load_huggingface_model(model_path).eval()
    sample_input = (torch.zeros(1, 16, dtype=torch.long),)
    exported = torch.export.export(model, args=sample_input)
    
    # 2. Decompose ATen operators
    decomposed = exported.run_decompositions(get_decomp_table())
    
    # 3. Apply 4-bit Palettization for Apple Silicon Memory Bandwidth
    opt_config = PalettizationConfig(nbits=4, group_size=128)
    optimized_ir = palettize_weights(decomposed, opt_config)
    
    # 4. Convert to .aimodel bundle
    program = TorchConverter().add_exported_program(optimized_ir).to_coreai()
    program.save(output_path)
    return output_path
```

---

## 6. Multi-LoRA Hot-Swapping Architecture

SpacePilot maintains a single frozen base model resident in Unified Memory while hot-swapping LoRA adapters ($\Delta W = A \times B$) in **$<10\text{ ms}$**:

```
┌────────────────────────────────────────────────────────────────────────┐
│               SHARED UNIFIED MEMORY POOL (UMA)                         │
├────────────────────────────────────────────────────────────────────────┤
│  [ Frozen Base Model: 4-Bit Palettized Qwen 14B (~8.2 GB VRAM) ]       │
├───────────────────────────────────┬────────────────────────────────────┤
│ Active LoRA Buffer (ANE/GPU)      │ Adapter Cache (SSD / Standby RAM)  │
│ ┌───────────────────────────────┐ │ ┌────────────────────────────────┐ │
│ │ Active: "saas-ui" (18 MB)     │ │ │ Inactive: "fintech" (18 MB)    │ │
│ └───────────────────────────────┘ │ │ Inactive: "3d-motion" (18 MB)  │ │
│   ▲ Switch Latency: <10ms         │ └────────────────────────────────┘ │
└───┴───────────────────────────────┴────────────────────────────────────┘
```

---

## 7. Implementation Roadmap & Milestones

1. **Milestone 1 (`SP-COREAI-01`)**: Provider Plugin Interface (`spacepilot/providers/coreai/`).
2. **Milestone 2 (`SP-COREAI-02`)**: Packaging Engine (`spacepilot ship --provider coreai` wrapping `coreai-torch` and `coreai-build`).
3. **Milestone 3 (`SP-COREAI-03`)**: Native Swift Execution Daemon (`coreaid`) with Unix Domain Socket streaming.
4. **Milestone 4 (`SP-COREAI-04`)**: Dynamic Multi-LoRA Hot-Swapper & Paged KV Cache validation on M1/M3/M4 Max chips.

---

## 8. Verification & Performance Acceptance Criteria

- **Prefill Latency:** $>160\text{ tok/s}$ prompt ingestion for 8B models on 32-core Metal GPU.
- **Decoding Power Draw:** $\le 5\text{ Watts}$ sustained package power during ANE token decoding.
- **LoRA Swap Time:** $<10\text{ ms}$ between consecutive requests targeting distinct adapter IDs.
- **IPC Overhead:** $<1.5\text{ ms}$ round-trip latency over `/tmp/spacepilot-coreai.sock`.
