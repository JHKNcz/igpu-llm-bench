# Controlled backend comparison at the 0.5 GB carve-out

This is the one comparison in the repository where Vulkan and ROCm ran under
the **same** memory setting, the **same** command-line flags, the **same**
models, and the **same** depths. It is the cleanest backend evidence here, and
it does not support a single "Vulkan is N times faster" claim.

Measured 2026-11-10. Carve-out: 512 MiB VRAM, 15,439 MiB GTT, 30,878 MiB host
RAM. llama.cpp `f872b5911` for Vulkan; the archived `build-rocm` binary inside
image `518ced857e9b…` (HIP 7.15.26333) for ROCm.

## Method

- `llama-bench -ngl 999 -fa on -t 12 -b 2048 -ub 512 -p 512 -n 128`
- Depths 0, 16,384, 65,536 where the model fits.
- 3 measured repetitions (2 for the larger models), one discarded warmup run
  per model.
- Vulkan and ROCm each ran the full matrix; nothing else was running.
- Every row records the carve-out, CPU/GPU temperature, and GPU power.
- A row whose spread exceeds 15% of its mean is flagged `noisy` and is not used
  to support a claim.

## Results

`tg128`, threads 12. Ratio is Vulkan / ROCm: **above 1 means Vulkan faster,
below 1 means ROCm faster.**

| Model | Size | KV | Depth | Vulkan t/s | ROCm t/s | Vulkan/ROCm | Winner |
|---|---|---:|---:|---:|---:|---:|---|
| LFM2.5-8B-A1B | 4.05 GiB | F16 | 0 | 43.88 | 30.97 | 1.42x | Vulkan |
| LFM2.5-8B-A1B | 4.05 GiB | F16 | 16,384 | 30.32 | 22.38 | 1.35x | Vulkan |
| LFM2.5-8B-A1B | 4.05 GiB | F16 | 65,536 | 20.63 ⚠ | 16.19 | 1.27x | Vulkan |
| LFM2.5-8B-A1B | 4.05 GiB | Q8_0 | 0 | 39.74 | 25.57 | 1.55x | Vulkan |
| LFM2.5-8B-A1B | 4.05 GiB | Q8_0 | 16,384 | 28.98 | 20.09 | 1.44x | Vulkan |
| LFM2.5-8B-A1B | 4.05 GiB | Q8_0 | 65,536 | 19.87 ⚠ | 8.24 | 2.41x ⚠ | Vulkan |
| LFM2.5-8B-A1B | 8.69 GiB | F16 | 0 | 35.12 | 25.66 | 1.37x | Vulkan |
| LFM2.5-8B-A1B | 8.69 GiB | F16 | 16,384 | 18.27 | 22.55 | 0.81x | **ROCm** |
| LFM2.5-8B-A1B | 8.69 GiB | F16 | 65,536 | 9.74 | 19.72 | 0.49x | **ROCm** |
| Qwen3-VL-4B-Instruct | 4.70 GiB | F16 | 0 | 11.74 | 10.34 | 1.14x | Vulkan |
| Qwen3-VL-4B-Instruct | 4.70 GiB | F16 | 16,384 | 5.46 | 6.40 | 0.85x | **ROCm** |
| Qwen3.6-35B-A3B-MTP | 17.25 GiB | F16 | 0 | — | 17.66 | — | ROCm only |
| Qwen3.6-35B-A3B-MTP | 17.25 GiB | F16 | 16,384 | — | 14.54 | — | ROCm only |

⚠ = the Vulkan row was flagged noisy and is not used to support a conclusion.

## What the table shows

### 1. Vulkan wins when the model is small

For the 4.05 GiB IQ4 model, Vulkan is faster at every depth measured:
**1.27x–1.42x** on the F16 KV rows. This is the one case where the archive's
"Vulkan is faster" story holds under controlled conditions.

### 2. The ranking reverses at depth for the 8.69 GiB model

Same architecture, 2.1x the bytes, same backend pair:

| Depth | Vulkan | ROCm | Winner |
|---|---:|---:|---|
| 0 | 35.12 | 25.66 | Vulkan 1.37x |
| 16,384 | 18.27 | 22.55 | **ROCm 1.23x** |
| 65,536 | 9.74 | 19.72 | **ROCm 2.03x** |

