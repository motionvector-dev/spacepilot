# Decision Inbox: React vs. Vanilla Frontend

**Status**: Open — awaiting decision
**Verified**: 2026-08-22, by `gh pr list`, `gh pr view 14`, and reading `docs/REDESIGN-PLAN.md`, `docs/PLUTO_FRONTEND_MIGRATION.md`, `docs/FRONTEND-SYNC-HANDOFF.md`
**Supersedes / Superseded by**: none — this doc records the conflict, it resolves nothing

## The conflict

Two frontend strategies exist side by side. Both are dated 2026-08-21. Neither has been withdrawn.

**Side A: React + Vite.** `docs/PLUTO_FRONTEND_MIGRATION.md` lays out the migration plan, and `docs/FRONTEND-SYNC-HANDOFF.md` assumes it as the integration target. This side is built: PR #14 (`feat/frontend-react-ui`) carries 75 files and 12,765 added lines, all under `ui/`. It is open, unreviewed, CI-green, and its merge state is CLEAN.

**Side B: vanilla HTML/JS.** `docs/REDESIGN-PLAN.md` explicitly rejects React and bundlers. It proposes a Runway-inspired redesign built on the existing zero-build vanilla stack. Its own header marks it `Status: Draft — Pending Approval`. No code for it exists yet.

These two plans cannot both be the frontend. One assumes a build step and a component framework; the other rejects both by design.

## Why merging #14 does not force the decision

PR #14 is purely additive. It touches zero backend files — everything it adds lives under `ui/`. That means it can merge cleanly into main without breaking anything and without requiring anyone to choose between React and vanilla. Both trees, `ui/` (React) and the existing `studio/` (vanilla), can sit in the repo at once.

This is exactly why the conflict can persist unnoticed. Nothing forces a resolution. CI stays green either way, because CI has no coverage of `ui/` today — a merge of #14 would add 12,765 lines with no test gate over them.

## What each path costs

**Merge #14 as-is, keep REDESIGN-PLAN alive.** Two frontends in one repo, no rule for which one is authoritative, no CI coverage for the new one. Anyone landing a UI change has to guess which tree to touch.

**Do nothing.** The ambiguity sits in the repo indefinitely. PR #14 stays open and unreviewed. REDESIGN-PLAN stays a draft nobody has approved or rejected. Two documents keep telling two different stories about the frontend.

**Pick a side.** Whichever side loses, some cost is already sunk: 12,765 lines of built React code on one side, or the Runway-inspired design work captured in REDESIGN-PLAN on the other.

## Options

Saurabh needs to choose one. This document does not recommend an option.

1. **Merge #14, retire REDESIGN-PLAN.** Review and merge the React frontend, mark `docs/REDESIGN-PLAN.md` superseded, and make `ui/` the one frontend going forward. Add CI coverage for `ui/` as part of the merge, since none exists today.
2. **Close #14, build vanilla.** Close the React PR, keep the existing `studio/` vanilla stack, and move `docs/REDESIGN-PLAN.md` from draft to active work. The 12,765 lines in #14 become sunk cost.
3. **Keep both, with an explicit boundary.** Decide what each frontend is for (for example: `ui/` for a specific surface, `studio/` for the rest), write that boundary down, and add CI coverage for both trees. This is the only option that does not require throwing away either side's work, but it is also the only one that keeps two frontends to maintain long-term.

## What happens until this is decided

Treat `docs/PLUTO_FRONTEND_MIGRATION.md` and `docs/FRONTEND-SYNC-HANDOFF.md` as describing a built-but-unreviewed PR, not an accepted direction. Treat `docs/REDESIGN-PLAN.md` as an unapproved draft, not a plan in progress. Neither is current authority on "the" Pluto frontend until this inbox entry is closed.
