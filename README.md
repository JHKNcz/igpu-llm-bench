# igpu-llm-bench

**Decode throughput for a 35B mixture-of-experts model on a Radeon 890M
integrated GPU, measured on two backends, with the raw logs, the analysis
scripts, and the caveats that keep the claim honest.**

One laptop. One model. Two backends. A 2.3x raw gap that turns out to be
somewhere between 1.4x and 2.3x once you look at how the runs were actually
configured. The repository is built so that a stranger can check that sentence
rather than trust it.

```
Vulkan  25.31 t/s   ────────────────────────────
ROCm    10.89 t/s   ───────────
                    raw ratio 2.32x, defensible range 1.4x–2.3x
```

---

## TL;DR

- **Vulkan was faster than ROCm in every archived same-machine comparison**, by
  roughly 1.4x–2.3x. The 2.32x headline is the raw depth-0 ratio, not a
  controlled effect size.
- **The archived comparison is not a controlled A/B.** Build, VRAM carve-out,
  and runtime all differ, and ROCm's own depth series is non-monotonic.
- **MTP speculative decoding is a clear win** on this machine: 1.51x generation
  throughput, 95% CI 1.37–1.63.
- **DFlash2 is marginal**: 1.28x point estimate, but the 95% CI touches 1.00
  (1.00–1.56). With 9 paired cells it is not distinguishable from noise for
  every prompt.
- **Neither backend reaches the memory roofline.** Effective bandwidth plateaus
  near 40 GB/s, about a third of an assumed 120 GB/s peak.

## Key findings

### 1. The backend gap is real in direction, unsettled in size

Same model, same machine, `tg128`:

| Backend | Build | t/s | ± |
|---|---|---:|---:|
| Vulkan | `f872b5911 (11310)` | **25.31** | 0.75 |
| ROCm | `unknown (0)` | **10.89** | 1.61 |

![Decode throughput by backend and context depth](docs/figures/backend-depth.svg)

Three things stop this from being a clean 2.3x:

1. **Different builds.** The Vulkan binary reports commit `f872b5911`; the ROCm
   binary reports `unknown (0)`. Same source tree, not the same binary.
2. **Different memory configuration.** The ROCm log's "15,438 MiB VRAM" is the
   GTT/UMA aperture, not a dedicated carve-out. The carve-out records for the
   same day disagree (512 MiB vs 16 GiB).
3. **Non-monotonic ROCm series.** Throughput goes 10.89 → 12.63 → 7.84 t/s as
   depth grows. Depth 0 should not be the slowest point. A separate ROCm server
   baseline reached 18.17 t/s, so 10.89 is a lower bound.

**What survives:** the direction, and a range. See
[`docs/limitations.md`](docs/limitations.md).

### 2. MTP helps; DFlash2 probably helps

Vulkan, 32K capacity, 256-token outputs, 3 prompts × 3 rounds, paired by
(prompt, round):

| Mode | Median generation t/s | Paired speedup vs baseline | 95% CI |
|---|---:|---:|---|
| Baseline | 23.78 | 1.00x | — |
| DFlash2, 6 drafts | 31.02 | 1.28x | 1.00–1.56 |
| MTP-off | 25.90 | 1.07x | 1.05–1.10 |
| MTP, 2 drafts | **36.27** | **1.51x** | **1.37–1.63** |

![Speculative decoding medians with 95% confidence intervals](docs/figures/speculative.svg)

The intervals are the result. MTP clears 1.00 comfortably; DFlash2 does not.
The per-cell DFlash2 range is 0.94–1.69, which is consistent with "helps on some
prompts, not others" rather than "a uniform 28% gain".

### 3. The roofline says the bottleneck is not only bytes

A first-order model — active weights plus attention KV per token — puts Vulkan
at 39.5 GB/s effective at depth 0, and 40.6 GB/s at 64K, against an assumed
120 GB/s peak:

![Effective bandwidth against the assumed 120 GB/s peak](docs/figures/roofline.svg)

The flatness is the interesting part. Token rate falls with depth, but the KV
term grows almost exactly enough to keep effective bandwidth near 40 GB/s. That
is consistent with a fixed per-token budget being spent on something the model
does not count: dequantization, expert routing, occupancy, synchronization.
Five hypotheses, each with a test, are in
[`analysis/roofline.md`](analysis/roofline.md). None is confirmed.

> The model is hybrid: 10 full-attention layers and 30 SSM/recurrent layers.
> The attention KV cache is 20,480 bytes/token, roughly half what a naive
> 40-layer transformer would imply. The 30 SSM layers' 1,067.81 MiB state is not
> modeled per token, which is the largest gap in the estimate.

## Hardware

| Component | Value |
|---|---|
| CPU | AMD Ryzen AI 9 HX 375, 12C/24T, 24 MiB L3 |
| iGPU | Radeon 890M, `gfx1150`, RADV STRIX1, Mesa 26.0.8 |
| Memory | 32 GB LPDDR5X (30 GiB visible); exact speed not recorded |
| VRAM | 512 MiB dedicated + 15.08 GiB GTT current; 16 GiB note conflicts |
| Kernel | `7.0.0-42-generic` current; archived runs on `7.0.0-38-generic` |
| NPU | `amdxdna` loaded, `/dev/accel/accel0` present; **unused** |
| llama.cpp | `f872b591121761ac7b2af18283bd99bdc092a63a` |

Full detail, including the carve-out conflict and the binary hashes:
[`docs/hardware.md`](docs/hardware.md).

## Reproduce it

Model weights are not included. The headline needs the exact target:

- `Qwen3.6-35B-A3B-UD-IQ4_NL.gguf`
- 18,040,888,288 bytes
- SHA256 `0d17e255dc257a11f398ed4bc8d62412d8ce9ca24b3fce2947d962e4bfed5758`

