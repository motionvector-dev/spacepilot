# Pipette and Herdr — SpacePilot adjacents (2026-08-24)

Two GPT-5.6 research passes, digested and assessed by Fable. Source docs:
Saurabh's Downloads (`gpt-liquidai.research.md`, `gpt-herdr-research.md`).
**Status: context, partially verified.** The verification checklist below
must clear before any claim here enters product canon.

## Pipette (Liquid AI) — the evidence layer

- Benchmarks complete deployment configs: model × quant × runtime × device ×
  workload. Runners claimed for llama.cpp, MLX, OpenVINO, vLLM, SGLang.
- Independently validates SpacePilot's flown thesis: performance is a
  property of the whole configuration, measured, with readiness checks
  (cool + idle) before timing.
- Relationship: **consume, don't rebuild.** Pipette data slots into
  SpacePilot's provenance axes as high-trust *measured-elsewhere* ("on
  paper"), never "flown here". SpacePilot's own sweep infra is already a
  contention-aware mini-Pipette; an importer + a `spacepilot calibrate`
  command are the integration, queued post-v1 in the CLI plan.
- Moat restatement (third independent convergence): the benchmark graph is
  buildable by anyone; the asset is the decision made from public evidence ×
  your live private state — "a leaderboard that only exists at decision
  time."
- Risk: their `pipette-plan` + worker loop is proto work-distribution;
  Liquid could climb from benchmark scheduling to inference scheduling.
  Classify: partner-first, credible future competitor.

## Herdr — the adjacent runtime

- Agent runtime (persistent agent sessions across machines). Different noun:
  Herdr manages *agents*; SpacePilot manages *workloads*. Composable: their
  agents request work, our layer places it.
- Fourth independent convergence on the architecture: "the server owns the
  terminals; TUI/CLI/SSH are views" = one picture, many cockpits.
- The product lesson that changed our sequencing: launch one
  ten-second-explainable primitive, earn expansion. SpacePilot's equivalent:
  `spacepilot run <thing>` with a ranked, honest table — amendment sent to
  the CLI workstream to pull a local-only version forward.
- Watch trigger: any Herdr roadmap move into GPU awareness, provisioning,
  cost routing, or workload scheduling.

## Verification checklist (before canon)

- [ ] Pipette clients licence is Apache-2.0; data licence is separate
      (claimed "Pipette Data License v1.0", export by request)
- [ ] Pipette runner list and public device/model coverage
- [ ] Herdr traction (claimed 31.6k stars, 539k installs, YC F26) and
      Apache-2.0 licence
- [ ] Herdr "connect the machines" roadmap statement (YC page)
