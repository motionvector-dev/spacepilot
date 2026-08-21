#!/bin/bash
# Hardened remote setup and worker orchestrator for LTX-2.5 on EC2 DLAMI (L40S / A100)
set -euo pipefail

echo "=========================================================================="
echo "  PLUTO LTX-2.5 HARDENED WORKER SETUP"
echo "=========================================================================="

# ─────────────────────────────────────────────────────────────────────────────
# [1/5] Preflight: Environment & NVMe Storage Discovery
# ─────────────────────────────────────────────────────────────────────────────
echo "==> [1/5] Discovering NVMe storage & verifying host resources..."

# 1.1 Verify LOCAL_WORKER_TOKEN
if [ -z "${LOCAL_WORKER_TOKEN:-}" ]; then
  echo "ERROR: LOCAL_WORKER_TOKEN is not set; the worker refuses to run unauthenticated." >&2
  exit 1
fi

# 1.2 Verify HF_TOKEN
if [ -z "${HF_TOKEN:-}" ]; then
  echo "WARNING: HF_TOKEN is not set; downloading gated model Lightricks/LTX-2.5-Diffusers may fail with 401." >&2
fi

# 1.3 Detect best scratch storage (NVMe ephemeral vs root)
SCRATCH_BASE=""
if [ -d "/opt/dlami/nvme" ] && [ -w "/opt/dlami/nvme" ]; then
  SCRATCH_BASE="/opt/dlami/nvme"
elif [ -d "/mnt" ] && [ -w "/mnt" ]; then
  SCRATCH_BASE="/mnt"
else
  # Fallback to local /scratch directory
  sudo mkdir -p /scratch
  sudo chown -R ubuntu:ubuntu /scratch
  SCRATCH_BASE="/scratch"
fi

echo "  Target Scratch Disk : $SCRATCH_BASE"

# Ensure target subdirectories exist
sudo mkdir -p "$SCRATCH_BASE/hf" "$SCRATCH_BASE/out" "$SCRATCH_BASE/worker" "$SCRATCH_BASE/tmp"
sudo chown -R ubuntu:ubuntu "$SCRATCH_BASE"
sudo ln -sfn "$SCRATCH_BASE" /scratch

# Check available disk space (require >= 80 GB)
AVAILABLE_GB=$(df -BG /scratch | awk 'NR==2 {print $4}' | tr -d 'G')
echo "  Available Disk      : ${AVAILABLE_GB} GB on /scratch"
if [ "$AVAILABLE_GB" -lt 80 ]; then
  echo "ERROR: Insufficient disk space (${AVAILABLE_GB} GB available, need >= 80 GB). Aborting." >&2
  df -h
  exit 1
fi

# 1.4 Ensure 32GB high-speed swapfile exists to safely buffer peak shard loading (30.5GB RSS)
CURRENT_SWAP_GB=$(free -g | awk '/^Swap:/ {print $2}')
if [ "$CURRENT_SWAP_GB" -lt 16 ]; then
  echo "  Configuring 32GB swapfile for safe shard buffering..."
  if [ ! -f /swapfile ]; then
    sudo fallocate -l 32G /swapfile || sudo dd if=/dev/zero of=/swapfile bs=1M count=32768
    sudo chmod 600 /swapfile
    sudo mkswap /swapfile
  fi
  sudo swapon /swapfile 2>/dev/null || true
  # Tune swappiness for optimal burst buffering
  sudo sysctl vm.swappiness=60 >/dev/null 2>&1 || true
fi

# 1.5 Check Total Virtual Memory (RAM + Swap)
TOTAL_RAM_GB=$(free -g | awk '/^Mem:/ {print $2}')
TOTAL_SWAP_GB=$(free -g | awk '/^Swap:/ {print $2}')
TOTAL_VIRT_GB=$((TOTAL_RAM_GB + TOTAL_SWAP_GB))
echo "  Host System Memory  : ${TOTAL_RAM_GB} GB RAM + ${TOTAL_SWAP_GB} GB Swap (${TOTAL_VIRT_GB} GB Total)"
if [ "$TOTAL_VIRT_GB" -lt 40 ]; then
  echo "ERROR: Total virtual memory is only ${TOTAL_VIRT_GB} GB. Loading LTX-2.5 requires >= 48 GB virtual memory headroom. Aborting." >&2
  exit 1
fi

# ─────────────────────────────────────────────────────────────────────────────
# [2/5] Installing Dependencies (Diffusers Main, TorchAO, hf_transfer)
# ─────────────────────────────────────────────────────────────────────────────
echo "==> [2/5] Installing and verifying PyTorch, Diffusers, and TorchAO dependencies..."

