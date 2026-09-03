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

### Public demo cost model: BYOK vs SpacePilot subsidizing inference

- **Raised 2026-09-03**, direction agreed, not yet written as policy. A
  public/open-source demo that calls a paid model (voice, chat) cannot default
  to SpacePilot's own hosted credits — nothing stops unlimited free use by
  strangers. The Archie hackathon demo sidestepped this by going
  voice-optional and gesture-first instead of resolving it.
- **Working direction:** a public demo either (a) stays local/free-tier only
  (on-device models, no paid call), (b) asks the visitor for their own
  OpenAI/Gemini Live key (BYOK), or (c) runs behind a capped, monitored budget
  Saurabh explicitly sets. No demo defaults to (a) unlimited SpacePilot-hosted
  credits.
- **Close when:** one of the three options above is written into
  `docs/design/CONCEPT.md` as the standing rule for anything public-facing,
  not just remembered from this conversation.

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

## Log

### 2026-09-03 — SpaceBar icon, shared speech API, board bugs, WebMCP hackathon

Three PRs pushed today, **none merged yet — GitHub Actions is stuck queued**
on all three (pytest/packaging never started as of tonight, not a red run).
Check the Actions queue before merging tomorrow.

- [#124](https://github.com/motionvector-dev/spacepilot/pull/124) — SpaceBar
  ship-silhouette icon with state-driven motion (draft, Opus-reviewed clean).
- [#125](https://github.com/motionvector-dev/spacepilot/pull/125) — shared
  `/api/speech/transcribe` and `/api/speech/say` (built for a peer session's
  WebMCP hackathon demo). Bundles a real security fix: CORS was widened to
  reach these routes from a public demo page, which also newly exposed
  `studio_token` (unlocks the GPU shell websocket) to anything CORS could
  reach. Fix: a separate, narrowly-scoped `speech_token`, regenerated fresh on
  every daemon start, that opens only the two speech routes.
- [#126](https://github.com/motionvector-dev/spacepilot/pull/126) — four
  board bugs fixed (cockpit config key mismatch, hardcoded runtime fallback,
  Spotlight indexing the app bundle, a test-isolation leak in registry
  export tests).
- **Not SpacePilot's repo, but built alongside it tonight:** the WebMCP
  hackathon submission itself shipped and is public —
  [Air Instruments](https://github.com/unfoundbox-crew/air-instruments) (gesture
  instruments + agent-taught lessons) and a second entry,
  [Archie](https://devpost.com/software/archie-voice-first-webmcp-agent)
  (voice-first, built on this repo's new speech API). Both are `unfoundbox-crew`
  work, referenced here only because #125 exists to serve them.
- **Real incident, root-caused:** a second agent dispatched into a worktree
  already checked out on a branch silently evicted the worktree backing a
  live local daemon and took it down. Fix pattern: run long-lived local
  daemons from a **detached-HEAD** worktree pinned to a commit, never a
  branch-tracking one another dispatch can reclaim.
- **Not done tonight:** `docs/BUILD-PLAN.md` was not re-validated against
  these three PRs — it still describes main as of 2026-09-02. Needs a
  freshness pass once #124/#125/#126 land, per the doc's own "evidence
  expires" rule.
- **Found while writing this up, unresolved:** `.worktrees/spacebar-handoff`
  has an uncommitted edit to `native/SpaceBar/Sources/SpaceBarApp.swift` on a
  branch whose PR (#97) was closed, and this worktree
  (`fable-mythos-ascii-guide-9c6a45`) has an uncommitted 357+/53- rewrite of
  `voice/web/voice.html` with no matching commit or PR. Neither was touched —
  unknown-provenance uncommitted work is Saurabh's call, not an agent's.
