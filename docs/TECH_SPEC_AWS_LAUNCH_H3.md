# Technical Specification: SpacePilot AWS Launch & MiniMax-H3 Registry Integration

## 1. Objective
Enable end-to-end interactive model selection, GPU tier recommendation, deployment, lifecycle management, and clip generation for `minimax-h3` on AWS within SpacePilot.

## 2. Architecture & Components

+-- spacepilot/
    +-- registry/models/
    |   +-- minimax-h3.yaml           (Schema 1 model entry with fp8, bf16-offload, and bf16-tp4 variants)
    +-- services/
    |   +-- aws_fleet_launcher.py     (AWS EC2 Spot/On-Demand provisioning, quota enforcement, DLAMI bootstrap)
    |   +-- gpu_recommender.py        (Placement logic matching model working set to AWS G/VT GPU instances)
    +-- cli.py                        (Interactive `spacepilot launch` CLI workflow and user preference persistence)
    +-- tests/
        +-- test_minimax_h3_registry.py
        +-- test_aws_gpu_recommender.py
        +-- test_aws_fleet_launcher.py
        +-- test_cli_launch_workflow.py

## 3. Specification Details

### 3.1 Model Registry (`minimax-h3.yaml`)
- Schema: 1
- Family: `minimax`
- Kind: `video`
- Variants:
  1. `minimax-h3-fl2va-fp8`: ~32GB working set. Recommended: `g6e.4xlarge`, `g6e.8xlarge` (1x L40S 48GB, 50 layers resident).
  2. `minimax-h3-fl2va-bf16-offload`: ~44GB VRAM + 128GB host RAM. Recommended: `g6e.8xlarge` (24 resident layers).
  3. `minimax-h3-fl2va-bf16-tp4`: ~64GB aggregate VRAM. Recommended: `g6e.12xlarge` (4x L40S 192GB, TP=4, zero offload).

### 3.2 GPU Recommender Engine (`spacepilot/services/gpu_recommender.py`)
- Given model `working_set_bytes` and required precision (`fp8`, `bf16`), filters candidate AWS instance types (`g6e.*`, `g5.*`, `g6.*`).
- Evaluates against active account quota (64 vCPUs for `L-DB2E81BA`).
- Ranks candidate instances by:
  - Latency / resident layer capability (L40S > A10G > L4).
  - Spot price vs On-Demand price ratio.
  - VRAM headroom and host RAM pinning capacity.

### 3.3 Interactive CLI Launch Flow (`spacepilot/cli.py` -> `cmd_launch`)
- Prompt 1: Model Selection (searchable or list, filtered by kind `video`).
- Prompt 2: GPU Recommendation display:
  - Shows top 3 GPU candidates with live Spot price, generation speed estimate (s/step), and VRAM margin.
  - Option to customize or select recommended GPU.
- Prompt 3: Preference persistence: "Save this GPU choice as default for `minimax-h3`? (y/n)".
  - Persists to `~/.spacepilot_config.json` under `model_defaults.minimax-h3`.
- Execution:
  - Requests EC2 Spot/On-Demand instance with DLAMI.
  - Bootstraps via `h3-video-pipeline/scripts/up-dlami.sh`.
  - Attaches to status watcher, outputs SSH command and tunnel instructions.

## 4. Subagent Delegation Plan (TDD)
1. **Subagent 1 (Registry)**: Implement and validate `spacepilot/registry/models/minimax-h3.yaml` + schema tests.
2. **Subagent 2 (Recommender)**: Write unit tests and implementation for `gpu_recommender.py` matching working set to AWS offerings.
3. **Subagent 3 (AWS Provisioner)**: Write unit tests and implementation for `aws_fleet_launcher.py` with dry-run mocking.
4. **Subagent 4 (Config & Defaults)**: Write tests and implementation for user default GPU persistence in `~/.spacepilot_config.json`.
5. **Subagent 5 (CLI Orchestration & End-to-End)**: Wire `cmd_launch` in `spacepilot/cli.py` with mockable interactive prompts and verification tests.
