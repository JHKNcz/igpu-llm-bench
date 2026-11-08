# Vulkan speculative-decoding comparison

*Source: `~/LLM/testing_resources/speculative_compare/results/20261018-200821-488233/`,
started 2026-10-18T18:08:21Z. The harness itself is not included; the summary and
measurements are. This is a separate experiment from the ROCm vs Vulkan
`llama-bench` comparison.*

## Method

| Setting | Value |
|---|---|
| Backend | Vulkan, build `f872b5911 (11310)` |
| Context capacity | 32,768 tokens |
| GPU layers | 99 |
| Flash attention | on |
| Slots | 1 |
| Thinking | disabled |
| Automatic fit | disabled |
| Prompt-cache reuse | disabled |
| Sampling | greedy |
| Output | exactly 256 tokens per request; EOS ignored |
| Prompts | 3 synthetic prompts: stock fundamentals, Python portfolio analysis, structured earnings extraction |
| Rounds | 3, rotating mode order |
| Warmup | 64 unmeasured tokens after loading |
| Modes | baseline, DFlash2 (6 draft tokens), MTP-off, MTP (2 draft tokens) |
| Samples | 9 measured requests per mode |

The MTP-off control uses the MTP-capable weights with speculation disabled, so
the MTP-on vs MTP-off pair isolates speculative acceleration from a weight-file
difference. The DFlash2 pair uses the same regular target with the draft model
enabled or disabled.

## Results

| Mode | Median generation t/s | 95% CI of median | Paired vs baseline | 95% CI | Paired vs MTP-off |
|---|---:|---|---:|---|---:|
| Baseline (regular target, no draft) | 23.78 | 22.29–25.66 | 1.00x | — | 0.93x |
| DFlash2, 6 draft tokens | 31.02 | 23.98–37.74 | 1.28x | 1.00–1.56 | 1.25x |
| MTP-off (MTP weights, speculation off) | 25.90 | 24.38–27.25 | 1.07x | 1.05–1.10 | 1.00x |
| MTP, 2 draft tokens | **36.27** | 32.78–37.42 | **1.51x** | **1.37–1.63** | **1.37x** |

Ratios are computed inside each (prompt, round) cell and then summarised across
the 9 cells. Intervals are a 20,000-sample percentile bootstrap, seeded.
Regenerate with `python3 scripts/stats.py`.

### Per-prompt medians

| Prompt | Baseline | DFlash2 | MTP-off | MTP |
|---|---:|---:|---:|---:|
| Stock fundamentals | 23.78 | 23.98 | 25.93 | 32.78 |
| Python portfolio analysis | 24.26 | 31.02 | 25.90 | 36.37 |
| Structured earnings extraction | 23.49 | 37.74 | 24.75 | 37.42 |

The DFlash2 gain is prompt-dependent: essentially flat on the stock prompt and
large on the structured-extraction prompt. MTP is faster than baseline on all
three prompts in this sample.

## Caveats

- Generation tokens/second, not total request time, and not answer quality.
- Three short synthetic prompts; this does not measure a filled 32K context.
- Three rounds; the samples are not independent across prompts.
- One machine, one Vulkan build, no power or clock control.
- **DFlash2 is not established at n=9.** The point estimate is 1.28x, but the
  interval touches 1.00 and the per-cell range is 0.94–1.69. Report it as
  "probably faster, not proven". MTP is the result that survives.
- The 1.28x here is not the same workload as the 1.65x short-prompt Vulkan note
  or the 1.51x coding-agent result. Do not average them.
- The baseline 23.78 t/s is within 6% of the independent `llama-bench` Vulkan
  `tg128` result (25.31 t/s), which cross-validates the baseline roughly, not
  exactly.
