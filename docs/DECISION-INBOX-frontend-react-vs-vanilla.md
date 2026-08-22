# Decision Inbox: React vs. Vanilla Frontend — settled by deployment

**Status**: Closed on the framework question. Open on the cleanup.
**Verified**: 2026-08-22, by `curl -I https://spacepilot.dev` (HTTP/2 200, `server: Vercel`, `last-modified` 07:41 UTC that day), by counting brand strings in the served HTML, and by `gh pr view 14 16`
**Supersedes / Superseded by**: supersedes the "contested" framing in `docs/REDESIGN-PLAN.md`

## What an earlier pass got wrong

An earlier version of this file called React and vanilla an open, unresolved conflict, and treated PR #14 as a large but unreviewed branch. That was wrong. It was written from the repo alone, without checking whether the product was live.

The product is live. That settles the framework question.

## What is verified

`https://spacepilot.dev` responds HTTP/2 200 from Vercel. It served a 5,737-byte SPA shell whose `<title>` is `SpacePilot 🛸 · Autonomous Generative Cinema Workstation`. That shell contains 19 occurrences of "SpacePilot" and zero of "Pluto". Its `last-modified` was 07:41 UTC on 2026-08-22, so the site is being deployed to actively, not parked.

PR #16 is stacked on PR #14 — its base is `feat/frontend-react-ui`, not `main`. A second session is fixing landing-page copy on that branch. Nobody stacks copy fixes onto a branch they consider speculative.

## What is inferred, not proven

That the deployed bundle is built from this repo's `ui/` tree is strongly supported but not proven. The evidence is PR #16's own statement that spacepilot.dev serves the built `ui/dist`, plus a near-match between the served HTML (5,737 bytes) and `ui/index.html` in a worktree (5,639 bytes) — close, but not identical, consistent with Vercel injecting analytics at the edge.

No deploy manifest exists in the repo. There is no `vercel.json`, `netlify.toml`, `Dockerfile`, or `CNAME`. The domain-to-repo mapping lives in a Vercel dashboard, outside version control. Anyone auditing this later cannot confirm it from the repo alone.

## What follows

React won, by shipping. `docs/REDESIGN-PLAN.md` proposes a vanilla, zero-build redesign for a frontend that is now a built React app in production. It is superseded, not contested.

The `studio/` vanilla tree is legacy. `docs/HANDOFF-2026-08-22.md` already describes it that way.

## What is still open

These are the real decisions left, and they are smaller than the one this file used to pose.

1. **`main` does not contain the production frontend.** `ui/` exists only on `feat/frontend-react-ui`. The site people can visit is built from a branch, not from the default branch. Merging PR #14 fixes that; leaving it open means `main` does not describe the product.
2. **CI has no coverage of `ui/`.** 12,765 lines of TypeScript with nothing gating build, typecheck, or lint. See PR #18, which scopes CI spend and deliberately leaves this gap open rather than deciding it in passing.
3. **Deploy config is not in the repo.** Committing a `vercel.json` would make the domain-to-repo link auditable.
4. **`studio/` has no stated end date.** It is legacy by description, but nothing says when it goes.

## What this does not settle

Whether PR #14 should merge as-is. It should not — an adversarial review confirmed eight blocking defects in it, including GPU-lifecycle controls that never send the auth token and a generation flow that fabricates success when the backend is down. Those are recorded against the PR, not here. The framework question is closed; the code quality question is not.
