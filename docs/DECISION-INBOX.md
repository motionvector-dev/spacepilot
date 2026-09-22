# SpacePilot decision inbox

---
status: accepted
authority: normative-process
decided_at: 2026-09-02
last_verified_at: 2026-09-02
owners: [cto, founder]
---

One unresolved decision gets one entry. Agents add evidence to the entry instead
of independently asking the same question again.

The prior version of this file was archived on 2026-08-24 (commit 20bf158) for
a docs rewrite; see `AGENTS.md`'s "Read these before asking" for where it
lives now. This file restarts empty except for the entry below.

## Open

### AgentWorth loop: SpacePilot is the inference layer AgentWorth calls; AgentWorth is a trajectory producer for the registry

- **Decided 2026-09-02.** One platform, two products, each runnable alone.
  SpacePilot owns the fleet — nodes, open-weight models, placement,
  endpoints, the registry. AgentWorth grades trajectories from any agent,
  any harness, any machine, and never grows a fleet mode of its own.
- **Three named calls, nothing else.** AgentWorth may call SpacePilot's
  local inference for exactly three uses: Archie's question router
  (`--route`), entity resolution for the beliefs spec (`--resolve-entities`),
  and `asks --summarize` (`--summarize`). Each sits behind its own flag;
  there is no default path that reaches SpacePilot.
- **The flag-and-cost rule.** AgentWorth never sends a prompt to a model on
  its own. Every one of the three calls above only fires behind its named
  flag, and prints the estimated cost before it runs.
- **What crosses back.** Graded trajectories, handoffs, receipts, ATIF
  export, and outcome rates flow from AgentWorth to SpacePilot's registry —
  redacted by default, one export command at a time, no background sync.
- **Full contract**: AgentWorth's `docs/specs/spacepilot-loop.md`
  (`unfoundbox-crew/agentworth`, PR #103). This entry is SpacePilot's record
  of the same agreement; neither file replaces the other.
- **Close when**: the contract's two open questions — one binary or two, and
  how the call surface is versioned — are answered.

### Cache the Metal memory limit on disk, or keep naming the guess?

- **Raised 2026-09-22** (PR #158, the honesty lane). `doctor`, `probe` and the
  two local-status surfaces now share one computation
  (`device_probe.usable_memory_report`) and one format, and each names its
  source. That closed the code divergence. It did not make the numbers equal
  on this machine.
- **Why they still differ.** `metal` is the platform's own recommended working
  set, read through `torch.mps.recommended_max_memory()`. A process without
  torch — the web daemon — cannot ask Metal and falls back to our reserve
  heuristic. So on one 32 GB M1 Max at one instant: 24.96 GiB `[metal]` from
  the CLI, 28.80 GiB `[heuristic]` from the daemon. One function, two
  processes, one of which can reach Metal.
- **What we are not doing.** Forcing agreement would mean either making the
  daemon assert the metal number it cannot measure, or discarding a real
  measurement in `doctor`. Both trade a true reading for a matching one.
- **The option on the table.** Probe writes the measured limit to disk
  (`user_cache_dir()`), and any process without torch reads it — with the
  reading's age carried alongside, since RAM pressure moves the Metal figure.
  It is a real convergence rather than a cosmetic one. The cost is cache
  invalidation: a stale number that reads as measured is worse than a fresh
  one that reads as a guess.
- **Every fit verdict** in `/v1/models` and `spacepilot models` is computed
  from this number, which is why it is a decision and not a nit.
- **Close when**: Saurabh picks — cache it with an age, or keep naming the
  source and let the two numbers differ honestly.
