# What the hardware is doing to the scheduler

Four forces in AI hardware change what a scheduler must know. This explains
them. It holds almost no numbers on purpose: the parts live in
`spacepilot/registry/silicon/`, where every figure carries its source and the
date it was read, and a loader refuses one that does not.

**If a new part ships tomorrow, this document should not need editing.** Add a
file to the registry instead. Only a change in *understanding* belongs here.

## 1. Memory is the binding constraint, not compute

Every vendor is shipping more compute on schedule. None can get enough memory.
The registry records four symptoms across two vendors: a desktop line whose top
configuration cannot be upgraded at all, a machine whose price rose 18% mid-life
with memory named as the reason, a laptop-class desktop that cannot be kept in
stock, and a roadmap part designed for sixteen times today's capacity whose
shipping is explicitly contingent on the memory market.

One cause sits behind all four. HBM4 entered mass production in 2026, and
datacenter demand for it is bidding memory away from everything else.

**What follows:** plan any fleet of owned machines assuming capacity is harder
to buy next year, not easier.

## 2. Capacity and throughput are different questions

Memory size tells you whether weights *load*. Memory bandwidth tells you whether
the result is *usable*. They rank machines differently, and the gap is not small.

On one 128 GB box, a dense 70B model generates 4–6 tokens per second while a
120B mixture-of-experts model reaches 31–55 — because a mixture-of-experts model
reads only a fraction of itself per token. Same memory, same box, an order of
magnitude apart.

Two machines in the registry make the same point from the other direction: a
mid-range desktop and a purpose-built AI box move memory at an identical rate
and differ by roughly three times in price.

**What follows:** a `fits` verdict computed from capacity alone is not an answer.
It needs a companion number, and today `usable_memory_bytes` is one integer.

## 3. "How much memory" has stopped having one answer

Memory used to be a number. It is now an arrangement:

```
  discrete       its own VRAM, separate from system RAM
  unified        CPU and GPU share all of it
  partitionable  shared, but a slice is assignable as VRAM
  coherent       shared across heterogeneous cores
  near-memory    compute sited next to the memory array
```

A part with 128 GB *partitionable* memory has two correct capacity answers
depending on configuration. A new flash tier sitting between HBM and SSD adds a
third speed band to machines that previously had two.

**What follows:** the fit check needs to know which arrangement it is looking at.
`memory_model` is a required concept, not a detail.

## 4. Every machine has an accelerator nothing can name

The Copilot+ badge requires 40 TOPS or more, so every current client machine
ships a neural processing unit. Apple, AMD, Intel and Qualcomm all have one.

No common backend vocabulary can express it. CUDA, Metal, ROCm and Vulkan all
describe GPUs. A scheduler that cannot name an NPU cannot route to one — and it
is the accelerator most likely to be sitting idle.

The same gap has a cheaper version. A machine with a working Vulkan compute path
and no ROCm installed is reported by most probes as having no usable
accelerator, because their backend list has three entries and Vulkan is not one
of them. That machine will run models. The probe says it cannot.

**What follows:** a backend is not one value per machine. It is a set of paths
per device, and the set is larger than any probe currently knows. The registry's
`compute_paths` vocabulary is deliberately wider than the probe's for this
reason — it names paths we cannot yet route to, so the gap is visible.

## 5. Orchestration is now worth its own silicon

A major vendor now ships a CPU designed specifically for the work *around*
inference: tool calls, code execution, data processing and coordination between
model calls. It is marketed on agentic throughput against x86, not on FLOPS.

That is an outside party arriving at the same conclusion this project is built
on — that deciding what runs where is real work, distinct from running it.

## How to read the registry

```
spacepilot silicon            # the table: kind, availability, memory, bandwidth, source
spacepilot silicon <id>       # one part, every claim with its date and its link
spacepilot silicon --json     # the same, for anything that has to consume it
```

In the table a `*` marks a figure a publication reported rather than one the
vendor published, and `not published` marks a figure nobody published at all.
Neither is ever shown as a blank cell or a zero.

`spacepilot/registry/silicon/` holds one file per part. Every figure carries a
source, an ISO date and an https link. Two source kinds exist and neither is
`measured`:

- `declared` — the vendor published it
- `reported` — a named publication claimed it; the vendor has not confirmed

A measurement never appears here. Measurements belong in the corpus, beside the
machine that produced them, because a number somebody ran and a number somebody
announced are not the same kind of fact and must never be averaged together.

Silence is recorded too. Some vendors publish no bandwidth figure for a part;
those fields are empty and the note says so, rather than being filled from
third-party numbers that are probably right.
