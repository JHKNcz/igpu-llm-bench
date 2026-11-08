#!/usr/bin/env bash
# Reproducible llama-bench wrapper for the archived iGPU measurements.
#
# The archived logs used ngl=999, flash attention on, tg128, and two measured
# repetitions after llama-bench's automatic warmup. The original CLI was not
# recorded; this wrapper makes those settings explicit and records the exact
# command, binary hash, model hash, and host metadata next to the output.
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: scripts/bench.sh [options]

Required environment (or flags):
  LLAMA_BENCH   path to llama-bench          (or --llama-bench)
  MODEL         path to the GGUF model       (or --model)

Options:
  --backend vulkan|rocm   label for the output file (default: vulkan)
  --depths LIST           comma-separated depths (default: 0,16384,65536)
  --reps N                measured repetitions per depth (default: 2)
  --ngl N                 GPU layers (default: 999)
  --threads N             CPU threads (default: 12)
  --batch N               batch size (default: 2048)
  --ubatch N              micro-batch size (default: 512)
  --out-dir DIR           output directory (default: runs)
  --llama-cpp DIR         llama.cpp checkout for the commit hash (optional)
  --dry-run               print commands, do not run
  -h, --help              show this help

Example:
  LLAMA_BENCH=$HOME/llama.cpp/build-vulkan/bin/llama-bench \
  MODEL=$HOME/models/Qwen3.6-35B-A3B-UD-IQ4_NL.gguf \
  scripts/bench.sh --backend vulkan
EOF
}

LLAMA_BENCH="${LLAMA_BENCH:-}"
MODEL="${MODEL:-}"
BACKEND="${BACKEND:-vulkan}"
DEPTHS="${DEPTHS:-0,16384,65536}"
REPS="${REPS:-2}"
NGLOBAL="${NGLOBAL:-999}"
THREADS="${THREADS:-12}"
BATCH="${BATCH:-2048}"
UBATCH="${UBATCH:-512}"
OUT_DIR="${OUT_DIR:-runs}"
LLAMA_CPP="${LLAMA_CPP:-}"
DRY_RUN=0

while (($# > 0)); do
  case "$1" in
    --backend) BACKEND="$2"; shift 2 ;;
    --model) MODEL="$2"; shift 2 ;;
    --llama-bench) LLAMA_BENCH="$2"; shift 2 ;;
    --depths) DEPTHS="$2"; shift 2 ;;
    --reps) REPS="$2"; shift 2 ;;
    --ngl) NGLOBAL="$2"; shift 2 ;;
    --threads) THREADS="$2"; shift 2 ;;
    --batch) BATCH="$2"; shift 2 ;;
    --ubatch) UBATCH="$2"; shift 2 ;;
    --out-dir) OUT_DIR="$2"; shift 2 ;;
    --llama-cpp) LLAMA_CPP="$2"; shift 2 ;;
    --dry-run) DRY_RUN=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

[[ -n "$LLAMA_BENCH" ]] || { echo "error: set LLAMA_BENCH or pass --llama-bench" >&2; exit 2; }
[[ -x "$LLAMA_BENCH" ]] || { echo "error: not executable: $LLAMA_BENCH" >&2; exit 2; }
[[ -n "$MODEL" ]] || { echo "error: set MODEL or pass --model" >&2; exit 2; }
[[ -r "$MODEL" ]] || { echo "error: not readable: $MODEL" >&2; exit 2; }
case "$BACKEND" in
  vulkan|rocm) ;;
  *) echo "error: --backend must be vulkan or rocm" >&2; exit 2 ;;
esac

if [[ "$BACKEND" == "rocm" && -n "${ROCM_PATH:-}" ]]; then
  export LD_LIBRARY_PATH="$ROCM_PATH/lib:$ROCM_PATH/lib64:$(dirname "$LLAMA_BENCH")${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
fi

mkdir -p "$OUT_DIR"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BASE="$OUT_DIR/llama-bench-$BACKEND-$STAMP"
META="$BASE.metadata.txt"
OUT="$BASE.txt"

{
  echo "date_utc: $STAMP"
  echo "backend: $BACKEND"
  echo "model: $MODEL"
  echo "model_sha256: $(sha256sum "$MODEL" | awk '{print $1}')"
  echo "llama_bench: $LLAMA_BENCH"
  echo "llama_bench_sha256: $(sha256sum "$LLAMA_BENCH" | awk '{print $1}')"
  echo "ngl: $NGLOBAL"
  echo "threads: $THREADS"
  echo "batch: $BATCH"
  echo "ubatch: $UBATCH"
  echo "reps: $REPS"
  echo "depths: $DEPTHS"
  echo "uname: $(uname -a)"
  if [[ -n "$LLAMA_CPP" ]]; then
    echo "llama_cpp_commit: $(git -C "$LLAMA_CPP" rev-parse HEAD 2>/dev/null || echo 'not a git repository')"
    echo "llama_cpp_status: $(git -C "$LLAMA_CPP" status --short 2>/dev/null | wc -l) modified paths"
  fi
  echo "--- llama-bench --version ---"
  "$LLAMA_BENCH" --version 2>&1 || true
  echo "--- lscpu ---"
  lscpu 2>/dev/null | sed -n '1,30p' || true
  echo "--- free -h ---"
  free -h 2>/dev/null || true
} > "$META"

IFS=',' read -r -a DEPTH_ARRAY <<< "$DEPTHS"
if ((${#DEPTH_ARRAY[@]} == 0)); then
  echo "error: no depths" >&2
  exit 2
fi

echo "metadata: $META"
: > "$OUT"
for DEPTH in "${DEPTH_ARRAY[@]}"; do
  CMD=("$LLAMA_BENCH" -m "$MODEL" -ngl "$NGLOBAL" -fa on -t "$THREADS" \
       -b "$BATCH" -ub "$UBATCH" -p 0 -n 128 -r "$REPS" -d "$DEPTH")
  echo "command: ${CMD[*]}" | tee -a "$META"
  if ((DRY_RUN)); then
    continue
  fi
  "${CMD[@]}" 2>&1 | tee -a "$OUT"
done

if ((DRY_RUN)); then
  echo "dry run complete; no benchmark executed"
else
  echo "wrote $OUT"
fi
