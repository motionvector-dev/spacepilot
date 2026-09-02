# Technical Specification: Distributed Apple Silicon Inference & Training via Thunderbolt 5 RDMA & JACCL

- **Document ID**: `SP-DESIGN-042`
- **Target Path**: `docs/design/macos-distributed-inference-and-training-with-mlx.md`
- **Status**: `PROPOSED / IMPLEMENTATION-READY`
- **Author**: Saurabh Nandwana (SpacePilot Architect)
- **Reference**: Apple WWDC26 Session 233 (*Explore distributed inference and training with MLX*, Tatiana Likhomanenko)

---

## 1. Executive Summary

As frontier foundation models expand beyond single-node unified memory boundaries (e.g., 1-trillion parameter MoE models requiring ~1TB VRAM, or multi-stream video diffusion models like Wan 2.1 14B), single-device Apple Silicon becomes memory and bandwidth constrained. 

Starting in **macOS 26.2**, Apple introduced kernel-level **Remote Direct Memory Access (RDMA) over Thunderbolt 5**, coupled with **JACCL** (*Joint Apple Collective Communication Library*). This specification defines how **SpacePilot** and its **SpaceBar** macOS companion orchestrate distributed, desk-scale Apple Silicon clusters over Thunderbolt 5 mesh interconnects for multi-device inference and local fine-tuning.

```
┌───────────────────────────────────────────────────────────────────────────────────┐
│                        SPACEPILOT DISTRIBUTED MLX STACK                           │
├───────────────────────────────────────────────────────────────────────────────────┤
│  Layer 4: Application   │ SpaceBar HUD / Web Cockpit / SpacePilot Agentic MCP Server   │
│  Layer 3: Framework     │ MLX & MLX LM (Tensor Parallelism / Data Parallelism)   │
│  Layer 2: Collective    │ JACCL (Mesh & Ring Auto-Routing, Metal Fast Synch)      │
│  Layer 1: Transport     │ RDMA over Thunderbolt 5 (Bi-directional 80-120 Gbps)    │
│  Layer 0: Physical      │ Thunderbolt 5 Interconnect (4x M-Series Studio / Max)  │
└───────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Hardware Topology & Transport Architecture

### 2.1 Physical Interconnects & Topologies
SpacePilot supports two physical cluster topologies managed via `spacepilot.daemon.fleet`:

1. **Full Mesh Topology (Latency-Optimized)**:
   * Every node is directly cabled to every other node via Thunderbolt 5.
   * **Best For**: **Tensor Parallelism** (splits model layers by width; requires frequent, all-to-all token communication at every layer boundary).
   * Single-hop latency: `< 1.2 µs`.

2. **Aggregated Multi-Cable Ring Topology (Bandwidth-Optimized)**:
   * Nodes connect only to two immediate neighbors, using dual or triple Thunderbolt 5 cables per link (aggregating up to 240 Gbps bi-directional link bandwidth).
   * **Best For**: **Data Parallelism & LoRA Fine-Tuning** (gradient accumulation ring-allreduce) and **Pipeline Parallelism**.

```
   FULL MESH (Tensor Parallel)             AGGREGATED RING (Data Parallel)
       [ Node 1 ] ──────── [ Node 2 ]               [ Node 1 ] ═══════ [ Node 2 ]
          │   \          /   │                         ║                   ║
          │     \      /     │                         ║ (Dual TB5 Cables) ║
          │       \  /       │                         ║                   ║
       [ Node 4 ] ──────── [ Node 3 ]               [ Node 4 ] ═══════ [ Node 3 ]
