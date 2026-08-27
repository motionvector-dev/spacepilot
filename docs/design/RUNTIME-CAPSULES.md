# Runtime Capsules

**Status:** Draft

**Scope:** Local inference runtimes on ships

**Decision owner:** MotionVector

**Last updated:** 2026-08-27

## Summary

SpacePilot must stop treating an importable Python package as an inference
runtime. A runtime is an independently provisioned, immutable execution
capsule with an exact interpreter, a complete dependency lock, a hardware
probe, a real canary inference, and a stable subprocess protocol.

The SpacePilot control plane never imports an ML runtime. It selects a verified
capsule, resolves pinned model weights, shows the plan, and invokes the capsule
as a child process. Runtime dependency changes therefore cannot mutate or
break the CLI, another runtime, or the user's project environment.

This turns dependency churn from a workstation failure into compatibility
evidence: candidate capsules are built and tested in isolation, promoted only
after their probes succeed, and rolled back by changing a pointer.

## Problem

The current runtime registry describes an install using a package name and a
minimum version. Installation targets a Python interpreter selected from the
calling process or environment. Readiness is primarily an import check.

That model has four structural failures:

1. **A minimum version is not a compatibility contract.** `mlx-lm>=0.31.3`
   says nothing about which Transformers, tokenizer, MLX, NumPy, or Python
   versions work together.
2. **The calling interpreter is not the execution environment.** A pipx
   SpacePilot installation, a configured Conda environment, and a checkout can
   all resolve different Python executables while appearing to describe one
   runtime.
3. **Shared environments make unrelated runtimes coupled.** Installing one
   runtime can upgrade or downgrade a transitive dependency required by
   another runtime or by SpacePilot itself.
4. **An import is weaker than readiness.** It does not prove that Metal or CUDA
   is usable, that the selected model architecture loads, or that one token can
   be generated.

These failures are expected outcomes of the architecture, not exceptional pip
accidents. More version checks inside the same shared environment will not fix
them.

## Goals

- Give every runtime an exact, reproducible execution environment.
- Keep the SpacePilot control plane independent of inference dependencies.
- Make `ready` mean that real work completed on this machine recently.
- Prevent runtime installation from mutating any existing environment.
- Support atomic promotion, rollback, coexistence, and garbage collection.
- Preserve one shared, deduplicated model cache across runtime capsules.
- Record enough identity to reproduce and compare every flown measurement.
- Support released packages and explicitly marked experimental source pins.
- Make dependency failures visible before a model download or large load.

## Non-goals

- Building a general-purpose replacement for uv, Conda, pip, or Nix.
- Containerizing Metal execution. Linux containers on macOS are not the local
  accelerator boundary SpacePilot needs.
- Guaranteeing that a lock built for one OS and architecture works elsewhere.
- Declaring a runtime safe merely because dependency resolution succeeded.
- Combining all local ML packages into one universal environment.
- Hiding source builds, prereleases, or experimental commits behind a stable
  label.

## Principles

### The control plane is not a runtime

The `spacepilot` command, daemon, API, registry, planner, and measurement
writer form the control plane. Its environment contains only control-plane
dependencies. Runtime packages are imported only inside capsule subprocesses.

### Isolation is the default

Every runtime owns its Python environment. Sharing is permitted only through
content-addressed package caches and model caches, never through an import
path.

### Exact inputs, measured outputs

Dependency versions, artifact hashes, source commits, interpreter builds, and
model revisions are exact inputs. Import success, accelerator availability,
load success, and generation speed are measured outputs. One must never stand
in for the other.

### Ready is a live fact

`installed` means files exist. `verified` means static and import probes
passed. `ready` means a representative canary completed on the selected ship.
Every readiness result carries a timestamp and expires.

### Promotion is atomic

A candidate is constructed in a temporary directory. The active runtime is
unchanged until every required probe passes. Promotion replaces one pointer;
rollback restores the previous pointer.

## Architecture

```text
                         SPACEPILOT CONTROL PLANE
              plan · confirm · execute · observe · record
                                  │
                     selects exact capsule + model
                                  │
                                  ▼
┌──────────────────────────────────────────────────────────────────┐
│                    RUNTIME CAPSULE                               │
│ exact Python · locked packages · runner · probes · manifest      │
│                                                                  │
│ stdin request ──▶ inference subprocess ──▶ stdout result envelope│
└──────────────────────────────────────────────────────────────────┘
                                  │
                         reads pinned snapshot
                                  │
                                  ▼
                    SHARED CONTENT-ADDRESSED CACHE
                  model weights · package archives · locks
```

