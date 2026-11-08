# Roofline: where the decode time plausibly goes

This is a first-order argument, not a hardware-counter measurement. It asks a
narrow question: **if decode were limited only by streaming the active weights
and the KV cache from LPDDR5X, how close would the measured throughput be to the
memory roofline?** The answer is “not very close,” and the size of the gap is
itself the interesting result.

## Assumptions

| Quantity | Value | Why |
|---|---:|---|
| Target | Qwen3.6-35B-A3B UD-IQ4_NL, 16.79 GiB | `data/raw/llama-bench-*.txt` |
| Total parameters | 34.66 B | llama-bench table |
| Active parameters | 3 B | Vendor `A3B` label; not independently measured |
| Active weight fraction | 3 / 34.66 = 0.08655 | Assumption |
| Active weight bytes/token | 1.560 GB | 16.79 GiB × 0.08655 |
| Attention layers | 10 of 40 | `full_attention_interval=4` |
| KV cache | 20,480 bytes/token | 2 × 2 KV heads × 256 head_dim × 2 bytes × 10 attention layers |
| KV at 16K | 0.336 GB | 16,384 × 20,480 |
| KV at 64K | 1.342 GB | 65,536 × 20,480 |
| SSM/recurrent state | 1,067.81 MiB | 30 SSM layers; not modeled per token |
| Peak bandwidth | 120 GB/s | LPDDR5X-7500, 128-bit; exact RAM speed not recorded |
| Sensitivity | 102.4 / 128 GB/s | LPDDR5X-6400 / 8000 |

The active-weight term is the biggest assumption. The model is a mixture of
experts with 256 experts and 8 active per token. The vendor’s `A3B` label is a
convenient summary, but it may not equal the exact bytes read for every token.
If the true active traffic is 3.5 B instead of 3 B, the weight term rises by
about 17% and every “effective GB/s” value below rises with it.

The KV term assumes the entire F16 attention cache (10 layers, 20,480
bytes/token) is read once per generated token. Flash attention tiles the
computation; the memory system may serve part of the cache from a closer level.
The KV term is therefore an upper-bound estimate for the attention cache, not a
measured counter. The 30 SSM layers' recurrent state is excluded.

## Measured effective bandwidth

| Backend | Depth | t/s | Total GB/token | Effective GB/s | % of 120 GB/s |
|---|---:|---:|---:|---:|---:|
| ROCm | 0 | 10.89 | 1.560 | 16.99 | 14.2% |
| ROCm | 16,384 | 12.63 | 1.896 | 23.95 | 20.0% |
| ROCm | 65,536 | 7.84 | 2.903 | 22.76 | 19.0% |
| Vulkan | 0 | 25.31 | 1.560 | 39.49 | 32.9% |
| Vulkan | 16,384 | 19.96 | 1.896 | 37.84 | 31.5% |
| Vulkan | 65,536 | 13.97 | 2.903 | 40.55 | 33.8% |

Computed by `scripts/roofline.py`; raw values in `data/processed/roofline.csv`.

Two patterns stand out:

1. **Utilization is roughly flat with depth.** Vulkan is 32.9% at depth 0,
   31.5% at 16K, and 33.8% at 64K. The token rate falls, but the KV term grows
   almost exactly enough to keep the effective bandwidth near 38–40 GB/s. This
   is consistent with a fixed effective ceiling of about 40 GB/s, with KV
   traffic consuming a growing share of that fixed budget. It does not prove the
   ceiling is DRAM bandwidth.
2. **ROCm is further from the roofline at every depth.** At depth 0 it reaches
   14.2% of the assumed peak, versus 32.9% for Vulkan. The gap is largest at
   depth 0 (2.32x) and smaller at 16K/64K (1.58x/1.78x). At 16K and 64K, ROCm’s
   utilization is similar (20.0% vs 19.0%), which is what a roughly fixed
   effective ceiling would produce; its depth-0 utilization is lower (14.2%).
   That pattern is consistent with a fixed per-token overhead on the ROCm path
   that is diluted by KV traffic at depth, plus the build/carve-out confounds
   described in `docs/limitations.md`.

## Where the gap plausibly goes

Every item below is a **hypothesis**, not a measured conclusion.

### H1 — IQ4_NL dequantization

IQ4_NL stores 4-bit weights and dequantizes them on the fly. The dequantization
cost per byte is higher than for a plain F16 model, and it is sensitive to the
kernel’s vectorization and memory access pattern. The llama.cpp HEAD at the time
of the runs is a commit about guarding the IQ4_NL dequantize row kernel against
short rows (`f872b5911`, “cuda: guard the iq4_nl dequantize row kernel against
short rows”). That is evidence the path was under active tuning, not evidence
that it explains this gap.