Vulkan's throughput falls by 72% from depth 0 to 64K; ROCm's falls by 23%. The
crossover happens somewhere between depth 0 and 16K.

### 3. The dense 4B model crosses over too, earlier

Vulkan is 1.14x faster at depth 0, but ROCm is 1.17x faster at 16K. The
crossover is between 0 and 16K, as with the 8.69 GiB model.

### 4. The 35B runs only on ROCm at this setting

Vulkan cannot load it: its total budget at 512 MiB is ~14.5 GiB and the model is
17.25 GiB. ROCm loads it through HIP unified memory into 30 GiB of host RAM and
decodes at 17.66 t/s at depth 0, falling to 14.54 t/s at 16K. GPU activity was
verified by sampling `gpu_busy_percent` during the run (46–65%), so this is GPU
work, not a CPU fallback.

There is **no Vulkan number for the 35B at this setting**, and none can exist.
This is a capacity result, not a speed comparison.

## Why the ranking flips: hypotheses, not conclusions

- **H-A: memory pressure.** At 512 MiB, Vulkan's addressable budget is about
  14.5 GiB and it cannot oversubscribe. As KV grows with depth, a large model
  leaves less headroom, and the driver may thrash or fall back to slower paths.
  ROCm's unified memory can spill into host RAM, trading bandwidth for capacity.
- **H-B: kernel behaviour at long context.** Vulkan's attention path may degrade
  more steeply with sequence length for this architecture. The 4 GiB model shows
  only a 53% drop from 0 to 64K on Vulkan, while the 8.7 GiB model shows 72%, so
  size and depth interact.
- **H-C: thermal.** The GPU reached 87–96 °C during these runs. Throttling could
  affect later runs more than earlier ones. Run order was not randomised, which
  is a real weakness of this campaign.

None of these is established. The *pattern* is measured; the *cause* is not.

## Data quality

- One Vulkan configuration (LFM IQ4 F16, threads 12) was cold-start contaminated
  on the first attempt and re-measured with a discarded warmup and 5 repetitions.
  The re-measured depth-0 value is 43.88 ± 2.73; the earlier 42.58 ± 9.32 is
  superseded.
- Two Vulkan 64K rows remain flagged noisy and are marked ⚠. The 2.41x figure for
  Q8_0 KV at 64K should not be quoted.
- The ROCm arm initially ran with `/dev/dri` but without `/dev/kfd`, which made
  HIP fall back to CPU while still printing numbers. That run was discarded, the
  device was added, and `campaign.py` now refuses to record a run when the log
  contains a CPU-fallback message.
- Spreads: most clean rows are within 5%. The 16K Vulkan rows are the least
  stable (up to 30% on one re-measurement), which is why only the depth-0 and
  the clean 64K comparisons are used for claims.

## Reproduce

```bash
# Vulkan
MODELS_DIR=$HOME/LLM/LLMs make campaign \
  LLAMA_BENCH=$HOME/llama.cpp/build-vulkan/bin/llama-bench

# ROCm, inside the archived image
MODELS_DIR=$HOME/LLM/LLMs python3 scripts/campaign.py \
  --llama-bench $HOME/LLM/llama.cpp-managed/build-rocm/bin/llama-bench \
  --container docker.io/rocm/dev-ubuntu-24.04:latest \
  --mount "$HOME/LLM:/LLM" \
  --model-root "$HOME/LLM/LLMs:/LLM/LLMs" \
  --warmup --include-large

# Join
python3 scripts/compare_backends.py \
  --vulkan data/processed/campaign-vulkan-20261110.csv \
           data/processed/campaign-vulkan-20261110-kv-recheck.csv \
  --rocm   data/processed/campaign-rocm-20261110.csv \
  --out data/processed/backend-comparison-512mb.csv
```

## What this does not establish

- It does not rank the backends in general. It ranks them at 512 MiB, on this
  iGPU, for these models.
- It does not explain the crossover. Three hypotheses are listed; none is tested.
- It does not cover the archived 16.79 GiB target, which is absent. The 35B here
  is the MTP variant (17.25 GiB), a different file.
- It does not cover ROCm 10. The measured ROCm is 7.15.
- It does not control run order or thermals, so a repeat could move the
  crossover point.
