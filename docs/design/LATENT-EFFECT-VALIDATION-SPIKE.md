> **DESIGN DOC  /  v0.1**

# Quick Validation Spike: Latent Effect Decoding

*The shortest falsifiable test of a model-to-runtime boundary for MotionVector*

| Field | Value | Field | Value |
|:---|:---|:---|:---|
| **Owner** | Research team | **Duration** | 4 hours + 1 day |
| **Substrate** | MotionVector effect IR | **Status** | Ready to run |



## Decision this experiment makes

> **One question, one boundary**
> Can a frozen local language model's hidden state be decoded into a small, typed MotionVector effect record with accuracy comparable to a constrained token output—without generating code or general JSON?


### Why this is the quickest useful test

- It tests the novel boundary directly: latent state → typed semantic effect.
- It requires no renderer changes, semantic framebuffer, OS integration, or large-scale training.
- It produces interpretable evidence within hours: per-layer separability, exact-record accuracy, invalid-effect rate, and latency.
- A negative result is valuable: it tells us to keep the token interface or redesign the effect vocabulary before building infrastructure.

### Two gates

| **Gate** | **Time** | **Question** | **Advance when** |
| :--- | :--- | :--- | :--- |
| 0 — separability | ≈4 h | Do hidden states contain a clean effect signal? | Held-out op macro-F1 ≥ 0.80 |
| 1 — structured effect | ≈1 day | Can the latent head match a token baseline? | Within 5 pp exact accuracy, or ≥30% lower latency |


> **Interpretation limit**
> Success validates a research direction, not the complete agentic-computing thesis. The action space is deliberately small and closed.


## 1. Experimental contract


### Research question

Given a compact scene state and a natural-language goal, does a frozen model encode enough task structure at an internal layer for a small learned decoder to select a valid semantic effect?


### Falsifiable hypotheses

| **ID** | **Hypothesis** | **Primary test** |
| :--- | :--- | :--- |
| H1 | Effect class is linearly decodable from at least one middle or late layer. | Linear probe, held-out template families |
| H2 | A two-layer MLP decodes op + target + argument nearly as accurately as constrained token output. | Exact structured-record accuracy |
| H3 | The latent route reduces serialization cost and decision latency. | p50/p95 latency and emitted bytes/tokens |
| H4 | A confidence threshold supports useful abstention rather than unsafe guessing. | Risk–coverage curve; invalid-effect rate |



### In scope

- Frozen, locally runnable open-weight instruct model; use the model already working on your machine.
- Six semantic operations, candidate target IDs, and one small categorical or numeric argument.
- Synthetic but validator-clean MotionVector-like states, plus an optional small real-state sanity set.
- Linear and two-layer MLP latent heads compared with direct and constrained token baselines.
- Existing effect validation and deterministic application; rendering is optional evidence, not part of the learned path.

### Explicitly out of scope

- Arbitrary code generation, free-form strings, multi-step planning, or end-to-end app generation.
- Semantic framebuffer, object-indexed perception, new Vello/wgpu work, or GPU co-scheduling.
- Capability OS, cross-app authority, AWS training, or cross-platform replication.
- Claims of a complete replacement for conventional software interfaces.

### Unit of analysis

One example is a triple (state, goal, effect). The model sees state + goal + a fixed decision marker. The target is one effect record. No chain-of-thought is requested or stored.


## 2. Minimal task and dataset


### Effect record

Use a fixed typed record. For Gate 0, predict only op. For Gate 1, add target and argument heads.

> **Canonical record**
> { op: EffectOp, target: CandidateId, arg_kind: ArgKind, arg_value: Category | normalized float, confidence: float }


### Initial effect vocabulary

| **Operation** | **Argument** | **Example goal** | **Validator rule** |
| :--- | :--- | :--- | :--- |
| SetText | text_slot* | Change the title to the supplied text slot. | Target is text-capable |
| SetFill | color enum | Make the selected card blue. | Target supports fill |
| MoveNode | direction + bucket | Move the icon slightly right. | Target is movable |
| SetDuration | duration bucket | Make the transition slower. | Timeline target exists |
| DeleteNode | none | Remove the secondary badge. | Target is deletable |
| NoOp / Clarify | reason enum | Make it better. | Goal is ambiguous or invalid |