/opt/pytorch/bin/python -m pip install -q --upgrade \
  torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128

/opt/pytorch/bin/python -m pip install -q --upgrade \
  "git+https://github.com/huggingface/diffusers.git" \
  "torchao>=0.8.0" \
  hf_transfer \
  "huggingface_hub>=0.28.0" \
  "transformers>=4.48.0" \
  accelerate \
  safetensors sentencepiece protobuf av imageio imageio-ffmpeg Pillow numpy scipy \
  kernels flask 2>&1 | tail -5

# Ensure ScalingType compatibility if needed
/opt/pytorch/bin/python -c "
import torch, diffusers, torchao
print(f'  PyTorch   : {torch.__version__} (CUDA: {torch.cuda.is_available()})')
print(f'  Diffusers : {diffusers.__version__}')
print(f'  TorchAO   : {torchao.__version__}')
if torch.cuda.is_available():
    print(f'  GPU Name  : {torch.cuda.get_device_name(0)}')
"

# ─────────────────────────────────────────────────────────────────────────────
# [3/5] Parallel Downloading LTX-2.5 FP8 Weights (~78 GB)
# ─────────────────────────────────────────────────────────────────────────────
echo "==> [3/5] Fast downloading LTX-2.5 FP8 weights (via Rust hf_transfer)..."

HF_HOME=/scratch/hf \
TMPDIR=/scratch/tmp \
HF_HUB_ENABLE_HF_TRANSFER=1 \
HF_TOKEN="${HF_TOKEN:-}" \
/opt/pytorch/bin/python - <<'PY'
import os
from huggingface_hub import snapshot_download

token = os.environ.get("HF_TOKEN") or None
print("  Initiating fast snapshot download for Lightricks/LTX-2.5-Diffusers...")
snapshot_download(
    "Lightricks/LTX-2.5-Diffusers",
    ignore_patterns=["transformer_full/*", "*distilled-lora*", "transformer/*-of-00008.safetensors"],
    token=token,
    max_workers=16
)
print("  ✅ Download completed successfully!")
PY

# ─────────────────────────────────────────────────────────────────────────────
# [4/5] Single Worker Guarantee & Startup
# ─────────────────────────────────────────────────────────────────────────────
echo "==> [4/5] Launching resident LTX worker process..."

# Terminate any previously running worker instances
if pgrep -f "ltx_worker.py" > /dev/null; then
  echo "  Stopping existing worker process..."
  pkill -f "ltx_worker.py" || true
  sleep 2
fi

cd /scratch/worker
PID_FILE="/scratch/worker/worker.pid"
LOG_FILE="/scratch/worker/worker.log"

export PYTHONUNBUFFERED=1
export HF_HOME=/scratch/hf
export TMPDIR=/scratch/tmp
export LOCAL_WORKER_TOKEN="$LOCAL_WORKER_TOKEN"
export HF_TOKEN="${HF_TOKEN:-}"

nohup /opt/pytorch/bin/python ltx_worker.py > "$LOG_FILE" 2>&1 &
WORKER_PID=$!
echo "$WORKER_PID" > "$PID_FILE"
echo "  Worker started with PID: $WORKER_PID (logging to $LOG_FILE)"

# ─────────────────────────────────────────────────────────────────────────────
# [5/5] Warmup Health Polling & Failure Detection
# ─────────────────────────────────────────────────────────────────────────────
echo "==> [5/5] Monitoring initial warmup health (takes ~120-180s)..."

for i in $(seq 1 30); do
  sleep 6
  # Check if PID is still alive
  if ! kill -0 "$WORKER_PID" 2>/dev/null; then
    echo "❌ ERROR: Worker process $WORKER_PID died unexpectedly during warmup!" >&2
    echo "─── Last 30 lines of worker log ───"
    tail -n 30 "$LOG_FILE" || true
    echo "─── Kernel OOM / dmesg diagnostics ───"
    dmesg | tail -n 20 || true
    exit 1
  fi

  # Check /health endpoint
  HEALTH_HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:5000/health || echo "000")
  if [ "$HEALTH_HTTP_CODE" = "200" ]; then
    echo "  ✅ LTX-2.5 Worker is fully warm and resident in VRAM (HTTP 200)!"
    curl -s http://localhost:5000/health
    echo ""
    exit 0
  elif [ "$HEALTH_HTTP_CODE" = "503" ]; then
    echo "  [Warmup in progress] Shards loading into VRAM... ($((i*6))s elapsed)"
  else
    echo "  [Server initializing] Port 5000 status: $HEALTH_HTTP_CODE... ($((i*6))s elapsed)"
  fi
done

echo "  Worker is still loading in background. Monitor progress with: tail -f /scratch/worker/worker.log"

