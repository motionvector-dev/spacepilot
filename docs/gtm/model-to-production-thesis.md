# Model to production — the thesis, checked against the repo

---
status: draft
authority: proposal (not normative; VISION.md still governs)
written_at: 2026-10-02
source: Saurabh's session summary, 2026-10-02, plus the users-and-positioning scan the same day
---

**One line:** autonomous model-to-production infrastructure.
**Kept:** *You decide what to run. SpacePilot decides how and where.*
**Added underneath:** *From model to production.*

This file records the thesis, puts it next to the earlier GTM recommendation,
and says plainly which parts the repo already has and which it does not. It
does not replace `docs/design/VISION.md`; whether it should is the open
decision at the end.

## The thesis

A user gives SpacePilot a model, a workload, latency and throughput targets,
reliability needs, and a budget. SpacePilot picks the place (owned GPU, rented
box, cloud, API), the runtime (vLLM, SGLang, TensorRT-LLM, llama.cpp, MLX),
the quantization and serving config (batching, KV cache, parallelism,
speculative decoding), then deploys, measures, and keeps improving it.

```
MODEL + WORKLOAD + CONSTRAINTS
  → REGISTRY   models / runtimes / GPUs / clouds / quantizations
  → PLANNER    viable strategies
  → HARNESS    provision → deploy → benchmark → profile
  → OPTIMIZER  runtime / GPU / quant / batching / KV / topology / cost
  → PRODUCTION
  → OPERATOR   observe → diagnose → recover → migrate
  → EVIDENCE   benchmarks / receipts / failures / recipes ──↺ REGISTRY
```

Why a small team can try: vLLM, SGLang, Kubernetes, SkyPilot and Hugging Face
are primitives underneath, not things to rebuild. SpacePilot operates them.

The market reads this as many separate jobs (inference engineer, GPU
performance, SRE, capacity planning, forward-deployed engineer). The bet is
that much of that work becomes software run by agents, with SpacePilot as
their registry, tools, harness, evidence and feedback loop.

**What SpacePilot is not:** another inference cloud, GPU provider, model
server, Kubernetes layer, or multi-cloud orchestrator. SkyPilot owns *where
compute runs*; BentoML/Modular own *serving*; Fireworks, Together, Baseten and
Modal own *optimized hosted inference*. SpacePilot's claim is the search: "I
tested the viable options; this config meets your SLO cheapest; here is the
evidence."

## Business model: open core plus inference engineering as a service

| open source | commercial |
| --- | --- |
| registry, provider and runtime adapters, benchmark harness, deployment primitives, optimization loops, receipts, recipes, agent tools | a team hands over model + workload + SLO + budget; SpacePilot plus forward-deployed engineers own deployment, optimization and reliability |

Autonomy ramps: human → human + agent → agent + human approval → mostly
autonomous. Each engagement should leave behind a recipe, a trace, or a tool,
so the next one needs less human work.

## How it sits next to the earlier recommendation

The same-day positioning scan recommended **"the local lane for your coding
agent"**: developers on 36–128 GB Macs, a savings ledger, a
`where_should_this_run(task)` MCP tool. The two are the same engine aimed at
different buyers:

| | local lane (earlier) | model to production (this) |
| --- | --- | --- |
| buyer | individual developer | startup that needs someone to own inference |
| hardware | their Mac | cloud and owned GPUs |
| runtimes | MLX, llama.cpp | vLLM, SGLang, TensorRT-LLM |
| money | free, maybe $5/month | services first, then software |
| proof | "412 calls ran locally, ~$X saved" | "this config meets p95 < 300 ms at $Y per million tokens; reproduce it" |
| shared core | registry, fit verdict, measured-not-quoted numbers, receipts, MCP tools | same |

They don't conflict at the core. They conflict on **what gets built next**,
because the runtimes, hardware and buyers barely overlap.

## What the repo has, and what it doesn't

Checked on main at `9bc8a2d`.