```

### 2.2 RDMA Protocol & Zero-Copy Memory Semantics
* **Bypasses CPU & OS Kernel**: RDMA allows Node A’s GPU to read/write directly into Node B’s Unified Memory over PCIe/Thunderbolt DMA without intermediate socket buffer copying.
* **Environment Configuration**:
  ```bash
  export MLX_METAL_FAST_SYNCH=1
  export JACCL_COMM_BACKEND=jaccl # auto-selects mesh vs ring
  ```
  `MLX_METAL_FAST_SYNCH=1` enables sub-microsecond GPU-to-CPU synchronization barriers, critical since computation executes on the Metal GPU while RDMA orchestration runs on the host CPU.

---

## 3. Sharding Strategies & Parallelism Modes

SpacePilot maps model architectures to distributed runtimes according to the following matrix:

| Parallelism Mode | Sharding Dimension | Communication Pattern | Target Workload | SpacePilot Engine |
| :--- | :--- | :--- | :--- | :--- |
| **Tensor Parallelism** (Default) | Width (Weights per layer) | All-Reduce every layer / token | Interactive Chat / Video Denoising | `spacepilot.engines.wan_engine` / `mflux` |
| **Pipeline Parallelism** | Depth (Sequential layer groups) | Point-to-Point activations | Massive MoE Models (>500B params) | `spacepilot.drivers.gguf_driver` |
| **Data Parallelism** | Batch (Replicated model weights)| Ring All-Reduce gradients | Local LoRA / Adapter Training | `spacepilot.services.lora` |

### 3.1 Trillion-Parameter Memory Sizing Formula
To host a model across $N$ cluster nodes:

$$\text{VRAM}_{\text{node}} = \frac{\text{Params} \times \text{BytesPerParam}}{N} + \text{KV\_Cache}_{\text{node}} + \text{Activation\_Buffer}$$

*Example*: **Kimi 2.6 (1 Trillion Parameters, 8-bit quantized = ~1,000 GB weights)**:
* Across 4× Mac Studio M3 Ultra (512 GB Unified RAM each = 2,048 GB total cluster memory):
  * **Memory per node**: $250\text{ GB (Weights)} + 32\text{ GB (KV Cache)} + 16\text{ GB (Workspace)} = 298\text{ GB}$.
  * **Headroom**: $>214\text{ GB}$ free per node for host OS and display.

---

## 4. SpacePilot Daemon & CLI Integration

### 4.1 Automated Cluster Discovery & Setup
SpacePilot extends `spacepilot/daemon/fleet.py` with the `spacepilot cluster` CLI:

```bash
# 1. Probe Thunderbolt 5 topology and auto-configure RDMA interfaces
spacepilot cluster init --auto-setup --backend jaccl --output ~/.spacepilot/cluster.json

# 2. Inspect active cluster health and peer bandwidth
spacepilot cluster status

# 3. Launch distributed video diffusion across the desk cluster
spacepilot run --cluster ~/.spacepilot/cluster.json --model wan-2.1-14b --prompt "Cinematic hyper-lapse"
```

### 4.2 Machine-Readable Cluster Configuration Schema (`cluster.json`)
```json
{
  "version": "2026.2",
  "cluster_id": "sp-cluster-studio-quad",
  "backend": "jaccl",
  "nodes": [
    {
      "hostname": "studio-m3-01.local",
      "ssh_user": "saurabh",
      "ip": "192.168.1.101",
      "chip": "Apple M3 Ultra",
      "unified_ram_gb": 512,
      "rdma_devices": ["tb5-link-0", "tb5-link-1"]
    },
    {
      "hostname": "studio-m3-02.local",
      "ssh_user": "saurabh",
      "ip": "192.168.1.102",
      "chip": "Apple M3 Ultra",
      "unified_ram_gb": 512,
      "rdma_devices": ["tb5-link-0", "tb5-link-2"]
    }
  ],
  "env": {
    "MLX_METAL_FAST_SYNCH": "1",
    "JACCL_ENABLE_RDMA": "1"
  }
}
```

---

## 5. SpaceBar Studio & Popover HUD Telemetry Specs

In SpaceBar (`spacebar-artboard.html`), the **Fleet Nodes** tab exposes real-time distributed cluster telemetry:

```
┌───────────────────────────────────────────────────────────────────────────────────┐
│ 🍏 CLUSTER TOPOLOGY: 4-NODE M3 ULTRA MESH (2.0 TB UNIFIED MEMORY)                 │
├───────────────────────────────────────────────────────────────────────────────────┤
│ • Node 01 (Master): 🟢 48°C · TB5 Mesh Active · VRAM: 248/512 GB · 45.2 FPS       │
│ • Node 02 (Worker): 🟢 47°C · TB5 Mesh Active · VRAM: 248/512 GB · 45.2 FPS       │
│ • Node 03 (Worker): 🟢 49°C · TB5 Mesh Active · VRAM: 248/512 GB · 45.2 FPS       │
│ • Node 04 (Worker): 🟢 48°C · TB5 Mesh Active · VRAM: 248/512 GB · 45.2 FPS       │
├───────────────────────────────────────────────────────────────────────────────────┤
│ Interconnect Bandwidth: 118.4 GB/s bi-directional · Link Latency: 1.1 µs          │
│ Active Shard: Kimi 2.6 (1 Trillion Params) / Wan 2.1 14B Video Pipeline           │
└───────────────────────────────────────────────────────────────────────────────────┘
```

---

## 6. Implementation Roadmap

1. **Milestone 1 (`v0.8.0`)**: Implement `spacepilot cluster probe` with Thunderbolt IOKit device enumeration.
2. **Milestone 2 (`v0.8.5`)**: Add JACCL collective communication bindings in `spacepilot.substrate`.
3. **Milestone 3 (`v0.9.0`)**: Integrate distributed tensor parallel sharding for Wan 2.1 and FLUX into `spacepilot.engines.wan_engine`.
4. **Milestone 4 (`v1.0.0`)**: Ship SpaceBar native macOS cluster HUD and 1-click distributed launch in `spacebar.app`.
