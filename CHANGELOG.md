# Changelog

All notable changes to this repository. Dates are UTC unless stated.

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
