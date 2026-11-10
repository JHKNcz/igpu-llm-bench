# Vulkan, ROCm, and CPU at the 0.5 GB carve-out

Three ways to run the same models on the same machine, measured under one memory
setting. The result is not "Vulkan is faster" or "ROCm is faster". It is that
**the CPU is competitive at short context, ROCm is the most consistent GPU
backend, and Vulkan is the most variable of the three.**

Measured 2026-11-10, carve-out unchanged at 512 MiB VRAM / 15,439 MiB GTT /
30,878 MiB host RAM.

## Method

- `llama-bench -ngl 999 -fa on -t 12 -b 2048 -ub 512 -p 512 -n 128`
  (CPU runs use `-ngl 0` and a CPU-only build of the same commit).
- Backends interleaved, **round order shuffled** with a fixed seed, so no
  backend systematically runs first (cold) or last (hot).
- Three rounds for the main suites, six for the stability suite.
- One discarded warmup per model in the earlier fixed-order campaign; the
  randomised suites rely on shuffling instead.
- Every row records its round and its position in the round, so an order effect
  can be tested after the fact (`scripts/order_effects.py`).
- GPU temperature and power sampled once per second.

## The 8.69 GiB model: the main result

`tg128`, medians across rounds.

| Depth | Vulkan | ROCm | CPU |
|---:|---:|---:|---:|
| 0 | 23.97 | **30.61** | **36.70** |
| 4,096 | 18.28 | 24.45 | — |
| 8,192 | 17.46 | 23.72 | — |
| 12,288 | 15.70 | 22.56 | — |
| 16,384 | 16.31 | **26.14** | 23.85 |

Ranges, which matter as much as the medians:

| Backend | Depth 0 range | n | Spread |
|---|---|---:|---:|
| Vulkan | 18.66–35.19 | 6 | 5.99 sd |
| ROCm | 26.93–34.55 | 6 | 3.13 sd |
| CPU | 35.87–36.59 | 3 | 0.36 sd |

**ROCm is faster than Vulkan at every depth measured**, by 1.28x at depth 0
(median) and 1.60x at 16K. It also wins in every one of the three randomised
rounds at 16K (Vulkan/ROCm = 0.61x, 0.65x, 0.59x).

**Vulkan is not stable.** Its depth-0 throughput spans 18.7–35.2 t/s across six
repetitions of the same command. The earlier fixed-order campaign recorded
35.12 t/s once, with a tight ±0.04; that was the top of the distribution, not
the typical value. This is why the earlier "Vulkan wins at depth 0" claim does
not survive randomisation.

