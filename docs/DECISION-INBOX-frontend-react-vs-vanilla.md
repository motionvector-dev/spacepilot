# Decision Inbox: React vs. Vanilla Frontend — settled by deployment

**Status**: Closed on the framework question. Open on the cleanup.
**Verified**: 2026-08-22, by `curl -I https://spacepilot.dev` (HTTP/2 200, `server: Vercel`, `last-modified` 07:41 UTC that day), by counting brand strings in the served HTML, and by `gh pr view 14 16`
**Supersedes / Superseded by**: supersedes the "contested" framing in `docs/REDESIGN-PLAN.md`

## What two earlier passes got wrong

The first pass called React and vanilla an open conflict and treated PR #14 as a large but unreviewed branch. The second pass saw spacepilot.dev serving React and concluded React had won by shipping. Both were wrong, in opposite directions.

What is deployed is the **landing page**. PR #16 fixes a star badge in `LandingPage.tsx`, which is the marketing surface. It is not evidence that the app works.

## What actually happened

The vanilla `studio/` app worked. It was the frontend until 2026-08-21.

The problem with it was file length, not function: `studio.css` is 3,402 lines, `studio.js` 1,977, `create.html` 1,848, `create.js` 1,375. Files that size are hard for agents to work in. On the night of 2026-08-21 the migration to React was handed to agy/Gemini to fix exactly that.

The migration is incomplete. It delivered the decomposition — 55 modules, average 198 lines, largest 677 — and a correct token-aware API layer in `ui/src/hooks/`. It did not connect the screens to it.

## Where it actually stands

VERIFIED by reading the tree:

- The hooks are right. `useGenerate.ts`, `useGpuStatus.ts` and `useCompute.ts` attach `X-Pluto-Token` across more than a dozen call sites.
- Five files bypass them. `pages/CockpitPage.tsx`, `pages/CreatePage.tsx` and `components/cockpit/MultiCloudProviderHub.tsx` call `fetch()` directly without the token. `stores/gpuStore.ts` and `stores/studioStore.ts` hold hardcoded state that nothing updates.
- Every blocker found in the adversarial review of PR #14 sits in those five files. None are spread across the other fifty.

That is the whole gap. The surfaces were rebuilt faithfully and wired to mock data instead of to the hooks sitting next to them.

## What follows

Neither "React won" nor "React failed" is right. The expensive half — decomposition and the API layer — is done and correct. The cheap half is missing.

`docs/REDESIGN-PLAN.md` remains superseded, but not because React shipped. It proposes a vanilla redesign, and the vanilla stack is the thing being migrated away from for a reason that still holds: agents cannot work well in 3,400-line files.

Until the five files are connected, `studio/` is still the working app and `ui/` is an unfinished migration whose landing page happens to be deployed.

## What is still open

These are the real decisions left, and they are smaller than the one this file used to pose.

1. **`main` does not contain the production frontend.** `ui/` exists only on `feat/frontend-react-ui`. The site people can visit is built from a branch, not from the default branch. Merging PR #14 fixes that; leaving it open means `main` does not describe the product.
2. **CI has no coverage of `ui/`.** 12,765 lines of TypeScript with nothing gating build, typecheck, or lint. See PR #18, which scopes CI spend and deliberately leaves this gap open rather than deciding it in passing.
3. **Deploy config is not in the repo.** Committing a `vercel.json` would make the domain-to-repo link auditable.
4. **`studio/` has no stated end date.** It is legacy by description, but nothing says when it goes.

## What this does not settle

Whether PR #14 should merge as-is. It should not — an adversarial review confirmed eight blocking defects in it, including GPU-lifecycle controls that never send the auth token and a generation flow that fabricates success when the backend is down. Those are recorded against the PR, not here. The framework question is closed; the code quality question is not.
