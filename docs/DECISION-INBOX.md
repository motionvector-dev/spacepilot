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
