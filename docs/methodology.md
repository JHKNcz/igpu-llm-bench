# Methodology

## 1. Archived llama-bench comparison (the headline)

**Model:** `Qwen3.6-35B-A3B-UD-IQ4_NL.gguf`, 16.79 GiB, 34.66 B parameters,
label `qwen35moe 35B.A3B IQ4_NL - 4.5 bpw`.

**Recorded settings from the logs:**

| Setting | Value |
|---|---|
| `ngl` | 999 |
| Flash attention | on (`fa = 1` in the table) |
| Test | `tg128` |
| Depths | 0, 16,384, 65,536 |
| Measured runs per test | 2 (the log says “generation run 1/2”, “2/2”) |
| Warmup | one warmup generation run before the measured runs |
| Vulkan build | `f872b5911 (11310)` |
| ROCm build | `unknown (0)` |

**What is not recorded:** the exact original CLI, batch size, ubatch size,
thread count, power limit, clocks, temperatures, BIOS version, and the per-run
VRAM carve-out. The wrapper reconstructs the flags from the table header and the
2026-10-02 setup notes. A fresh run is the only way to prove the original
invocation.

**Reproduction wrapper:**

```bash
LLAMA_BENCH=$HOME/llama.cpp/build-vulkan/bin/llama-bench \
MODEL=$HOME/models/Qwen3.6-35B-A3B-UD-IQ4_NL.gguf \
scripts/bench.sh --backend vulkan --llama-cpp "$HOME/llama.cpp"
```

The wrapper runs one `llama-bench` invocation per depth, with
`-ngl 999 -fa on -t 12 -b 2048 -ub 512 -p 0 -n 128 -r 2 -d <depth>`.
It records the command, model hash, binary hash, `llama-bench --version`,
`lscpu`, `free -h`, and the llama.cpp commit in a `.metadata.txt` file next to
the output. It does not overwrite an existing run.

For a short harness check with the present 4 GiB LFM model:

```bash
LLAMA_BENCH=$HOME/llama.cpp/build-vulkan/bin/llama-bench \
MODEL=$HOME/models/LFM2.5-8B-A1B/LFM2.5-8B-A1B-UD-IQ4_NL.gguf \
scripts/bench.sh --backend vulkan --depths 0 --reps 1
```

The LFM run is a smoke test of the wrapper, not a reproduction of the 35B
headline.

## 2. Vulkan speculative-decoding comparison (2026-10-18)

**Source:** `~/LLM/testing_resources/speculative_compare/results/20261018-200821-488233/`.

| Setting | Value |
|---|---|
| Backend | Vulkan, build `f872b5911 (11310)` |
| Context capacity | 32,768 tokens |
| GPU layers | 99 |
| Flash attention | on |
| Slots | 1 |
| Thinking | disabled |
| Automatic fit | disabled |
| Prompt cache reuse | disabled |
| Sampling | greedy |
| Output | exactly 256 tokens per request; EOS ignored |
| Prompts | 3 synthetic prompts (stock fundamentals, Python portfolio analysis, structured earnings extraction) |
| Rounds | 3, with rotating mode order |
| Warmup | 64 unmeasured tokens after loading |
| Modes | baseline, DFlash2 (6 draft tokens), MTP-off, MTP (2 draft tokens) |
| Samples | 9 measured requests per mode (3 prompts × 3 rounds) |

The primary metric is generation tokens/second, not total request time. Paired
speedups match the same prompt and round before taking the median. The suite is
a throughput benchmark, not a correctness or answer-quality evaluation.

## 3. Long-context KV-cache comparison (2026-10-18)

**Source:** `~/LLM/testing_resources/speculative_compare/long-context-results/20261018-203923-240284/`.

