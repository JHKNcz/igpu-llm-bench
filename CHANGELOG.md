# Changelog

All notable changes to this repository. Dates are UTC unless stated.

## 2026-11-10 — Controlled backend comparison

New measurements, no carve-out change (512 MiB throughout).

- **New primary result.** Ran Vulkan and ROCm under the same carve-out, flags,
  models, and depths. On a 4 GiB MoE model Vulkan is 1.27x–1.42x faster at every
  depth. On an 8.7 GiB model of the same architecture the ranking reverses:
  Vulkan 1.37x at depth 0, ROCm 1.23x at 16K and 2.03x at 64K.
- **The 35B runs on ROCm at 512 MiB** (17.66 t/s at depth 0, 14.54 at 16K) via
  unified memory; GPU activity verified with `gpu_busy_percent`. Vulkan cannot
  load it: budget ~14.5 GiB vs 17.25 GiB model.
- **Roofline finding.** IQ4 moves half the bytes of Q8 for the same model but is
  only ~20% faster, so effective bandwidth halves (22.5 vs 38.7 GB/s). The IQ4
  path is dequantization-bound, not bandwidth-bound.
- **Archived 2.32x demoted** to a cross-setting observation, because no single
  carve-out lets both backends fully offload the 35B.
- Added `campaign.py`, `capacity_probe.py`, `compare_backends.py`,
  `roofline_campaign.py`, `campaign_summary.py`, `reparse_campaign.py`, a
  crossover figure, and a CPU-fallback guard (HIP silently ran on CPU when
  `/dev/kfd` was missing).
- Recorded that the measured ROCm is **HIP 7.15**, proven by image-ID match,
  not ROCm 10.

## 2026-11-08 — Carve-out correction

Analysis of existing logs; no new measurements.

- **Corrected a misdiagnosis.** The 512 MiB and 16 GiB records were logged as
  contradictory. They are two BIOS settings, both used, and both are correct.
  Added `data/raw/historical/carveout-states-2026-10-02.json` and the primary
  ROCm load-failure log.
- **New finding:** at the 16 GB carve-out the target's 16,679.34 MiB weight
  buffer exceeds the 16,384 MiB pool, so ROCm cannot fully offload the model,
  while Vulkan can. At 0.5 GB ROCm loads it via unified memory into 30 GiB of
  host RAM. The carve-out decides what can run, not only how fast.
- Recorded the operator-confirmed 24,022 MiB GPU-addressable figure for the
  16 GB setting, and the ~15.5 GiB host-RAM cost of raising it.
- `verify_results.py` now checks the carve-out arithmetic and fails with a
  non-zero exit (a latent `NameError` in the failure path was also fixed).

## 2026-11-08 — Research presentation pass

Documentation and analysis, no new measurements.

- Added paired statistics with bootstrap confidence intervals
  (`scripts/stats.py`, `data/processed/speculative-stats.json`).
- **Corrected a claim.** The DFlash2 speedup is reported as marginal: 1.28x with
  a 95% CI of 1.00–1.56, not a solid 1.28x. MTP remains a clear win at 1.51x
  (1.37–1.63).
- Added three dependency-free SVG figures (`scripts/chart.py`,
  `docs/figures/`).
- Added `scripts/verify_results.py`, which checks headline numbers against the
  generated data and rejects known stale values.
- Added `docs/glossary.md`, `docs/faq.md`, `docs/references.md`,
  `docs/reproduction-checklist.md`, `CONTRIBUTING.md`, `CITATION.cff`.
- Restructured `README.md` around findings, reproduction, and limitations.
- Added a `Makefile` and a CI job that regenerates the data, verifies the docs,
  scans for secrets, and fails if regeneration produces a diff.

## 2026-11-05 — Initial publication

First private release of the consolidated artifacts.

- 44 files: raw logs, parsed CSV/JSON, provenance, methodology, hardware,
  limitations, privacy, scripts, roofline analysis, Dockerfile.
- Headline: Vulkan 25.31 t/s vs ROCm 10.89 t/s at `tg128`, raw ratio 2.32x,
  qualified to a defensible 1.4x–2.3x.
- **Corrected** the KV model: the target is a hybrid 10-attention / 30-SSM
  model, so the attention KV cache is 20,480 bytes/token, not 40,960. The
  roofline and every dependent number were regenerated.
- **Corrected** the memory interpretation: the ROCm log's 15,438 MiB is the
  GTT/UMA aperture, not a 15.4 GB dedicated carve-out.
- Sanitised all copied files; 44 text files scanned, 0 unallowlisted matches.
