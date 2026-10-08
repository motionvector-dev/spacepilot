# SpacePilot roadmap

Status: release preparation · Checked: 2026-10-08 · Scope: local branch audit and GitHub release metadata.
Code baseline: main and tag `v2.9.0` at `9bc8a2d1a25016f6f4d7740f482eef5b589fcf2d`.
This roadmap supersedes BUILD-PLAN's release sequencing; that document retains historical task detail.

## Next release decision

The public GitHub release is v2.8.0. v2.9.0 is a draft with a wheel and source archive attached.
The package version is 2.9.0. Main contains no commits after the v2.9.0 tag.
Finish v2.9.0 before widening scope is the working sequence for the 2026-10-08 preparation.
PR #188 is a separate candidate for v2.10.0, not part of v2.9.0.

## Release gates

1. Configure the PyPI trusted publisher for owner `motionvector-dev`, repository `spacepilot`, workflow `publish.yml`, environment `pypi`. Publishing run [36110141436](https://github.com/motionvector-dev/spacepilot/actions/runs/36110141436) failed with `invalid-publisher`; current account settings are not confirmed.
2. Review corrected v2.9.0 notes against the tagged source. CoreAI is wired but non-default; the long soak is outstanding. Registry measurements belong to v2.9.0, not Unreleased.
3. Obtain approval for public branch/PR publication. Merge through the agreed release branch; do not move or replace tag v2.9.0. The instructed `~/code/motionvector/docs/GIT-FLOW.md` is absent, so train procedure needs confirmation before a push. Remote branches include `main-2026-09-22` and `main-2026-09-23`; neither has an open PR in the inspected list.
4. Verify artifacts before PyPI publication. Main CI [36108122821](https://github.com/motionvector-dev/spacepilot/actions/runs/36108122821) passed at `9bc8a2d`; this audit did not rerun hardware inference or rebuild the draft assets.
5. Publish from an approved ref and verify PyPI plus GitHub installation artifacts. The workflow change in this preparation branch does not change the workflow frozen at tag v2.9.0. The preparation workflow accepts an explicit existing tag on manual dispatch, builds that tag after checking the package version, and finalizes the existing draft with corrected notes from the workflow ref. After approval and PyPI setup, dispatch `publish.yml` from the preparation branch with `release_tag=v2.9.0`. Do not move the tag or rerun its old workflow.

## Branch and worktree inventory

Counts are unique commits relative to main `9bc8a2d`, ahead / behind.

| Branch | Count | Release treatment |
| --- | --- | --- |
| feat/h3-aws-launch | 20 / 0 | PR #188: atomic inference, AWS launch, video client; unmerged. Security and Vercel checks failed; pytest and packaging were pending at inspection. |
| feat/qwen-image-2-1-registry | 2 / 0 | Qwen-Image 2.1 and Ideogram registry changes; review separately. |
| feat/registry-sept-2026-models | 3 / 86 | Old work includes GTM and registry changes; reconcile with main before reuse. |
| spec/docs-surface-v3 | 1 / 2 | PR #182, design only; does not ship generated docs. |
| spec/litert-lm-runtime | 1 / 2 | PR #181, design only; does not ship a runtime. |
| main-2026-09-22 | 0 / 39 | Historical train, not a release baseline. |

The other local feature/chore branches have no commits unique to main. Preserve all branches.
The root worktree is clean on `feat/h3-aws-launch` at `3abdd9b`.
The positioning worktree is clean and detached at `9bc8a2d`.
The two detached worktrees under `~/code/.mvec-local/worktrees/main/` were repaired on 2026-10-08 with `git worktree repair`. `cockpit` at `f45110b` is clean. `spacepilot` at `3d43e93` holds the Qwen1.5 measurement already shipped on main (byte-identical) and an older system record superseded by main’s 2026-09-22 record. Preserve the worktrees; no unique release change remains unaccounted for.

Open dependency PRs #184–#186 and GTM PR #187 need separate review. Do not infer readiness from an open PR.

## After v2.9.0

1. Decide v2.10.0 scope for PR #188. Require passing security, packaging and pytest checks; inspect cloud spend authorization, token checks, download containment and real failure reporting before acceptance. Do not launch a rented instance to validate readiness.
2. Reconcile the image registry branch and old September branch; retain only changes still missing from main.
3. Implement docs generation and LiteRT-LM only after reviewing their design PRs. Keep proposed features separate from shipped behavior.
4. Revalidate BUILD-PLAN phases against code before using them as implementation tasks. Keep SpaceBar read-only; keep video claims tied to measured model output.

## Limits of this audit

Local refs match the inspected remote main SHA. GitHub metadata and CI results were read directly on 2026-10-08. PyPI account configuration and current live inference are not confirmed. Repaired worktree edits were inspected and reconciled with main. No branch was merged, no release was published, and no paid compute was started.

## Repair work on 2026-10-08

The founder assigned the release blockers for completion. The PR #188 repair branch fixes the CLI/preferences circular import, restores shipped CLI aliases, binds text runtimes to loopback, rejects arbitrary runtime modules, requires confirmation and cache containment for MCP mutations, pins and narrows staged downloads, blocks cross-origin video downloads, and refuses unfinished video jobs. New regression tests first failed on the original branch.

AWS STS and service-quotas confirmed account 842954813809 and quota 8 on 2026-10-08. Paid launch stays gated until the dock budget and worker deployment exist; dry-run planning is the candidate release scope. H3 license metadata is corrected from Apache-2.0 to the upstream community license. No H3/video flight is claimed.

Vercel preview failures were diagnosed: project `spacepilot` incorrectly selects FastAPI at the repo root; `spacepilot.dev` uses an ignore command that interprets landing/ as a revision/path from the wrong directory. Project configuration repairs are prepared for the existing landing/ Vite app.