*For the spike, choose from 4–8 supplied text slots. Do not generate arbitrary strings; that adds a separate sequence-decoding problem.


### Dataset size and construction

**Minimum  **600 examples: 6 ops × 10 template families × 10 state/wording variations.

**Better same-day target  **1,200 examples, balanced by op and approximately balanced by target position.

**State  **4–12 candidate objects with type, capabilities, compact properties, and randomized opaque IDs.

**Goal  **Short human instruction. Mix direct, paraphrased, referential, ambiguous, and impossible requests.

**Labels  **Deterministically generated and passed through the effect validator before admission.


### Split that prevents an easy false positive

- 70/15/15 train/validation/test, grouped by instruction template family—not random paraphrase rows.
- Randomize object order and opaque IDs independently in every split.
- Reserve at least two state-layout generators for test only.
- Record a fixed split seed and a dataset hash.
> **Leakage test**
> Train a cheap bag-of-words classifier on the goal alone. If it scores unusually high on target selection, the dataset leaks target position or template cues; repair before probing the model.


## 3. The model interface and experiment arms


### Model choice

Use the smallest open model already running locally that can expose hidden states. A 4B–8B instruct model is ideal for turnaround. If your existing 20B–30B MLX setup already exposes activations reliably, keep it; changing stacks is not part of this experiment.


### Prompt and activation capture

1. Serialize the compact state, candidate text/color/duration slots, and goal in a fixed prompt.
2. Append a literal marker such as EFFECT_DECISION:. Do not ask for reasoning.
3. Capture the hidden vector at the final marker token from 25%, 50%, 75%, and 100% depth.
4. Store vectors once (float16 is sufficient for storage); train all probes offline with the backbone frozen.
5. Fit heads on train, choose layer/hyperparameters on validation, and open test exactly once.

### Required arms

| **Arm** | **Output route** | **Purpose** | **Keep fixed** |
| :--- | :--- | :--- | :--- |
| A — direct token | Model emits compact JSON | Practical unconstrained baseline | Prompt, model, decoding budget |
| B — constrained token | Grammar or enumerated labels | Strong typed-token baseline | Same record vocabulary |
| C — linear latent | One affine head per field | Tests linear accessibility | Frozen hidden vectors |
| D — MLP latent | 2-layer head, small bottleneck | Tests lightweight nonlinear decoding | Frozen vectors; ≤1M params preferred |



### Fast fallback when grammar tooling is absent

Replace Arm B with enumerated single-label decisions: one pass for op, one for target, one for argument. Record that this is a token-classification baseline, not a full grammar-constrained decoder. Do not delay Gate 0 for grammar integration.


### Head structure

- Op head: 6-way softmax.
- Target head: masked softmax over candidates; mask invalid candidate capabilities.
- Argument head: categorical buckets first; optionally add normalized scalar regression later.
- Confidence: calibrated maximum probability or a learned accept/abstain head.
> **Capability boundary**
> The decoder proposes. A deterministic validator rejects type, target, range, and authority violations before any state mutation.


## 4. Evaluation and decision rules


### Primary metrics

| **Metric** | **Definition** | **Why it matters** |
| :--- | :--- | :--- |
| Exact record accuracy | op + target + argument all correct | Main Gate 1 quality measure |
| Op macro-F1 | Unweighted F1 across six ops | Robust to class imbalance |
| Target accuracy | Correct candidate among valid candidates | Tests grounding in state |
| Invalid-effect rate | Rejected proposals / all proposals | Safety and runtime compatibility |
| Risk–coverage | Error as low-confidence cases abstain | Whether uncertainty is useful |
| Decision latency | p50/p95 from prompt-ready to validated record | System-level advantage |
| Serialization cost | Tokens and bytes emitted after model compute | Measures interface overhead |



### Gate 0 — continue or stop

| **Outcome** | **Threshold** | **Action** |
| :--- | :--- | :--- |
| GO | Best test op macro-F1 ≥ 0.80 and ≥0.10 above goal-only control | Run Gate 1 |
| PROMISING | 0.65–0.79 or strong validation/test gap | Repair split/data; rerun once |
| STOP / PIVOT | <0.65 after one repair, or near goal-only control | Redesign marker, state encoding, or effect vocabulary |



### Gate 1 — evidence grades

