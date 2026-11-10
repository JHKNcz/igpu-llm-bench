#!/usr/bin/env bash
# Entrypoint for running llama.cpp binaries inside the archived ROCm container.
#
# The archived measurements used the image
#   rocm/dev-ubuntu-24.04:latest  (HIP 7.15.26333-0000000)
# at the 0.5 GB carve-out, with HIP unified memory enabled so a model larger
# than the GTT aperture can still load.
#
# Usage (the container is started with this script as its entrypoint):
#   rocm-entry.sh /LLM/llama.cpp-managed/build-rocm/bin/llama-bench -m ... -ngl 999
set -euo pipefail

export ROCM_PATH=/opt/rocm
export HIP_PATH=/opt/rocm
export PATH="/opt/rocm/bin:${PATH}"
export LD_LIBRARY_PATH="/opt/rocm/lib:/opt/rocm/lib64:$(dirname "${1:-/opt/rocm/bin/false}"):${LD_LIBRARY_PATH:-}"
export GGML_CUDA_ENABLE_UNIFIED_MEMORY="${GGML_CUDA_ENABLE_UNIFIED_MEMORY:-1}"
export GGML_CUDA_DISABLE_GRAPHS="${GGML_CUDA_DISABLE_GRAPHS:-0}"

exec "$@"