```bash
export LLAMA_BENCH=$HOME/llama.cpp/build-vulkan/bin/llama-bench
export MODEL=$HOME/models/Qwen3.6-35B-A3B-UD-IQ4_NL.gguf
export LLAMA_CPP=$HOME/llama.cpp

./scripts/bench.sh --backend vulkan --llama-cpp "$LLAMA_CPP"
python3 scripts/parse_logs.py
python3 scripts/roofline.py
python3 scripts/verify_results.py
```

`bench.sh` runs one `llama-bench` invocation per depth with
`-ngl 999 -fa on -t 12 -b 2048 -ub 512 -p 0 -n 128 -r 2`, and records the
command, model hash, binary hash, `llama-bench --version`, `lscpu`, and
`free -h` beside the output.

Short harness check with a 4 GiB model:

```bash
LLAMA_BENCH=$HOME/llama.cpp/build-vulkan/bin/llama-bench \
MODEL=$HOME/models/LFM2.5-8B-A1B/LFM2.5-8B-A1B-UD-IQ4_NL.gguf \
./scripts/bench.sh --backend vulkan --depths 0 --reps 1
```

Step-by-step, with the failure modes ordered by how often they bite:
[`docs/reproduction-checklist.md`](docs/reproduction-checklist.md).

## What is in here

| Path | What it is |
|---|---|
| `README.md` | This file: findings, hardware, reproduction |
| `RESULTS.md` | Every table, one row per run, each with a source |
| `docs/methodology.md` | Exact flags, repetitions, warmup, protocols |
| `docs/hardware.md` | CPU, iGPU, RAM, VRAM, kernel, drivers, model architecture |
| `docs/limitations.md` | Confounds, missing data, what would close each gap |
| `docs/glossary.md` | tg128, GTT, A3B, KV cache, draft acceptance, and the rest |
| `docs/faq.md` | Troubleshooting and interpretation |
| `docs/references.md` | What is cited, and what is deliberately not |
| `docs/reproduction-checklist.md` | Preflight → run → compare → publish |
| `docs/privacy.md` | Redaction log and secret-scan results |
| `docs/figures/` | Generated SVG figures, no plotting dependency |
| `CONTRIBUTING.md` | How to add a run without breaking the provenance chain |
| `Makefile` | `make data`, `make figures`, `make check` |
| `.github/workflows/checks.yml` | CI: regenerate, verify, scan, fail on drift |
| `data/raw/` | Sanitised original logs and historical records |
| `data/processed/` | CSV/JSON parsed from the raw files |
| `data/processed/runs-index.csv` | One row per reported run: experiment, backend, metric, value, n, source |
| `data/provenance.md` | File → source → date → transformation |
| `scripts/bench.sh` | Reproducible `llama-bench` wrapper |
| `scripts/parse_logs.py` | Raw logs → CSV |
| `scripts/roofline.py` | First-order bandwidth model |
| `scripts/stats.py` | Paired ratios and bootstrap confidence intervals |
| `scripts/chart.py` | Data → dependency-free SVG |
| `scripts/verify_results.py` | Fails if the docs disagree with the data |
| `scripts/secret_scan.py` | Privacy and credential scan |
| `analysis/roofline.md` | The written roofline argument and its hypotheses |
| `docker/rocm-ubuntu26.04.Dockerfile` | Archived ROCm build recipe |

## What this is not

- **Not a hardware review.** One machine, one iGPU, one model family.
- **Not a controlled A/B** for the backend comparison. Builds and memory
  configuration differ; the ROCm runtime is gone.
- **Not a leaderboard.** The secondary experiments use different protocols and
  are not comparable to each other.
- **Not reproducible end-to-end today.** The target and draft GGUFs are absent
  from the source machine; sizes and hashes are recorded so a re-download can be
  checked.
- **Not statistically strong.** Nine paired cells per mode. The intervals are
  reported because they are wide, not because they are tight.

## Open questions

Ranked by what would most change the conclusion:

1. **A controlled backend A/B** — same build, same carve-out, alternating order,
   ≥5 repetitions. This is the single highest-value experiment.
2. **Wall power and locked clocks** — the archived runs have partial sensors for
   one Vulkan configuration (91–94 °C, 45–52 W) and none for ROCm.
3. **A quantization sweep** (IQ4_XS, Q5_K_M, Q8_0) to test whether the gap is
   dequantization.
4. **A dense-model control** to test whether expert routing explains the gap.
5. **A filled 61K baseline**, not only speculative modes.
6. **A second machine**, ideally another Strix Point laptop.
7. **The NPU path** — `amdxdna` and `/dev/accel/accel0` are present and unused.

## Verifying the numbers

```bash
python3 scripts/verify_results.py
```

This checks that every headline number in this file and in `RESULTS.md` appears
in the generated CSVs/JSON, and that known stale values are gone. It exits
non-zero on failure, so it can run in CI. It is the mechanism behind the claim
that every number here traces to a file.

## Licence and privacy

Code (shell, Python, Dockerfile) is MIT — [`LICENSE`](LICENSE).
Text, tables, logs, CSV, and JSON are CC BY 4.0 — [`LICENSE-DATA`](LICENSE-DATA).
Model weights are not included and keep their own licences.

The repository is private. It contains no weights, tokens, keys, emails, MAC
addresses, serial numbers, or personal names; paths and hostnames were redacted.
The log is in [`docs/privacy.md`](docs/privacy.md).

Citation metadata is in [`CITATION.cff`](CITATION.cff). Changes are in
[`CHANGELOG.md`](CHANGELOG.md).
