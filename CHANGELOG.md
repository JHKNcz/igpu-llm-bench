# Changelog

All notable changes to this repository. Dates are UTC unless stated.

## 2026-11-12 — 16 GB carve-out campaign

Measured at index 7 (16,384 MiB VRAM, 7,638 MiB GTT, 15,277 MiB host).

- **The 35B runs on Vulkan at 16 GB: 25.24 t/s at depth 0, 21.33 at 16K** — the
  best 35B result in the repository. At 0.5 GB it cannot load at all.
- Small models decode 1.4–3.0x faster at 16 GB. Prefill at 64K is 0.56–0.61x
  slower, and the GPU reached 99 °C; the comparison is thermally confounded.
- ROCm at 16 GB cannot fully offload the 35B; `-ngl 22` gives 5.00 t/s.
- CPU 35B drops from 18.38 to 13.78 t/s because host RAM falls to 15.3 GiB.
- Loading the 35B on Vulkan is **not deterministic under desktop load**: an
  idle repeat loads at `-ngl 999`, and the sweep is non-monotonic (`-ngl 28`
  loads, `-ngl 22` fails).
- Added `scripts/compare_carveouts.py`, `make carveouts`, and carve-out index
  and label in every campaign row.

## 2026-11-12 — Carve-out is settable from Linux

- **Corrected a claim.** The VRAM carve-out is not BIOS-only. On kernel
  7.0.0-43 it is writable at
  `/sys/class/drm/card*/device/uma/carveout` (index 0–7) and through
  `amd-smi set -g 0 -m <index>`.
- Confirmed 16 GB: index 7, VRAM 16,384 MiB, GTT 7,638 MiB, host 15,277 MiB,
  GPU-addressable 24,022 MiB. It survives a reboot via
  `UmaCarveOutIndexDefault`.
- Recorded the two traps: the GPU is `card1` (not `card0`) and index 8 is
  invalid.
- Added `scripts/carveout.sh` (`--show`, `--set-gb`, `--set-index`, `--gtt-gb`).
- GTT commands are documented but **unverified**; the write needs interactive
  sudo and has not been run on this machine yet.

## 2026-11-10 — Randomised replication, CPU baselines, corrections

Three new suites, all at the unchanged 512 MiB carve-out.

- **The earlier depth-0 conclusion did not replicate.** A fixed-order session had
  Vulkan at 35.12 t/s; six randomised repetitions give a median of 23.97 and a
  range of 18.66–35.19. The single value was an upper-tail sample.
- **ROCm is the most consistent GPU backend.** It beats Vulkan at every depth
  (1.28x at depth 0, 1.60x at 16K) and wins all three randomised rounds at 16K.
- **The CPU is fastest at short context for every model tested**, including the
  35B (18.38 vs 17.66 t/s on ROCm). Prefill is the opposite: 1,025 t/s on Vulkan
  vs 264 on CPU.
- **Quantization re-measured interleaved.** IQ4 carries 2.15x fewer bytes than Q8
  but is only 1.41x–1.92x faster depending on backend; Q8 reaches higher
  effective bandwidth everywhere. The 4-bit path pays a dequantization cost.
- **Corrected the runtime identity again:** the measured runtime is **ROCm
  10.0.0**. The `10.0.0-full` and `latest` tags resolve to the same image ID;
  HIP 7.15.26333 is the HIP version inside ROCm 10.0.0, not a ROCm version.
- Added `ab_campaign.py` (shuffled rounds, three backends), `order_effects.py`,
  `ab_summary`-style tables, a CPU-only build recipe, and `FINDINGS.md`.

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
- **Corrected** an earlier misreading: the measured runtime is **ROCm 10.0.0**,
  not "HIP 7.15". The `10.0.0-full` and `latest` tags resolve to the same image
  ID; 7.15 is the HIP version bundled inside ROCm 10.0.0.

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
