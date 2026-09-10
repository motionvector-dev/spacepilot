#!/bin/sh
# Pinned build for spacepilot's `bitnet-cpp` runtime recipe.
#
#   microsoft/BitNet @ 0b341e582afbf9e1011f24744b554c96a3477eb5
#   (main, checked 2026-09-10)
#
# There is no PyPI wheel and no upstream install.sh for bitnet.cpp -- the
# repo ships as a source tree with no setup.py/pyproject.toml, built with
# CMake, the same shape as llama.cpp itself. This script is spacepilot's own
# recording of the real upstream sequence (README.md "Build from source" at
# the pinned commit), POSIX sh so it can be curl-piped the same way
# desert-ant's install.sh is.
#
# NOT RUN as part of registering the recipe this script backs -- see
# spacepilot/registry/runtimes/bitnet-cpp.yaml's notes. setup_env.py's
# compile() step always runs a full CMake build of the bundled
# 3rdparty/llama.cpp fork (-DLLAMA_BUILD_TOOLS=ON -DLLAMA_BUILD_EXAMPLES=ON
# -DLLAMA_BUILD_COMMON=ON -DLLAMA_BUILD_SERVER=ON), unconditionally, with no
# flag to skip it even when a GGUF already exists -- not a small or quick
# build, so it was recorded here rather than run on a MacBook.

set -eu

BITNET_COMMIT="0b341e582afbf9e1011f24744b554c96a3477eb5"
BITNET_DIR="${BITNET_CPP_DIR:-$HOME/.local/share/spacepilot/bitnet-cpp}"
GGUF_DIR="${1:?usage: install-bitnet-cpp.sh <dir-containing-ggml-model-i2_s.gguf>}"

git clone --recursive https://github.com/microsoft/BitNet.git "$BITNET_DIR"
cd "$BITNET_DIR"
git checkout "$BITNET_COMMIT"
git submodule update --init --recursive

python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt

# setup_env.py always builds (see this script's header). --model-dir points
# at a GGUF spacepilot's own model registry already downloaded, so
# setup_env.py's own download/convert path no-ops ("GGUF model already
# exists") and only the CMake build actually runs.
python setup_env.py --model-dir "$GGUF_DIR" -q i2_s

mkdir -p "$HOME/.local/bin"
ln -sf "$BITNET_DIR/build/bin/llama-cli" "$HOME/.local/bin/bitnet-cli"