**What would test it:** run the same model at IQ4_XS/Q5_K_M/Q8_0 on both
backends. If the Vulkan/ROCm ratio shrinks as the quantization gets simpler, the
dequantization path is a strong candidate.

### H2 — MoE expert routing

The model has 256 experts and activates 8 per token. The active expert weights
are scattered across the 16.79 GiB file, so the access pattern is less
sequential than a dense model. Different backends schedule the expert matmuls
differently; a backend with more launch or synchronization overhead per expert
could lose more time here.

**What would test it:** compare a dense model of similar active size on the same
two backends, and profile the expert kernels. A dense model removes routing but
also changes the arithmetic intensity, so it is not a clean isolation.

### H3 — KV cache and recurrent-state traffic

The model is hybrid: 10 of 40 layers use full attention, and the other 30 use an
SSM/recurrent state. The attention KV cache is 20,480 bytes/token, or 320 MiB at
16K and 1.28 GiB at 64K. At 64K, the first-order model adds 1.342 GB/token of KV
traffic, and the effective bandwidth stays near 40 GB/s (33.8%) on Vulkan. The
throughput drop is consistent with that extra traffic consuming a fixed ~40 GB/s
budget; the absolute ceiling is a separate question. The long-context experiment
shows generation falling from 33.67 t/s at 4K to 21.99 t/s at 61K for MTP F16,
and from 32.24 to 22.13 t/s for DFlash2 F16. That trend is consistent with KV
traffic, but the long-context runs are speculative and use a different protocol.

The 30 SSM layers carry a 1,067.81 MiB recurrent state. If that state is
read/written once per token, it adds about 1.12 GB/token and the effective
bandwidth would be about 64 GB/s (54% of peak). The first-order table excludes it
because the per-token access pattern is not recorded. This is the largest
unmodeled term in the roofline.

**What would test it:** run the same depth sweep with F16 and Q8_0 KV on the
**baseline** (no drafting), and measure the KV read volume with a profiler. The
long-context suite already shows Q8_0 can help prompt processing substantially
while having a mixed effect on generation; that is a clue, not a resolution.

### H4 — iGPU occupancy and wave size

The Vulkan device reports warp size 64, 64 KiB shared memory, and
`KHR_coopmat`; the ROCm device reports wave size 32 and `VMM: no`. The Radeon
890M is a small iGPU (16 CUs by vendor specification, not measured here). A
kernel that is occupancy-limited on 16 CUs will be sensitive to block size,
register pressure, and synchronization. The two backends compile different
kernels, so equal source code does not mean equal occupancy.

**What would test it:** collect occupancy and wave-issue counters for the same
matmul shapes on both backends. This is the most direct way to separate
“bandwidth” from “not enough work in flight.”

### H5 — Thermal/power and run order

The Vulkan nmax6 runs recorded 91–94 °C and 45–52 W; the ROCm selected
configuration has no sensor data. Clocks and power limits were not locked. The
Vulkan nmax6 throughput increased across its three measured runs (37.98 → 42.20
→ 43.14 t/s), which looks more like clock ramp or warmup than thermal
throttling. The ROCm depth-0 point is lower than its own 16K point, which is not
the expected thermal shape.

**What would test it:** a wall-power meter, locked clocks, a fixed fan/power
profile, and alternating backend order across repetitions.

## What the roofline does **not** say

- It does not say Vulkan is 2.3x faster in general. The 2.3x is the raw depth-0
  ratio, with different builds and an unresolved carve-out.
- It does not say the remaining gap is definitely dequantization, routing, KV,
  or occupancy. Those are hypotheses with different testability.
- It does not say 120 GB/s is the achievable peak. If the achievable peak is
  80 GB/s, the Vulkan depth-0 utilization is 49%, not 33%, and the “gap” is
  smaller. The 102.4/120/128 GB/s sensitivity is in `config/models.json`; the
  table uses 120 GB/s.
- It does not model the 1,067.81 MiB SSM recurrent state. If that state is read
  per token, the effective bandwidth is higher and the gap is smaller.
- It does not include the cost of the draft model in the speculative rows. The
  roofline table is baseline-only for that reason.

## What would make the argument strong

1. A controlled backend A/B at the same build and carve-out, with alternating
   order and at least five repetitions.
2. Hardware counters for memory traffic, occupancy, and wave issue on both
   backends.
3. A quantization sweep (IQ4_XS, Q5_K_M, Q8_0) to test H1.
4. A dense-model control to test H2.
5. A baseline F16-vs-Q8 KV sweep at 4K/16K/64K to test H3.
6. A wall-power meter and locked clocks to test H5.

Until then, the honest summary is: **Vulkan gets more of the available bandwidth
than ROCm on this machine, but neither backend is close to the assumed
LPDDR5X roofline. The effective ceiling is about 40 GB/s, roughly one-third of
the assumed peak, and the archived comparison is not controlled enough to
attribute the difference to one cause.**
