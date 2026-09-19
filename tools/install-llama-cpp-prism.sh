#!/bin/sh
# Pinned build for spacepilot's `llama-cpp-prism` runtime recipe.
#
#   PrismML-Eng/llama.cpp @ d8f26eec76da6d09bb708bcba51ef64b8cd868a3
#   (branch `prism`, that branch's own default, checked 2026-09-10)
#
# Ternary Bonsai 8B's GGUF Q2_0 g128 quantization is not readable by mainline
# llama.cpp -- the model card is explicit: "Q2_0 is not yet in mainline
# llama.cpp. Use our fork at PrismML-Eng/llama.cpp (prism branch, default)
# which adds Q2_0 support for CPU (NEON/generic) and Metal." Like bitnet-cpp,
# this is a source-tree CMake build, not a pip package -- llama-cpp-python's
# wheel vendors mainline llama.cpp, not this fork, so pointing pip at it
# would not add Q2_0 support. POSIX sh so it can be curl-piped the same way
# desert-ant's install.sh is.
#
# NOT RUN as part of registering the recipe this script backs -- see
# spacepilot/registry/runtimes/llama-cpp-prism.yaml's notes. A default
# llama.cpp CMake configure enables the Metal backend on Apple Silicon,
# which is a full build of GGML plus every backend it detects, not a small
# or quick one -- recorded here rather than run on a MacBook.

set -eu

PRISM_COMMIT="d8f26eec76da6d09bb708bcba51ef64b8cd868a3"
PRISM_DIR="${LLAMA_CPP_PRISM_DIR:-$HOME/.local/share/spacepilot/llama-cpp-prism}"

git clone https://github.com/PrismML-Eng/llama.cpp.git "$PRISM_DIR"
cd "$PRISM_DIR"
git checkout "$PRISM_COMMIT"

cmake -B build -DCMAKE_BUILD_TYPE=Release -DLLAMA_BUILD_TOOLS=ON -DLLAMA_BUILD_SERVER=ON
cmake --build build --config Release

mkdir -p "$HOME/.local/bin"
ln -sf "$PRISM_DIR/build/bin/llama-cli" "$HOME/.local/bin/llama-cli-prism"
