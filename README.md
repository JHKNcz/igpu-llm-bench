# igpu-llm-bench

A small, reproducible benchmark of a 35B mixture-of-experts model on an AMD
Strix Point iGPU, comparing Vulkan and ROCm decode throughput and asking where
the time plausibly goes.

The headline is a **2.3x raw gap** between Vulkan and ROCm on the same model and
machine. The honest version is more interesting: the archived runs are **not a
controlled A/B**, and the defensible range is **1.4x–2.3x**. The repository keeps
the raw logs, the parsed tables, the exact hashes, and the caveats together so a
reader can check the claim rather than take it on trust.

## Headline

Same model, same machine, two backends, `tg128`:

| Backend | Build | t/s | ± |
|---|---|---:|---:|
| Vulkan | `f872b5911 (11310)` | **25.31** | 0.75 |
| ROCm | `unknown (0)` | **10.89** | 1.61 |

Raw ratio: **2.32x**.

**What this is not:** a controlled backend comparison. The builds differ, the
per-run VRAM carve-out is not consistently recorded, and ROCm’s own depth series
is non-monotonic (10.89 at depth 0, 12.63 at 16K). A separate ROCm server
baseline reached 18.17 t/s, so 10.89 is a lower bound. The ROCm log’s
“15,438 MiB VRAM” is UMA/GTT, not a 15.4 GB dedicated carve-out.

**What survives:** Vulkan was faster in every archived same-machine comparison,
by roughly **1.4x–2.3x**. The direction is consistent; the exact size is not
settled. See [`docs/limitations.md`](docs/limitations.md).

A second, more controlled result is Vulkan-only: in a 3-round paired run,
baseline **23.78 t/s**, DFlash2 **31.02 t/s (1.28x)**, and MTP **36.27 t/s
(1.51x)**. See [`docs/related/speculative-decoding.md`](docs/related/speculative-decoding.md).

## Why this is interesting

- The model is 16.79 GiB, but only about 3 B of its 34.66 B parameters are
  active per token. On a 16 GiB-class iGPU, the active-weight traffic is roughly
  1.56 GB/token.
- At 25.31 t/s, the first-order model implies about **39.5 GB/s** of effective
  bandwidth, or **33%** of an assumed 120 GB/s LPDDR5X peak. At 64K depth, the
  estimate is **40.5 GB/s (34%)**: the KV term grows, but the effective bandwidth
  stays roughly flat, consistent with a fixed ~40 GB/s ceiling and a throughput
  drop caused by the extra KV bytes. The model is hybrid (10 attention layers,
  30 SSM layers), so the KV term is smaller than a naive 40-layer estimate.
- The gap to the roofline is large enough that “it is just bandwidth” is not a
  satisfying explanation. The plausible remaining costs — IQ4_NL dequantization,
  MoE expert routing, KV cache, iGPU occupancy, thermal/power — are labeled as
  hypotheses in [`analysis/roofline.md`](analysis/roofline.md).

## Hardware

| Component | Value |
|---|---|
| CPU | AMD Ryzen AI 9 HX 375, 12C/24T |
| iGPU | Radeon 890M, `gfx1150`, RADV STRIX1, Mesa 26.0.8 |
| Memory | 32 GB LPDDR5X (30 GiB visible); exact speed not recorded |
| VRAM | 512 MiB dedicated + 15.08 GiB GTT current; historical 16 GiB note conflicts |
| Kernel | `7.0.0-42-generic` current; archived runs on `7.0.0-38-generic` |
| NPU | `amdxdna` loaded, `/dev/accel/accel0` present; unused |
| llama.cpp | `f872b591121761ac7b2af18283bd99bdc092a63a` |

Full details, commands, and the carve-out conflict:
[`docs/hardware.md`](docs/hardware.md).

## Quick start

The model weights are **not** included. Download the exact target and verify its
hash before benchmarking:

- `Qwen3.6-35B-A3B-UD-IQ4_NL.gguf`
- 18,040,888,288 bytes
- SHA256 `0d17e255dc257a11f398ed4bc8d62412d8ce9ca24b3fce2947d962e4bfed5758`

The draft GGUFs are also not included; sizes and hashes are in
[`config/models.json`](config/models.json).

```bash
export LLAMA_BENCH=$HOME/llama.cpp/build-vulkan/bin/llama-bench
export MODEL=$HOME/models/Qwen3.6-35B-A3B-UD-IQ4_NL.gguf
export LLAMA_CPP=$HOME/llama.cpp

./scripts/bench.sh --backend vulkan --llama-cpp "$LLAMA_CPP"
python3 scripts/parse_logs.py
python3 scripts/roofline.py
```