| Setting | Value |
|---|---|
| Context capacity | 65,536 tokens |
| Actual input depths | approximately 4,096, 32,768, 61,440 tokens |
| Modes | MTP (2 draft tokens), DFlash2 (6 draft tokens) |
| Main K/V cache | F16, then Q8_0 |
| Draft K/V cache | F16 |
| Rounds | 2 |
| Output | 256 tokens per request |
| Sampling | greedy |
| Thinking | off |
| Prompt-prefix reuse | disabled |
| Measured requests | 24 |

The suite records retrieval accuracy over a synthetic prompt with fields near
the beginning, middle, and end. It is a throughput and retrieval check, not a
general long-context quality benchmark.

## 4. ROCm coding-quality matrix (2026-10-02)

**Source:** `~/LLM/testing_resources/coder_benchmark/REVIEW.md`.

| Setting | Value |
|---|---|
| Backend | ROCm, 512 MiB reserved VRAM, HIP unified memory, GPU graphs disabled |
| Context capacity | 65,536 tokens |
| Output per turn | 4,096 tokens |
| Maximum turns | 8 per task |
| Conditions | baseline/thinking off; DFlash2-six/thinking off; DFlash2-six/budget 2048; baseline/budget 2048 |
| Acceptance checks | 27 (8 public, 19 independent) |
| Runs | one per condition, fixed order |
| Total elapsed | 65.75 minutes |

This is a coding-quality experiment on ROCm only. It is not a backend
comparison. The harness code and model outputs are not included; the review is.

## 5. Coding-agent workload (2026-10-13)

**Source:** `~/LLM/testing_resources/llama-agent-bench/runs/20261013-213047-183018/`.

| Setting | Value |
|---|---|
| Backend | Vulkan, build `f872b5911 (11310)` |
| Context | 32,768 tokens |
| Configurations | 12 |
| Tasks | 3 (`dom_watch`, `event_pipeline`, `dependency_scheduler`) |
| Repetitions | 3 per task |
| Max output | 12,288 tokens |
| Reasoning budget | 2,048 tokens |
| Temperature / seed | 0 / 20261013 |
| Quality mode | sandboxed Podman/Docker, no network |
| Metric | median wall TPS (completion tokens / request seconds) |

Wall TPS includes prefill, reasoning, generation, and HTTP transport. It is not
pure decode throughput. The run's `summary.csv` is included; the harness and
model outputs are not.

## 6. Build and hash checks

```bash
git -C "$LLAMA_CPP" log -1 --format='%H%n%cd%n%s'
git -C "$LLAMA_CPP" status --short
sha256sum "$VULKAN_SERVER" "$ROCM_SERVER" "$TARGET" "$DRAFT"
"$LLAMA_BENCH" --version
```

The archived hashes are in
`data/raw/historical/model-binary-sha256-2026-10-02.txt`. The Vulkan and ROCm
`llama-server` hashes match the current binaries. The archived `llama-bench`
binary hash was not recorded.

## 7. Roofline computation

`scripts/roofline.py` reads `data/processed/llama-bench.csv` and
`config/models.json` and computes:

```text
active_weight_bytes = model_bytes × (active_params / total_params)
kv_bytes            = depth × 20,480 bytes
total_bytes         = active_weight_bytes + kv_bytes
effective_GB/s      = total_bytes × tps / 10^9
percent_of_peak     = 100 × effective_GB/s / peak_GB/s
```

The model is a mixture of experts and a hybrid attention/SSM model. The
active-parameter count (3 B) is the vendor’s `A3B` label, not an independently
measured activation count. Ten of the 40 layers use full attention
(`full_attention_interval=4`), 2 KV heads, head_dim 256, F16 K and V:
`2 × 2 × 256 × 2 × 10 = 20,480 bytes/token`. The 30 SSM/recurrent layers use a
1,067.81 MiB state; its per-token traffic is not modeled. The 320 MiB KV cache
at 16K in the server log is consistent with 20,480 bytes/token. The peak assumes
LPDDR5X-7500 on a 128-bit bus (120 GB/s); the exact RAM speed is not recorded.
These are first-order approximations, not hardware counters. See
`analysis/roofline.md` for the argument and its limits.
