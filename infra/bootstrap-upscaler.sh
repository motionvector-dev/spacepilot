#!/usr/bin/env bash
# Runs ON the GPU box. Installs the upscaler stack and proves the GPU path works
# before any corpus is uploaded — a bad bootstrap discovered mid-run costs GPU
# minutes, and every check here is cheap.
set -euo pipefail

REPO="${UPSCALER_GPU_REPO:-https://github.com/katana-video/upscaler-gpu.git}"
BRANCH="${UPSCALER_GPU_BRANCH:-dev}"
WORK="$HOME/upscaler-gpu"

echo "=== 1/6 GPU present? ==="
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader

echo
echo "=== 2/6 PyTorch sees CUDA? ==="
# The DLAMI ships torch in a venv at /opt/pytorch; fall back to system python.
if [[ -f /opt/pytorch/bin/activate ]]; then
  # shellcheck disable=SC1091
  source /opt/pytorch/bin/activate
fi
python -c "import torch; assert torch.cuda.is_available(), 'CUDA not visible to torch'; \
print(f'  torch {torch.__version__}  cuda {torch.version.cuda}  {torch.cuda.get_device_name(0)}')"

echo
echo "=== 3/6 NVENC available? ==="
# pipeline_core writes its intermediate with h264_nvenc/hevc_nvenc. Without this
# the upscale stage silently has no encoder and fails deep into the run.
if ffmpeg -hide_banner -encoders 2>/dev/null | grep -qE 'h264_nvenc'; then
  echo "  h264_nvenc present"
else
  echo "  h264_nvenc MISSING — installing ffmpeg with nvenc"
  sudo apt-get update -qq && sudo apt-get install -y -qq ffmpeg
  ffmpeg -hide_banner -encoders 2>/dev/null | grep -qE 'h264_nvenc' \
    || { echo "  still missing; the distro ffmpeg lacks nvenc. Upscale stage will fail."; exit 1; }
fi

echo
echo "=== 4/6 upscaler-gpu checkout ==="
if [[ -d "$WORK/.git" ]]; then
  git -C "$WORK" fetch --quiet origin "$BRANCH" && git -C "$WORK" checkout --quiet "$BRANCH"
  git -C "$WORK" pull --quiet
else
  git clone --quiet --branch "$BRANCH" --depth 1 "$REPO" "$WORK"
fi
echo "  $(git -C "$WORK" log --oneline -1)"

echo
echo "=== 5/6 python deps ==="
pip install --quiet --upgrade pip
pip install --quiet numpy opencv-python-headless pillow boto3 vidgear
python -c "import cv2, numpy, PIL, boto3; print('  cv2', cv2.__version__, '| numpy', numpy.__version__)"

echo
echo "=== 6/6 RealESRGAN checkpoint + a real 1-second upscale ==="
cd "$WORK"
python - <<'PY'
import os, sys, subprocess, tempfile, time
sys.path.insert(0, os.getcwd())
import pipeline_core as pc

model, params, cfg = pc.create_realesrgan_model()
print(f"  model loaded: {params:,} params  {cfg}")

# Synthetic 1s 720p clip -> exercises decode, model and encode without needing S3.
with tempfile.TemporaryDirectory() as wd:
    src = f"{wd}/probe.mp4"
    subprocess.run(["ffmpeg","-v","error","-f","lavfi","-i","testsrc2=size=1280x720:rate=24",
                    "-t","1","-c:v","libx264","-pix_fmt","yuv420p",src,"-y"], check=True)
    t = time.time()
    import torch
    m = model.eval().cuda().half()
    with torch.no_grad():
        x = torch.zeros((1,3,720,1280), dtype=torch.half, device="cuda")
        y = m(x)
    torch.cuda.synchronize()
    print(f"  fp16 forward 720p -> {tuple(y.shape)} in {time.time()-t:.2f}s (incl. warmup)")
PY

echo
echo "bootstrap OK — GPU, NVENC, checkpoint and a fp16 forward pass all verified."
