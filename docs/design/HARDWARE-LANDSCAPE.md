# AI hardware landscape — August 2026

A scheduler that decides *where* a model runs must know what hardware exists,
not only what it has probed. This records the state of AI silicon and memory,
and what each change means for that decision.

Every figure here is **declared**: a vendor or a named report published it on a
stated date. Nothing here is measured. The two must never be confused.

## Datacenter silicon

| Vendor | Now | Next |
|---|---|---|
| NVIDIA | Rubin — production early 2026, partner systems H2 | Rubin Ultra Q2 2027, then Feynman |
| AMD | MI350 | MI400/MI450 in 2026. HBM4 **432 GB**, **19.6 TB/s** (from 288 GB, 8 TB/s). MI500 in 2027 |
| Intel | Gaudi 3 | Crescent Island — **160 GB LPDDR5X**, inference-optimised. Sampling H2 2026 |
| Huawei | Ascend 950PR Q1 2026 — 128 GB in-house memory, 1.6 TB/s | 950DT Q4 2026; 960 in 2027; 970 in 2028, each doubling |

Intel chose LPDDR5X over HBM on purpose: cheaper capacity, lower bandwidth. Two
accelerators with similar capacity can differ tenfold in how fast they feed the
chip.

## Memory

| | |
|---|---|
| **HBM4** | Mass production from early 2026. Interface doubles to 2048-bit; over 2.8 TB/s |
| **16-high HBM4E** | Requested for Q4 2026 |
| **HBF** — High Bandwidth Flash | A **new tier between HBM and SSD**. Standard published August 2026. Up to **512 GB at 0.4–3 TB/s**. Samples H2 2026; devices early 2027 |

HBF is the structural change. Machine memory stops being one number and becomes
a set of tiers with very different speeds.

### Memory is the binding constraint, not compute

Four independent signals, two vendors:

| Signal | Source |
|---|---|
| Mac Studio tops out at 96 GB; the M3 Ultra cannot be configured for memory at all | Apple spec page |
| DGX Spark $2,999 → $3,999 → **$4,699**, attributed to memory supply | NVIDIA |
| Mac mini out of stock, deliveries taking weeks to months | Bloomberg, 25 Aug 2026 |
| M7 Ultra **designed for 1.5 TB**, but shipping it "will depend on the state of the industry" | Bloomberg, Jul 2026 |

HBM4 demand is bidding memory away from everything else. Plan any fleet of owned
machines on the assumption that capacity is harder to buy in 2027, not easier.

## Local AI boxes

A machine you own that runs models without renting anything. The category is now
real: Apple cannot keep the Mac mini in stock because it became *"a popular tool
for running artificial intelligence applications locally."*

| Box | Memory | Bandwidth | Compute | Power |
|---|---|---|---|---|
| Mac Studio, M3 Ultra | 96 GB, **not configurable** | **819 GB/s** | — | — |
| Mac Studio, M4 Max | 36 → 64 GB | 410 → 546 GB/s | — | — |
| Mac mini, M4 Pro | 24 → 48 GB | **273 GB/s** | 16-core Neural Engine | — |
| NVIDIA DGX Spark | 128 GB LPDDR5x | **273 GB/s** | 1 PFLOP FP4 sparse; Arm + Blackwell | 140 W chip |
| AMD Ryzen AI Max+ 395 | 32–128 GB, **96 GB assignable as VRAM** | not published | 50+ TOPS NPU, 40 CU RDNA 3.5 | 55 W |
| Xiaomi AI Cube | 160 GB | 1.22 TB/s | 200 TOPS NPU | 150 W |

A mid-range Mac mini and a $4,699 DGX Spark move memory at the **same
273 GB/s**. They differ in capacity and compute, not in feeding rate.

**Capacity is not throughput.** On one 128 GB box: a dense 70B model generates
4–6 tokens/s, while a 120B mixture-of-experts model reaches 31–55 — because a
mixture-of-experts model reads only part of itself per token. Ranking on
capacity alone gets this backwards.

**Three memory models, not one:**

```
  fully unified      Apple          CPU and GPU share all of it
  partitionable      Ryzen AI Max   128 GB total, up to 96 GB assignable as VRAM
  coherent unified   DGX Spark      128 GB shared across Arm and Blackwell
```

"How much memory does this machine have" has a different answer per box.

## Client machines

Every current laptop line ships a neural processing unit. Microsoft's Copilot+
badge requires **40 TOPS or more**, so the floor is now universal:

| Part | NPU |
|---|---|
| AMD Ryzen AI 300 | 50 TOPS |
| Intel Core Ultra 200V | 48 TOPS |
| Qualcomm Snapdragon X Elite | 45 TOPS |
| Apple M5 | 38 TOPS Neural Engine |

Every major OEM ships these — over thirty Copilot+ models were shown at one
trade show in 2026.

## What this changes

**1. NPUs are universal and unnamed.** Every 2026 client machine has one, and no
common backend vocabulary can express it. CUDA, Metal, ROCm and Vulkan all
describe GPUs. A scheduler that cannot name an NPU cannot route to one — and it
is the accelerator most likely to be idle.

**2. Memory needs two numbers, not one.** Capacity says whether weights *load*.
Bandwidth says whether the result is *usable*. With HBF and partitionable
unified memory, a single "usable bytes" integer cannot express a real machine.

**3. Scarcity strengthens warm residency.** If capacity is expensive and its
ceiling is set by supply rather than engineering, evicting a loaded model to make
room costs more. A machine that *already holds* a model is worth more than one
that could. Warm residency stops being a latency optimisation and becomes an
inventory argument.

## Provenance

Apple, NVIDIA and AMD figures come from their own specification pages and
product blogs. AMD does not publish a memory-bandwidth number for the Ryzen
AI Max+ 395; widely-quoted figures near 256 GB/s are third-party. Xiaomi's box
is an engineering prototype with chips due in 2027. Roadmap items attributed to
Bloomberg are reported plans, not vendor announcements, and Apple has declined
to comment on them.

**Not established:** the chip in the next Mac mini. Reporting says Apple tested
both M5 and M6 generations and a launch is days away.
