#!/usr/bin/env bash
# Build llama-bench with HIP for gfx1150 inside a ROCm container.
#
# The container must have the source tree mounted at /LLM and this repository
# at /repo. The build directory is named by the caller so a ROCm 10 build can
# sit next to the archived ROCm 10.0.0 build.
#
# Usage:
#   rocm-build.sh /LLM/llama.cpp-managed /LLM/llama.cpp-managed/build-rocm10
set -euo pipefail

SRC="${1:?source dir}"
BUILD="${2:?build dir}"

export ROCM_PATH=/opt/rocm
export HIP_PATH=/opt/rocm
export PATH="/opt/rocm/bin:${PATH}"

cmake -S "$SRC" -B "$BUILD" \
  -DCMAKE_BUILD_TYPE=Release \
  -DGGML_HIP=ON \
  -DGGML_VULKAN=OFF \
  -DGGML_CUDA=OFF \
  -DAMDGPU_TARGETS=gfx1150 \
  -DCMAKE_HIP_COMPILER=/opt/rocm/lib/llvm/bin/clang++ \
  -DLLAMA_BUILD_TESTS=OFF \
  -DLLAMA_BUILD_EXAMPLES=OFF \
  -DLLAMA_BUILD_SERVER=OFF

cmake --build "$BUILD" -j "${JOBS:-20}" --target llama-bench

"$BUILD/bin/llama-bench" --version
