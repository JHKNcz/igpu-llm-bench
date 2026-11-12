# Findings in one page

For a reader who wants the result without the repository. Everything below is
measured on one laptop and reproducible from the files in this repo.

## The question

A 35B-class language model runs on an AMD Ryzen AI 9 HX 375 with a Radeon 890M
integrated GPU. Two software paths can drive that GPU — Vulkan and ROCm — and
there is always the CPU. Which is fastest?

## The short answer

**At short context, the CPU. At long context, ROCm. Vulkan is the most variable
of the three.**

At a fixed 512 MiB VRAM carve-out, same flags, shuffled run order, `tg128` on an
8.69 GiB mixture-of-experts model:

| Depth | Vulkan | ROCm | CPU |
|---:|---:|---:|---:|
| 0 | 24.0 | 30.6 | **36.5** |
| 16K | 16.3 | **26.1** | 23.9 |

The same ordering holds at depth 0 for every model tested, including the 35B:

| Model | CPU | Vulkan | ROCm |
|---|---:|---:|---:|
| 4.05 GiB MoE | **52.0** | 43.9 | 31.0 |
| 8.69 GiB MoE | **36.5** | 24.0 | 30.6 |
| 4.70 GiB dense | **14.8** | 11.7 | 10.3 |
| 17.25 GiB MoE | **18.4** | — | 17.7 |

## Three things worth knowing

1. **The iGPU is not automatically faster.** Decode streams the active weights
   once per token; the CPU and GPU read the same memory through the same
   controller, and the CPU has no driver overhead. Prefill is the opposite story
   — 1,025 t/s on Vulkan vs 264 t/s on CPU for the same model — so the GPU earns
   its place when the work is compute-dense.

2. **Vulkan is unstable at this memory setting.** The identical command gives
   18.7–35.2 t/s at depth 0 across six repetitions (sd 6.0), against 26.9–34.6
   for ROCm (sd 3.1) and 35.9–36.6 for the CPU (sd 0.4). A single earlier
   session recorded 35.1 and made Vulkan look like the winner; six randomised
   repetitions put the median at 24.0.

3. **4-bit quantization does not pay off in proportion to its size.** The IQ4
   file carries 2.15x fewer bytes per token than Q8, but is only 1.4x–1.9x
   faster depending on the backend. Q8 achieves *higher* effective bandwidth
   than IQ4 everywhere (40.4 vs 26.4 GB/s on the CPU), so the 4-bit path is
   paying a dequantization cost rather than winning on memory traffic.

## The carve-out changes speed, not just capacity

At 16 GB the same small models decode 1.4–3.0x faster, and the 35B runs on
Vulkan at **24.19 t/s** where it could not load at 0.5 GB. The cost is host RAM
(15.3 GiB): the 35B on CPU drops from 18.38 to 13.78 t/s.

| 35B, depth 0 | 0.5 GB | 16 GB |
|---|---:|---:|
| Vulkan | fails | **24.19** |
| ROCm | 17.66 | fails |
| CPU | 18.38 | 13.78 |

So "more VRAM" is not strictly better: 16 GB is best for models that fit the GPU,
0.5 GB is the only setting where ROCm's unified-memory path runs the 35B.

## Speculative decoding

MTP gives a solid 1.51x (95% CI 1.37–1.63). DFlash2 gives 1.28x but the interval
touches 1.00 (1.00–1.56), so at nine samples it is not distinguishable from noise
for every prompt.

## What this does not show

- It is one laptop, one iGPU, one software version (ROCm 10.0.0).
- It does not explain Vulkan's instability. Memory placement between the 512 MiB
  dedicated pool and GTT is the leading suspect; it was not instrumented.
- The 35B was measured on ROCm and CPU only; Vulkan could not load it with the
  desktop running.
- The "2.3x" figure that started this project compares two different memory
  settings. It is kept in `RESULTS.md` with that caveat and is not a controlled
  result.

## The memory setting is a command, not a BIOS trip

On kernel 7.0.0-43 the carve-out is writable from Linux:

```bash
echo 7 | sudo tee /sys/class/drm/card*/device/uma/carveout   # 16 GB
sudo amd-smi set -g 0 -m 7                                   # same
```

Two traps: the GPU is `card1` (not `card0`), and indices are 0-7. The write
survives reboot. `scripts/carveout.sh --show` prints the state.

## How to check it

```bash
git clone <this repo>
make check        # regenerate, verify every number against the data, scan
```

`scripts/verify_results.py` fails if a headline number in the documentation does
not appear in the generated data. That is the mechanism behind every figure
above.

Full detail: [`README.md`](README.md), [`RESULTS.md`](RESULTS.md), and
[`docs/related/backend-comparison-512mb.md`](docs/related/backend-comparison-512mb.md).