**The CPU is the fastest thing at depth 0** and stays competitive at 16K
(23.85 vs ROCm's 26.14).

## The other models

Depth 0, `tg128`, medians:

| Model | Size | CPU | Vulkan | ROCm |
|---|---|---:|---:|---:|
| LFM2.5-8B-A1B IQ4_NL | 4.05 GiB | **51.99** | 43.88 | 30.97 |
| LFM2.5-8B-A1B Q8_K_XL | 8.69 GiB | **36.70** | 23.97 | 30.61 |
| Qwen3-VL-4B Q8 (dense) | 4.70 GiB | **14.81** | 11.74 | 10.34 |
| Qwen3.6-35B-A3B-MTP | 17.25 GiB | **18.38** | — | 17.66 |

Depth 16,384:

| Model | CPU | Vulkan | ROCm |
|---|---:|---:|---:|
| LFM IQ4_NL | 29.57 | **30.32** | 22.38 |
| LFM Q8_K_XL | 23.85 | 16.31 | **26.14** |
| Qwen3-VL-4B Q8 | 4.94 | 5.46 | **6.40** |
| Qwen3.6-35B-MTP | — | — | 14.54 |

The CPU wins at short context for **every** model tested, including the 35B.
At 16K the ranking depends on the model: Vulkan for the 4 GiB MoE, ROCm for the
8.7 GiB MoE and the dense 4B, with the CPU close behind.

## Why the CPU is competitive

Decode at short context is dominated by streaming the active weights once per
token. The CPU and the iGPU read the same LPDDR5X through the same memory
controller. The CPU has AVX-512 and no driver or command-submission overhead;
the iGPU adds scheduling and synchronization on top of the same bandwidth.

Prefill tells the opposite story: on the same runs, `pp512` is about 1,025 t/s on
Vulkan and 264 t/s on the CPU for the 8.69 GiB model. The GPU is roughly 4x
faster when the work is compute-dense. The iGPU is not useless; it is simply not
the right tool for bandwidth-bound decode of a small MoE.

This is a hypothesis for the mechanism, not a measured decomposition. The
numbers are measured; the explanation is not.

## Quantization at depth 0

Interleaved, four rounds, medians. IQ4 carries 0.513 GB of active weights per
token; Q8 carries 1.102 GB, a 2.15x ratio.

| Backend | IQ4_NL | Q8_K_XL | IQ4/Q8 |
|---|---:|---:|---:|
| Vulkan | 49.30 | 25.63 | 1.92x |
| ROCm | 44.86 | 28.93 | 1.55x |
| CPU | 51.50 | 36.64 | 1.41x |

A purely bandwidth-bound decode would show 2.15x. Only Vulkan comes close; the
CPU and ROCm show more fixed overhead. Equivalently, Q8 achieves higher
effective bandwidth than IQ4 on all three backends, so the 4-bit path is paying
a dequantization cost rather than winning proportionally on traffic.

## The 35B at 0.5 GB

- ROCm loads it through HIP unified memory: 17.66 t/s at depth 0, 14.54 at 16K.
  GPU activity verified with `gpu_busy_percent` (46–65%).
- CPU: 18.38 t/s at depth 0 — slightly **faster** than the GPU.
- Vulkan could not load it with the desktop running: at `-ngl 0` it failed with
  `vk::DeviceLostError` after `Not enough memory for command submission`, while
  466 of 512 MiB of dedicated VRAM was held by the desktop session.
  `llama-bench --list-devices` reported 15,950 MiB total and 14,814 MiB free.
  A headless session was **not** tested. A formal `-ngl` sweep (0, 8, 16, 22,
  28, 34, 40) failed identically at every level, including CPU-only `-ngl 0`, so
  the block is not about how many layers are offloaded.

## Order and thermal checks

`scripts/order_effects.py` reports, per group:

- **Per-round ratios.** At 16K the Vulkan/ROCm ratio is 0.61, 0.65, 0.59 — the
  same sign and similar magnitude in all three rounds.
- **Rank correlation of throughput with position in the round.** For the 8.69 GiB
  model at depth 0, rho = +0.03; at 16K, rho = −0.28. Neither suggests the run
  order is driving the number.
- **Rank correlation with round number.** +0.00 and +0.26. No strong thermal
  drift across rounds.

So the ROCm advantage at 16K is not an ordering artefact. The Vulkan variance at
depth 0 is also not explained by position; it appears to be session-level
instability in the Vulkan path, which is a finding in its own right.

## Data quality

- The first fixed-order campaign recorded Vulkan at 35.12 t/s at depth 0. Six
  randomised repetitions give a median of 23.97 and a range of 18.7–35.2. The
  single value was an upper-tail sample and is **not** used for any claim.
- One ROCm 16K sample was flagged noisy (26.14 ± 4.53); the other two rounds were
  24.02 ± 1.83 and 27.61 ± 2.60.
- One Vulkan 8K sample hit 30.75 against a 16.4–17.5 cluster; treated as an
  outlier and excluded from the trend by using medians.
- The ROCm arm initially ran without `/dev/kfd`, silently falling back to CPU.
  That run was discarded; `ab_campaign.py` and `campaign.py` now refuse to record
  a run when the log contains a CPU-fallback message.

## What this does not establish

- It does not rank the backends in general. It ranks them at 512 MiB, on one
  iGPU, for these models.
- It does not explain Vulkan's instability. Memory placement between the 512 MiB
  dedicated pool and GTT is the leading suspect; it was not instrumented.
- It does not test a headless session, which might let Vulkan load the 35B.
- It does not cover ROCm 10.1. The measured runtime is ROCm 10.0.0.
- It does not control thermals with a fixed power profile.

## Reproduce

```bash
make ab SUITE=a VULKAN_BENCH=... ROCM_BENCH=... CPU_BENCH=... \
  ROCM_IMAGE=docker.io/rocm/dev-ubuntu-24.04:10.0.0-full \
  ROCM_MOUNT="$HOME/LLM:/LLM" ROCM_MODEL_ROOT="$HOME/LLM/LLMs:/LLM/LLMs" ROUNDS=3
make order AB_CSV=runs/ab-a-*/ab.csv
```
