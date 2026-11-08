# Limitations

## Scope

This is one machine, one iGPU, one model family, and a small number of archived
runs. It is not a hardware review, a leaderboard, or a universal statement about
Vulkan versus ROCm.

## The headline comparison is not a controlled A/B

The raw `tg128` ratio is **25.31 / 10.89 = 2.32x**, but the runs differ in at
least four ways:

1. **Build.** Vulkan is build `f872b5911 (11310)`; ROCm reports `unknown (0)`.
   The source tree is the same commit, but source identity does not prove binary
   provenance.
2. **Memory carve-out.** The ROCm log’s 15,438 MiB is the UMA/GTT total, not a
   15.4 GB dedicated allocation. Both BIOS settings were used (0.5 GB and
   16 GB), but the two archived `llama-bench` files do not record which one they
   ran under, and the settings differ in both capacity and host RAM.
3. **Runtime.** The ROCm runtime and container image are not available now; the
   exact runtime version is unresolved (Dockerfile says ROCm 10.0; notes mention
   7.2.3/7.15).
4. **Capacity, not just speed.** At the 16 GB carve-out ROCm cannot load this
   model at all; at 0.5 GB it can, via unified memory. A comparison that crosses
   settings is comparing two different feasible configurations, not two
   backends on equal footing.
5. **Protocol.** The original CLI, batch size, clocks, power limit, and
   temperature control were not recorded.

A separate ROCm server baseline reached **18.17 t/s**, so 10.89 is a lower
bound, not a clean backend ratio. ROCm’s own depth series is non-monotonic
(10.89 at depth 0, 12.63 at 16K), which is not the expected shape and suggests
run-to-run noise or a first-run effect. Vulkan is monotonic (25.31 → 19.96 →
13.97).

**Defensible claim:** Vulkan was faster in every archived same-machine
comparison, by roughly **1.4x–2.3x**. The direction is consistent; the exact
size is not settled.

## Replication limits

- No repeated runs across boots. The `±` values are llama-bench’s within-run
  spread over two measured repetitions, not a confidence interval over boots.
- No locked clocks, no fixed power limit, no wall-power measurement. One Vulkan
  configuration recorded 91–94 °C and 45–52 W; the ROCm selected configuration
  has no sensor data.
- The kernel changed after the runs: archived manifests report
  `7.0.0-38-generic`; the current machine is `7.0.0-42-generic`.
- The Mesa/Vulkan driver version at the time of the archived runs is not
  recorded; the current Mesa is 26.0.8.
- The exact RAM type/speed is not recorded. The roofline uses 120 GB/s with
  102.4–128 GB/s sensitivity.

## Missing files and runtime

- The 35B target GGUF and the DFlash2/DFlash1 draft GGUFs are **not on the
  source machine** as of 2026-11-05. Sizes and hashes are recorded, but the
  headline cannot be re-run without downloading/re-converting them.
- `/opt/rocm` is absent and `libhipblas.so.3` is missing, so the archived ROCm
  binary cannot run without a rebuild or the original container.
- The exact archived `llama-bench` CLI and its binary hash were not recorded.

## Secondary experiments are not directly comparable

| Experiment | What it measures | Why it is not comparable |
|---|---|---|
| Speculative comparison | generation t/s, 256-token outputs, 32K capacity | Short prompts; 3 rounds; Vulkan only |
| Long context | generation t/s and retrieval, 4K/32K/61K | 2 rounds; 1 prompt per depth; speculative modes only; no 61K baseline |
| Coding quality | 27 acceptance checks, ROCm | One run per condition; fixed order; harness policy confounds; ROCm only |
| Coding agent | wall TPS, 12 configs | Wall TPS includes prefill/reasoning; one run per config; low pass rates |

The speculative speedups differ by protocol: **1.28x** for DFlash2 in the paired
3-round comparison (95% CI 1.00–1.56, so marginal at n=9), **1.51x** for MTP in
the same comparison (95% CI 1.37–1.63), **1.65x** in the short-prompt Vulkan
note, and **1.51x** in the coding-agent workload. These are different workloads,
not estimates of one number.

The DFlash2 interval touching 1.00 is a limitation of the sample, not evidence
that DFlash2 does nothing. The per-cell range is 0.94–1.69, which is consistent
with a prompt-dependent effect. More prompts and more repetitions would narrow
it; see `docs/related/speculative-decoding.md`.

The coding-quality matrix explicitly says its 2048-token thinking comparison is
confounded by test-freeze policy and tool-protocol overhead. It does not
establish that a 2048-token thinking budget intrinsically reduces quality.

## Roofline limits

The roofline is a first-order model, not a measurement:

- The 3 B active-parameter count is the vendor’s `A3B` label.
- The KV term assumes every token reads the entire F16 attention cache once
  (20,480 bytes/token; 10 attention layers). The 30 SSM layers' 1,067.81 MiB
  recurrent state is not modeled. Flash attention, caching, and the actual
  kernel schedule can change this.
- The peak bandwidth assumes LPDDR5X-7500, 128-bit, 120 GB/s. The exact RAM speed
  is not recorded.
- The model does not include dequantization cost, expert-routing overhead, wave
  occupancy, memory-controller efficiency, or thermal throttling. Those are
  hypotheses, labeled as such in `analysis/roofline.md`.

## Privacy and publication

The repository is private and contains no model weights, no tokens, and no
personal names. The private GitHub owner is visible to anyone with repository
access; the content itself does not name the owner. See `docs/privacy.md`.

## What would strengthen the result

1. Re-run both backends on the same boot, same build, same carve-out, same CLI,
   alternating order, at least five repetitions.
2. Record wall power, package temperature, clocks, and BIOS settings.
3. Rebuild ROCm from the recorded commit and verify the binary hash.
4. Re-download the exact target/draft GGUFs and verify the recorded SHA256.
5. Add a filled 61K baseline (not only speculative modes).
6. Repeat on a second Strix Point laptop.
7. Add an NPU path; `amdxdna` and `/dev/accel/accel0` are present but unused.