`bench.sh` runs one `llama-bench` invocation per depth with
`-ngl 999 -fa on -t 12 -b 2048 -ub 512 -p 0 -n 128 -r 2`, and writes the
command, model hash, binary hash, `llama-bench --version`, `lscpu`, and
`free -h` next to the output.

For a short harness check with the 4 GiB LFM model:

```bash
LLAMA_BENCH=$HOME/llama.cpp/build-vulkan/bin/llama-bench \
MODEL=$HOME/models/LFM2.5-8B-A1B/LFM2.5-8B-A1B-UD-IQ4_NL.gguf \
./scripts/bench.sh --backend vulkan --depths 0 --reps 1
```

The ROCm backend needs a working ROCm runtime and `LD_LIBRARY_PATH`; the source
machine no longer has `/opt/rocm`, so the archived ROCm numbers cannot be
re-run there without a rebuild or the original container.

## Repository map

| Path | What it is |
|---|---|
| `README.md` | This file |
| `RESULTS.md` | All tables, one row per run, with sources |
| `docs/methodology.md` | Exact flags, repetitions, warmup, build info |
| `docs/hardware.md` | CPU, iGPU, RAM, VRAM, kernel, drivers, NPU |
| `docs/limitations.md` | Single machine, thermal, confounds, missing data |
| `docs/privacy.md` | Redaction log and secret-scan results |
| `data/raw/` | Sanitized original logs and historical records |
| `data/processed/` | CSV/JSON parsed from the raw files |
| `data/provenance.md` | File → source → date → transformation |
| `scripts/bench.sh` | Reproducible llama-bench wrapper |
| `scripts/parse_logs.py` | Raw logs → CSV |
| `scripts/roofline.py` | Theoretical vs measured bandwidth |
| `analysis/roofline.md` | The written roofline argument |
| `config/models.json` | Expected files, sizes, SHA256, presence |
| `docker/rocm-ubuntu26.04.Dockerfile` | Archived ROCm build recipe |

## Results at a glance

| Result | Value | Where |
|---|---:|---|
| Vulkan `tg128` | 25.31 t/s | `RESULTS.md` §1 |
| ROCm `tg128` | 10.89 t/s | `RESULTS.md` §1 |
| Raw ratio | 2.32x | `RESULTS.md` §1 |
| ROCm server baseline | 18.17 t/s | `RESULTS.md` §2 |
| Vulkan server baseline | 25.63 t/s | `RESULTS.md` §2 |
| Vulkan DFlash2 (paired) | 31.02 t/s, 1.28x | `RESULTS.md` §3 |
| Vulkan MTP (paired) | 36.27 t/s, 1.51x | `RESULTS.md` §3 |
| Vulkan 61K MTP F16 | 21.99 t/s | `RESULTS.md` §4 |
| Roofline, Vulkan depth 0 | 39.5 GB/s, 33% of 120 | `RESULTS.md` §6 |
| Roofline, Vulkan 64K | 40.5 GB/s, 34% of 120 | `RESULTS.md` §6 |

## Limitations in one paragraph

One machine, one iGPU, one model family. The backend comparison differs in
build and memory carve-out; the ROCm runtime is gone; the target and draft GGUFs
are absent; the runs have no boot-level error bars; clocks and power were not
locked; and the roofline uses an assumed 120 GB/s peak. The secondary
experiments use different protocols and should not be averaged. Details and
what would close each gap: [`docs/limitations.md`](docs/limitations.md).

## Privacy

The repository is private. It contains no model weights, tokens, keys, emails,
MAC addresses, serial numbers, or personal names. Paths and hostnames were
redacted; the redaction log and scan results are in
[`docs/privacy.md`](docs/privacy.md).

## License

Code (shell, Python, Dockerfile): MIT, see [`LICENSE`](LICENSE).
Text, tables, logs, CSV, and JSON: CC BY 4.0; see
[`LICENSE-DATA`](LICENSE-DATA). Model weights are not included and retain their
own licenses.

## What is missing

- Repeated runs across boots, with locked clocks and wall power.
- A controlled backend A/B at the same build and VRAM carve-out.
- A rebuilt ROCm runtime or the original container.
- The exact target/draft GGUFs (hashes are recorded).
- A filled 61K baseline, not only speculative modes.
- An NPU comparison; the NPU is present but unused.
- A second machine.

See [`docs/limitations.md`](docs/limitations.md) for the full list.