| thesis layer | exists today | evidence |
| --- | --- | --- |
| Registry | yes, with provenance rules: pinned revisions, dated and cited claims | `spacepilot/registry/`, loaders in `spacepilot/silicon.py` |
| Runtimes in the registry | 15, all local: MLX, llama.cpp, whisper.cpp, mflux, diffusers and others. **No vLLM, SGLang or TensorRT-LLM** | `spacepilot/registry/runtimes/` |
| Harness, benchmark | a seed: overnight sweeps walk a knob grid and record ok/failed per cell, image models only | `spacepilot/sweep.py`, `spacepilot/registry/sweeps/` |
| Measurements | 3 systems, all laptops/Macs, **no datacenter GPU** | `spacepilot/registry/measurements/` |
| Planner / optimizer | no. The scheduler is a comment | `docs/BUILD-PLAN.md`, "one-paragraph state" |
| Provision / deploy | one AWS spot launch path; docks and providers are zero code | `docs/BUILD-PLAN.md`, Phases 2 and 4 |
| Operator (observe, recover, migrate) | read-only daemon and signed fleet listing only | `docs/BUILD-PLAN.md`, "what is genuinely good" |
| Receipts | the measurement record format, yes | `spacepilot/measurements.py` |
| Agent tools | FastMCP server | `spacepilot/mcp_server.py` |

**Hardware ceiling, today.** The AWS boundary allows one g6e.2xlarge
(one L40S, 48 GB) at once, because the G-family spot quota is 8 vCPU
(`AGENTS.md`, "Money and hardware"). An H100 on AWS is a different instance
family the quota record doesn't cover. So the wedge's "H100 × L40S" comparison
needs either a quota request or a rented H100 elsewhere (RunPod, Lambda,
Modal). The L40S half is reachable now, at about $0.75/hour, and never to "just
check something."

## The wedge: one end-to-end workflow

```
Model:      a Qwen open-weight model
Traffic:    50 concurrent users
Constraint: p95 < 300 ms
Objective:  lowest cost
Search:     vLLM × SGLang, L40S (then H100), quantizations, batch size,
            KV-cache settings, parallelism, provider
Output:     chosen config, benchmark table, $/M tokens, TTFT, p95/p99,
            throughput, deploy command, reproducible receipt
```

The test is not breadth: **would an inference engineer trust and reproduce
SpacePilot's decision?**

Smallest honest path from the repo as it is:

1. Add vLLM and SGLang to `spacepilot/registry/runtimes/`, with the same
   provenance rules as the rest.
2. Generalize `sweep.py` from image knobs to serving knobs, with a load
   generator that reports TTFT, inter-token latency and p95/p99 at a set
   concurrency.
3. Run the grid on one L40S. Write each cell through `measurements.py`,
   including failures (OOM is a real boundary, not a missing row).
4. Publish the receipt: config, hardware, versions, raw numbers, cost per
   million tokens, and the command to reproduce it.
5. Only then add a second GPU type, and a planner that prunes the grid.

## Go to market

Target startups saying *"we need someone to own inference"*, where one engineer
carries deployment, benchmarking, cost, latency, quantization, scaling and
incidents.

Lead with evidence, not outreach: reproduce a workload similar to theirs,
then send "we saw you're hiring for inference; here are the configs we
evaluated on a similar workload, with benchmarks and a reproducible receipt;
give us one real workload and we'll see how much of the loop SpacePilot
automates." Address companies through their public job posts, not lists of
named people.

## Next step: turn job descriptions into evals

Take about 20 live inference job descriptions (SkyPilot, BentoML/Modular,
Modal, Baseten, Fireworks, Together, RunPod, OpenRouter, Perplexity, General
Compute, Cartesia and others). Turn every recurring responsibility into a
capability SpacePilot can be tested on:

| job requirement | SpacePilot eval | today |
| --- | --- | --- |
| Benchmark vLLM/SGLang | can it run both and compare? | no runtime entry |
| Tune batching | can it search batch size? | sweep grid can, for image knobs |
| Reduce TTFT | can it optimize TTFT under a set load? | no load generator |
| Select GPUs | can it compare GPU types? | one GPU type reachable |
| Capacity planning | can it estimate the fleet needed? | no |
| Diagnose OOM | can it identify and fix it? | sweeps record OOM as a boundary, no fix |
| Autoscale serving | can it configure scaling? | no |
| Investigate regressions | can it detect and bisect? | no |
| Optimize cost/token | can it minimize cost under the SLO? | no planner |

That table is the roadmap, the benchmark, and the customer proof at once.

## Open decision

Logged in `docs/DECISION-INBOX.md`: which buyer leads, the developer's local
lane or the team that needs inference owned. Until it's decided,
`docs/design/VISION.md` and the README stay as they are, and the website
change ("From model to production" under the tagline) waits too.
