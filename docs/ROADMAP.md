# SpacePilot roadmap

Status: release preparation · Checked: 2026-10-08 · Scope: published artifacts, local worktrees, GitHub CI and Vercel configuration.
Main baseline: `9bc8a2d1a25016f6f4d7740f482eef5b589fcf2d`.
This roadmap supersedes BUILD-PLAN's release sequencing; that document retains historical task detail.

## Release decision

Prepare **v2.10.0** with a new immutable tag after CI and founder review.
Do not rebuild or republish v2.9.0. Do not move the existing v2.9.0 tag.
The founder assigned the release blockers for completion on 2026-10-08; this is the working release scope, pending final publication approval.

## What is published

PyPI v2.9.0 was uploaded on 2026-09-24 at 16:47 UTC. GitHub v2.9.0 remains a draft; its public latest release is v2.8.0.
The earlier [publish failure](https://github.com/motionvector-dev/spacepilot/actions/runs/36110141436) reports `invalid-publisher`, but it is historical evidence, not proof that PyPI has no package today. Current trusted-publisher settings are not confirmed.

The PyPI and draft wheels have identical package code/data. Only dist-info/METADATA (the README) and RECORD differ. Both wheels leave CoreAI unwired. Every package file in the PyPI wheel matches source at `dea46bd`; the current v2.9.0 tag points at `9bc8a2d`, whose package files differ. Version alone is insufficient provenance for this release.

| Wheel | SHA256 |
| --- | --- |
| PyPI v2.9.0 | bc60ce001c516defacb83c42591e896c81fba4a1967e275fbe90a683bc212dc9 |
| GitHub draft v2.9.0 | 24ccf211c72d60b2df332fc4dae382fa6dbbddc72f9e35397ea2ece78ee3f5a5 |

Treat the v2.9.0 draft as historical until its tag/artifact discrepancy is explicitly resolved. The next release uses a distinct version and tag, preserving existing records.

## v2.10.0 scope

1. Include later main changes: gated CoreAI serving, MiniCPM5 registry evidence, board fixes, hosted CI and OSS documentation. CoreAI remains non-default with the long soak outstanding.
2. Include repaired PR #188 primitives: pinned staged downloads, loopback text runtime loading, selected runtime unload, resident-model inspection, verbose/version CLI flags and bench commands. Keep shipped aliases available.
3. Include image registry additions carried by PR #188 (Qwen-Image 2.1 and Ideogram) and H3 planning metadata with its actual community license.
4. Include the video HTTP client as unflown plumbing for a separately deployed compatible backend. Do not claim a measured SpacePilot video render or automatic worker deployment.
5. Permit AWS dry-run validation only. Paid launch stays gated pending a dock budget and worker deployment; see DECISION-INBOX.md.

## Release gates

1. Public branch pushes and PR updates were approved and completed on 2026-10-08. [Train PR #189](https://github.com/motionvector-dev/spacepilot/pull/189) combines the release-preparation branch, repaired PR #188 and dependency PR #186; package version is 2.10.0 and draft release notes are committed. The founder alone merges the train to main.
2. Run full pytest, packaging and security checks on the combined train. Main CI [36108122821](https://github.com/motionvector-dev/spacepilot/actions/runs/36108122821) passed at `9bc8a2d`; it does not validate PR #188. Focused regressions first failed against the original PR and passed after repair. Lenovo SSH timed out on 2026-10-08; full validation runs on hosted CI. The first full audit run passed 1,155 tests and found one generate-parser conflict, now corrected with 29 focused tests passing. Final combined CI is pending.
3. Verify Vercel previews for the combined commit. Both existing projects now use the landing Vite app. The ignore command is `git diff --quiet HEAD^ HEAD -- ':(top)landing/'`, independent of working directory. The PR #188 preview is Ready and returned authenticated HTTP 200 with the SpacePilot title. The train has identical landing source; subsequent preview builds were correctly ignored because landing files did not change.
4. Review package version 2.10.0, CHANGELOG.md and RELEASE_NOTES_v2.10.0.md against the final train. Inspect clean wheel/sdist contents and run the installed-wheel CLI gate.
5. Verify PyPI publishing access for the exact repo `motionvector-dev/spacepilot`, workflow `publish.yml`, environment `pypi`. Chrome shows the signed-in `unfoundbox` account and published v2.9.0. Publishing settings now confirm no trusted publisher exists. The exact publisher form is prepared; approval for the grant remains pending. Obtain action-time approval before a new publishing grant.
6. After the founder merges the train, obtain package/release publication approval and tag that exact commit as v2.10.0. The workflow validates tag/version equality, publishes through OIDC, and creates or finalizes the matching GitHub release. Verify public installation and artifact hashes.

The instructed `~/code/motionvector/docs/GIT-FLOW.md` is absent. Existing AGENTS.md supplies the train rule; no default-branch merge is delegated. Remote historical trains are `main-2026-09-22` and `main-2026-09-23`; neither has an open PR in the inspected list.

## Branch and worktree inventory

Counts use main `9bc8a2d`, before the audit repairs (ahead / behind).

| Branch | Count | Treatment |
| --- | --- | --- |
| feat/h3-aws-launch | 20 / 0 | PR #188, repaired in codex/pr188-release-fixes. Original CI had 32 pytest failures and 3 new Bandit findings; packaging was cancelled. |
| feat/qwen-image-2-1-registry | 2 / 0 | Both commits already occur in PR #188; do not merge twice. |
| feat/registry-sept-2026-models | 3 / 86 | Old GTM and registry work; reconcile before reuse. |
| spec/docs-surface-v3 | 1 / 2 | PR #182, design only. |
| spec/litert-lm-runtime | 1 / 2 | PR #181, design only. |
| main-2026-09-22 | 0 / 39 | Historical train. |

The other original local branches have no commits unique to main. Preserve all branches.
The root worktree is clean on `feat/h3-aws-launch` at `3abdd9b`.
The positioning worktree is clean and detached at `9bc8a2d`.
The two detached worktrees under `~/code/.mvec-local/worktrees/main/` were repaired with `git worktree repair` on 2026-10-08. `cockpit` at `f45110b` is clean. `spacepilot` at `3d43e93` holds a Qwen1.5 measurement byte-identical to main and a system record older than main's 2026-09-22 record. No unique release change is unaccounted for; leave the worktrees intact.

## Repair evidence

PR #188 fixes remove the CLI/preferences circular import, restore shipped CLI aliases and output-helper behavior, bind text servers to loopback, reject arbitrary backend modules, require confirmation and cache containment for MCP mutations, pin and narrow downloads, reject cross-origin video URLs/redirects, and fail unfinished video jobs. Unchecked runtime health stays unknown; text loaders refuse video deployment. Loading requires an explicit weights directory. The focused release-boundary suite passes 18 tests; the combined runtime, CLI and H3 registry selection passes 32 tests in 1.66 seconds. Full combined CI remains outstanding.

AWS STS and service-quotas confirmed account `842954813809`, profile `antigravity-dev-user`, region `us-east-1`, and G-family Spot quota 8 on 2026-10-08. No paid instance was started. H3 hardware costs and speed rankings remain planning estimates, not measured or live quotes.

## Later work

1. PR #186 is included in the release train: PyJWT 2.15.0, urllib3 2.8.0 and Accelerate 1.15.0 move beyond the affected ranges of the 17 alerts read on 2026-10-08 (including one critical). Reconcile Actions dependency PRs #184–#185, GTM PR #187 and the old September branch separately.
2. Implement docs generation and LiteRT-LM after their design reviews; do not call design PRs shipped features.
3. Revalidate BUILD-PLAN against code before implementation. Keep SpaceBar read-only and video claims tied to measured output.