The control plane communicates with a capsule through a versioned subprocess
protocol. It does not activate the environment, modify `PATH`, or rely on the
user's active shell.

## Capsule identity

A capsule is identified by the tuple:

```text
runtime id
runtime source and immutable version or commit
Python implementation and exact version
complete dependency lock digest
OS and architecture
accelerator backend
runner protocol version
```

The canonical capsule ID is a digest of a normalized identity document. A
human-readable prefix may be displayed, but it is not identity.

Example:

```text
mlx-lm/darwin-arm64/metal/python-3.11.11/sha256-f8a291…
```

Every measurement records `capsule_id` in addition to `runtime_id` and the
resolved model revision. Measurements from two different locks must never be
silently grouped as the same execution substrate.

## Runtime manifest

Runtime registry schema v2 describes how to construct and verify a capsule.
It does not claim that the capsule is already ready.

```yaml
schema: 2
id: mlx-lm
name: MLX-LM
serves: [text]
backends: [metal]

capsules:
  - id: darwin-arm64-stable
    platform:
      os: darwin
      arch: arm64
      backend: metal
    python:
      implementation: cpython
      version: "3.11.11"
    source:
      kind: pypi
      package: mlx-lm
      version: "0.31.4"
    lock:
      format: uv
      path: locks/mlx-lm/darwin-arm64.uv.lock
      sha256: "..."
    protocol: 1
    probes:
      import: spacepilot_runtime.probes:import_runtime
      accelerator: spacepilot_runtime.probes:probe_metal
      canary: spacepilot_runtime.probes:generate_canary
    supports:
      - model_family: qwen
        architectures: [qwen3_5]
        precisions: [4bit]
```

An unreleased upstream fix is represented explicitly:

```yaml
    channel: experimental
    source:
      kind: git
      repository: https://github.com/ml-explore/mlx-lm
      commit: ab1806e8f5d6...
```

An experimental capsule never becomes stable merely because its probes pass.
Promotion between channels is a registry decision with its own evidence.

## Locks and dependency resolution

Each capsule has a complete platform-specific lock containing:

- exact direct and transitive versions;
- artifact URLs and hashes;
- Python and platform markers;
- source commit and tree hash for Git dependencies;
- resolver version;
- generation timestamp and source manifest digest.

The lock is reviewed and committed. Runtime provisioning consumes it; it does
not resolve a new environment on the user's machine.

uv is the default Python capsule builder because it provides managed Python
installations, deterministic synchronization, artifact caching, and fast
environment creation. A runtime may use Conda or a native package manager when
required, but must produce the same identity, probe, and protocol records.

Broad constraints such as `transformers>=5` may be useful while generating a
candidate lock. They are never the installed capsule contract.

## Filesystem layout

```text
~/Library/Application Support/spacepilot/
  runtimes/
    mlx-lm/
      candidates/
        <capsule-id>/
      capsules/
        <capsule-id>/
          manifest.json
          uv.lock
          python/
          env/
          probes.json
      active -> capsules/<capsule-id>
      previous -> capsules/<capsule-id>
  registry/
  measurements/

~/.cache/spacepilot/
  packages/
  models/
```

Exact platform paths remain an implementation detail of `spacepilot.paths`.
The important boundary is that mutable runtime state lives outside the source
checkout and outside the pipx control-plane environment.

## Provisioning lifecycle

```text
absent
  │ provision
  ▼
resolving ──failure──▶ rejected
  ▼
materializing ───────▶ rejected
  ▼
import-verified ─────▶ rejected
  ▼
accelerator-verified ▶ rejected
  ▼
canary-flown ────────▶ rejected
  ▼
ready
  │ promote atomically
  ▼
active ──superseded──▶ retained ──policy──▶ collected
```

Provisioning performs these steps:

1. Resolve the manifest and validate its lock digest.
2. Confirm disk cost and any source-build or network implications.
3. Materialize into a new candidate directory.
4. Verify installed distributions against the lock.
5. Run the import probe in the capsule interpreter.
6. Run an accelerator allocation and synchronization probe.
7. Run a small, runtime-appropriate canary inference.
8. Write an immutable probe report.
9. Atomically move the candidate into `capsules/`.
10. Optionally promote it by replacing `active` while retaining `previous`.

Provisioning never runs `pip install` against the current SpacePilot, project,
pipx, or user-managed Conda environment.

## Readiness and compatibility

Readiness is evaluated for a route, not for a package in isolation:

```text
ship + capsule + model variant + bounded workload
```

A capsule can be ready for one architecture and unverified for another. A
model route is runnable only when all of the following hold:

- the capsule is active or explicitly selected;
- the last required probes succeeded and remain fresh;
- the capsule declares the model architecture and precision;
- the exact model snapshot is locally resolvable;
- current free memory and disk satisfy the route policy;
- requested knobs stay within the bounded route contract.

Initial architecture compatibility can be tested using a tiny model or
synthetic fixture. A large target model remains **unflown** until that exact
variant completes. SpacePilot must not convert a canary result into a claim
about the large model's peak memory or speed.

## Runner protocol

Protocol v1 uses newline-delimited JSON over stdin and stdout.

Request:

```json
{"protocol":1,"request_id":"...","operation":"generate","model_path":"...","prompt":"...","limits":{"max_output_tokens":256,"max_kv_tokens":4096}}
```

Result:

```json
{"protocol":1,"request_id":"...","status":"completed","artifact":"...","metrics":{"load_seconds":8.1,"generation_tokens":64,"generation_tokens_per_second":6.5,"peak_memory_bytes":18250000000}}
```

Prompts, credentials, and other user content never appear in argv. argv may
contain only the capsule runner entry point and non-sensitive protocol setup.
The child runs with network access disabled where the platform allows it and
with Hugging Face and Transformers offline modes enabled for local routes.

The parent accepts completion only when:

- the child exits zero;
- exactly one valid result envelope matches the request ID;
- all required metrics are finite and well-typed;
- the expected artifact is new, contained in the allowed output root, and
  non-empty;
- the reported model revision and capsule ID match the plan.

## CLI experience

```text
$ spacepilot runtimes list

STATE                 RUNTIME   CAPSULE        CHECKED       SERVES
ready                  mlx-lm    f8a291…         18s ago       text
candidate failed       mflux     90bf12…         2m ago        image, video
absent                  whisper   —               —             transcription
```

```text
$ spacepilot runtimes provision mlx-lm

MLX-LM · darwin-arm64 · experimental
  Python       CPython 3.11.11, managed by SpacePilot
  Source       ml-explore/mlx-lm@ab1806e8f5d6…
  Lock         sha256:f8a291… · 14 distributions
  Download     186 MB packages · on paper, checked 2026-08-27
  Existing     no environment will be modified
  Promotion    only after import, Metal and canary probes pass

Provision? [y/N]
```

Other required commands:

```text
spacepilot runtimes inspect mlx-lm
spacepilot runtimes verify mlx-lm
spacepilot runtimes candidates mlx-lm
spacepilot runtimes promote mlx-lm <capsule-id>
spacepilot runtimes rollback mlx-lm
spacepilot runtimes remove mlx-lm <capsule-id>
spacepilot runtimes gc --dry-run
```

Removing a capsule names its exact path and disk footprint before confirmation.
Package and model cache collection is a separate operation.

## Updates and the compatibility laboratory

Runtime updates are candidates, not upgrades.

An automated compatibility pipeline watches upstream package releases and
selected source branches. For every candidate it:

1. Generates locks for supported platform/Python combinations.
2. Builds capsules on representative ships or CI hardware.
3. Runs import and accelerator probes.
4. Runs architecture canaries.
5. Compares correctness, load time, throughput, and peak memory with the active
   capsule.
6. Publishes a signed candidate record to the registry.

Candidates with regressions are quarantined with their failure evidence. A
human or an explicit policy promotes a passing candidate. Stable users do not
receive an untested dependency resolution merely because PyPI published it.

The long-term compatibility corpus is keyed by capsule identity, device
identity, and model revision. It answers questions such as:

- Which MLX-LM lock last ran Qwen3.8 successfully on an M1 Max?
- Did Transformers 5.13 break import, tokenization, or generation?
- Does a new MLX release improve speed while increasing peak memory?
- Is a failure architecture-wide or specific to one model snapshot?

That corpus is product data, not CI exhaust.

## Security and supply chain

- Locks include hashes for downloaded artifacts.
- Git dependencies use immutable full commits and record repository identity.
- Capsule manifests and probe reports are immutable after promotion.
- Provisioning does not execute arbitrary model repository code by default.
- `trust_remote_code` is a separate, loud capability requiring confirmation.
- Secrets and prompts travel through stdin or protected files, never argv.
- Runtime subprocesses receive the minimum environment required for execution.
- A future signed-registry mechanism can authenticate promoted capsule recipes.
- An SBOM can be derived directly from each capsule lock.

## Failure semantics

The state shown to the user must identify the failing boundary:

- `resolution failed` — no lock could be produced;
- `materialization failed` — artifacts could not be installed or verified;
- `import failed` — the runtime package could not import;
- `accelerator unavailable` — the backend could not allocate and synchronize;
- `canary failed` — inference did not produce a valid result;
- `model not cached` — runtime is ready, exact weights are absent;
- `route unflown` — prerequisites pass, exact large model has not completed;
- `stale` — readiness evidence exceeded its freshness policy.

No failure falls forward to another interpreter, capsule, model revision, or
network download unless a new plan is shown and accepted.

## Migration from runtime schema v1

### Phase 1 — Establish the boundary

- Add capsule identity and protocol types.
- Add runtime-owned paths and atomic active/previous pointers.
- Make `run` services accept a resolved capsule executable explicitly.
- Move prompts and requests from argv to stdin.
- Keep schema v1 readable but label shared-interpreter routes `legacy`.

### Phase 2 — Provision one complete route

- Implement uv-based provisioning for Darwin arm64.
- Add the MLX-LM capsule and a small text canary.
- Provision a known-good experimental MLX-LM source pin if no fixed release is
  available.
- Run the bounded Qwen3.8 27B 4-bit experiment and record its exact capsule,
  model revision, peak memory, load time, and generation rate.

### Phase 3 — Migrate existing local runtimes

- Treat the existing isolated MFLUX environment as an imported capsule, then
  rebuild it from a lock.
- Move Kokoro and other in-process optional runtimes out of the control plane.
- Add native-binary capsule adapters for whisper.cpp and similar runtimes.
- Remove shared-interpreter installation after every supported route has a
  capsule path.

### Phase 4 — Compatibility laboratory

- Generate candidate locks automatically.
- Run hardware-backed canaries on supported ships.
- Publish candidate and quarantine evidence.
- Add promotion policies, rollback telemetry, and safe garbage collection.

## Acceptance criteria

The capsule foundation is complete when:

- installing or upgrading a runtime cannot change the SpacePilot environment;
- two conflicting runtime dependency graphs can run on the same ship;
- every execution record includes an exact capsule ID;
- deleting the active capsule and reprovisioning its lock produces the same
  package set;
- a broken candidate leaves the active runtime unchanged;
- rollback requires no dependency resolution or reinstall;
- `ready` requires import, accelerator, and canary evidence;
- the pipx interpreter and configured project interpreters are irrelevant to
  runtime execution;
- prompts and credentials never appear in process argv;
- the Qwen3.8 route can refuse, run, measure, and release memory without
  modifying `iogpu.wired_limit_mb` or any shared Python environment.

## Open decisions

1. Whether stable capsule locks ship inside the SpacePilot wheel or in a signed
   separately updated registry.
2. The freshness window for import, accelerator, and canary probes.
3. Which tiny models are legitimate architecture canaries without implying
   performance or memory equivalence to large variants.
4. Whether the first release supports only uv capsules or includes a generic
   native-binary capsule format immediately.
5. How much package-cache garbage collection can be automatic while keeping
   rollback reliable.
6. Which hardware configurations form the initial compatibility laboratory.

## Decision

SpacePilot will treat inference runtimes as immutable, independently verified
execution capsules. The control plane will not install ML dependencies into
itself or select a runtime by ambient interpreter state. Exact locks establish
what was built; probes and canary runs establish what is ready; full model runs
establish what has flown.
