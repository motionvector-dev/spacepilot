#!/bin/bash
# One-command remote setup script for LTX-2.5 on EC2 DLAMI (g6e.2xlarge / L40S)
set -euo pipefail

echo "==> [1/4] Preparing NVMe instance store..."
sudo mkdir -p /opt/dlami/nvme/hf /opt/dlami/nvme/out /opt/dlami/nvme/worker
sudo chown -R ubuntu:ubuntu /opt/dlami/nvme
sudo ln -sfn /opt/dlami/nvme /scratch

echo "==> [2/4] Installing PyTorch, Diffusers, and TorchAO dependencies..."
/opt/pytorch/bin/python -m pip install -q \
  "git+https://github.com/huggingface/diffusers@7564fb016dabda0c943416190fc92398c50b1b20" \
  "huggingface_hub[hf_transfer]>=1.23.0,<2.0" transformers==5.14.1 accelerate \
  safetensors sentencepiece protobuf av imageio imageio-ffmpeg Pillow numpy scipy \
  kernels torchao flask

echo "==> [3/4] Parallel downloading LTX-2.5 FP8 weights (78 GB)..."
HF_HOME=/scratch/hf HF_ENABLE_PARALLEL_LOADING=YES /opt/pytorch/bin/python - <<'PY'
import os
from huggingface_hub import snapshot_download
token = os.environ.get("HF_TOKEN", True)
print("Downloading snapshot...")
snapshot_download(
    "Lightricks/LTX-2.5-Diffusers",
    ignore_patterns=["transformer_full/*", "*distilled-lora*", "transformer/*-of-00008.safetensors"],
    token=token,
    max_workers=16
)
print("Download complete!")
PY

echo "==> [4/4] Starting LTX-2.5 resident Flask worker on port 5000..."
cd /scratch/worker
nohup /opt/pytorch/bin/python ltx_worker.py > /scratch/worker/worker.log 2>&1 &

echo "==> LTX Worker launched! Monitor logs with: tail -f /scratch/worker/worker.log"
echo "==> Waiting for /health check..."
sleep 5
curl -s http://localhost:5000/health || true