| **Grade** | **Required evidence** | **Claim supported** |
| :--- | :--- | :--- |
| Strong | Latent MLP within 5 pp of constrained token exact accuracy AND ≥30% lower p50 decision latency; invalid <5% | A latent typed-effect boundary is technically competitive in this closed task |
| Directional | Exact accuracy trails by 5–15 pp, but op macro-F1 ≥0.85 and latency/serialization improves materially | The signal exists; decoder/task design deserves iteration |
| Negative | >15 pp quality gap, poor held-out transfer, or unusable calibration | Do not expand runtime work yet |


> **Statistical hygiene**
> Run three probe seeds; bootstrap 95% confidence intervals on paired accuracy differences; use identical examples and protocols; report every layer and select by validation only.


## 5. Implementation plan


### Minimal repository shape

> **experiment/latent-effect-spike/**
> schema • generate_dataset • validate_dataset • extract_hidden • train_probe • eval_token_baselines • evaluate • results/<run_id>/


### Run sequence

| **Block** | **Elapsed** | **Deliverable** | **Stop condition** |
| :--- | :--- | :--- | :--- |
| Schema | 0:00–0:45 | 6 ops, capability masks, JSON Schema | Validator ambiguity remains |
| Dataset | 0:45–2:00 | 600–1,200 valid triples + grouped split | Goal-only leakage is high |
| Extraction | 2:00–3:15 | Four layer matrices + manifest | Vectors mismatch rows or contain NaNs |
| Gate 0 | 3:15–4:00 | Layer × probe metrics and confusion matrix | Apply Gate 0 rule |
| Gate 1 | Day 1 | Four-arm prediction files and benchmark | Apply evidence grade |
| Optional realism | +2–4 h | 50–100 real docIR states | Synthetic result fails to transfer |



### Required invariants

- Every label validates before training; every prediction is validated before scoring as executable.
- Example IDs remain stable across activations, labels, and all prediction files.
- Target masks derive from state capabilities, never from the gold answer.
- No model weights are updated; only the small heads train.
- No test-set decisions are made until code, thresholds, and report format are frozen.

### Optional MotionVector confirmation

For 20 correctly predicted and 20 failed effects, apply the record through the real docIR validator and deterministic state transition. Render before/after only if it is already one command. This confirms runtime compatibility; it should not block the core measurements.

> **Failure triage order**
> First check leakage, labels, row alignment, and masks. Then verify the marker token and compare layers. Finally slice errors; only then enlarge the head, data, or backbone.


## 6. Result packet to bring back

Return the following artifacts unchanged. With this packet, we can determine whether the thesis is strengthened, merely plausible, or falsified at this scale—and choose the next experiment without guessing.


### Machine-readable files

| **File** | **Minimum contents** |
| :--- | :--- |
| manifest.json | model/checkpoint, quantization, model hash, layer indices, marker tokenization, hardware, framework versions, git commit, split seed |
| metrics.csv | one row per arm × layer × seed × split; all primary metrics plus sample count |
| predictions.parquet or .csv | example_id, gold fields, predicted fields, confidence, valid flag, latency, emitted tokens/bytes |
| failures.jsonl | at least 20 diverse failures with state, goal, gold, prediction, layer/arm, validator reason |
| dataset_summary.json | counts by op, target type, template family, ambiguity class, candidate count; dataset hash |
| latency.json | warm-up count, repetitions, synchronization method, p50/p95, end-to-end boundary timestamps |



### One-page human summary

- Best layer and whether performance peaks in middle or late depth.
- Four-arm comparison with confidence intervals and seed variation.
- Confusion matrix and risk–coverage plot.
- Three representative successes, three failures, and your qualitative surprise.
- Gate decision: GO, PROMISING, or STOP / PIVOT—with no threshold changes after seeing test.

### Questions the datapoints will answer

1. Is the effect representation present, and at which layer?
2. Is target grounding harder than operation selection?
3. Does latent decoding buy real latency, or only remove visible serialization?
4. Does capability masking improve safety without hiding model errors?
5. Does performance survive held-out templates and real docIR states?
> **Recommended immediate start**
> Run Gate 0 with six operations, 600 examples, four layers, and two probes. If it exceeds four hours, reduce state complexity—not controls. After a GO, expand arguments, add transactions and a generated-code baseline; perception comes later.
