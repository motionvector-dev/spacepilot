# SpacePilot v2.10.0 — release candidate

Status: prepared locally on 2026-10-08; not tagged or published.

This release aligns the package with changes that followed the published v2.9.0 artifacts and includes the corrected PR #188 scope. The existing v2.9.0 tag contains newer source than its published wheels; keep that tag and those artifacts unchanged.

## Changes

- Gated CoreAI Qwen3.5-9B serving with thinking enabled by default; the long soak remains outstanding.
- MiniCPM5-2B measurements and updated model registry snapshots, including MiniMax H3, Qwen Image and Ideogram metadata.
- Text runtime loading through allowlisted backends, loopback binding and the current Python interpreter. Skipped health checks report an unknown result.
- Revision-pinned model downloads with bounded concurrency and variant file filters.
- MCP mutations require explicit confirmation and use canonical cache paths.
- Video endpoint client rejects cross-origin download URLs and redirects and reports polling timeouts. No GPU deployment or measured H3 performance is claimed.
- CLI compatibility restored, startup import cycle fixed and loading requires a weights directory.
- Release workflow verifies the immutable tag and package version before building.

## Limits

AWS Spot recommendations use the verified 8 vCPU quota. Live provisioning stays disabled until budget enforcement and authenticated worker deployment are implemented. Estimates are labeled as estimates. H3 has a custom license that requires review for the intended use.

## Release gates

1. Approve the public branch pushes and PR updates.
2. Pass the combined train CI, security and clean-install packaging checks.
3. Verify the landing preview after the Vercel configuration repair.
4. Confirm the PyPI trusted publisher matches motionvector-dev/spacepilot, publish.yml and environment pypi.
5. Saurabh reviews and merges the train to main.
6. Approve publication, create a fresh v2.10.0 tag on the reviewed commit and publish matching wheel and source artifacts.

See [ROADMAP.md](docs/ROADMAP.md) for evidence and remaining decisions.
