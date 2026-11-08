# Qwen local optimization results - 2 October 2026

*Historical source document. Scripts referenced here are not included in this
repository; the benchmark data and caveats are.*

Post-reboot update: see [Vulkan results and the new launcher](2026-10-02-vulkan-post-reboot.md). This document preserves the earlier ROCm session and pre-reboot Vulkan status.

New measurements on the AMD Ryzen AI 9 HX 375 / Radeon 890M. Historical evidence files and their claims are preserved separately. All rates below are measured on this machine.

## Main finding

Disabling HIP/CUDA graph execution with `GGML_CUDA_DISABLE_GRAPHS=1` restored DFlash2 GPU draft acceptance in the existing ROCm build. This is a tested runtime workaround; the precise graph or kernel defect has not been isolated.

The selected DFlash2 performance configuration uses draft offload `all`, maximum draft tokens `7`, target offload 999, flash attention on, and 16K context capacity. The selection is based on the largest observed median. Power and temperatures varied, so close rankings should not be treated as settled.

- `01c-rocm-baseline-no-graphs`: median **18.17 output tokens/s** end to end; range 18.02-24.51; median decode 18.38 tokens/s.
- `03c-rocm-dflash2-cpu-no-graphs`: median **29.56 output tokens/s** end to end; range 24.69-29.66; median decode 30.22 tokens/s; acceptance 57.55%.
- `04-rocm-dflash2-gpu`: median **7.19 output tokens/s** end to end; range 6.27-7.42; median decode 7.23 tokens/s; acceptance 0.45%.
- `04b-rocm-dflash2-gpu-no-graphs`: median **33.84 output tokens/s** end to end; range 26.77-38.83; median decode 35.39 tokens/s; acceptance 58.43%.
- `07-rocm-nmax-7-no-graphs`: median **27.47 output tokens/s** end to end; range 26.96-30.72; median decode 28.05 tokens/s; acceptance 58.43%.
- `11-rocm-baseline-confirmation`: median **21.26 output tokens/s** end to end; range 18.52-23.54; median decode 21.49 tokens/s.
- `11-rocm-dflash2-confirmation`: median **30.32 output tokens/s** end to end; range 29.89-30.63; median decode 31.01 tokens/s; acceptance 58.43%.
- `12-rocm-dflash1-gpu-no-graphs-n7`: median **26.08 output tokens/s** end to end; range 25.94-28.91; median decode 26.48 tokens/s; acceptance 54.28%.
- `12-rocm-dflash1-gpu-no-graphs-n15`: median **28.62 output tokens/s** end to end; range 27.36-31.40; median decode 29.37 tokens/s; acceptance 34.43%.

In the fresh back-to-back 16K confirmation pair, DFlash2's median end-to-end rate was 1.43x the no-draft baseline. This ratio applies to this short-prompt protocol and this pair, not all workloads.

## Correctness and limits

HTTP success and completed inference are reported as PASS in the performance results. They are not general correctness or quality certifications.

The 512-token thinking-on outputs are not byte-identical across all runs or across baseline and drafting. Even baseline repetitions differ: the first measured answer and later answers can take different reasoning paths. Disabling GPU graphs fixed the dramatic GPU draft acceptance collapse, but did not establish losslessness for this quantized target and runtime.

The main throughput prompt has 35 evaluated tokens, no prompt-cache reuse, and a 512-token generation limit. These outputs commonly stop during reasoning, before a completed user-facing answer. Context sweeps change allocated capacity only; they do not measure full 8K-64K prompts.

Completed configurations: 39 total, 36 successful inference runs and 3 loading failures. Each successful configuration has three measured requests plus its separate warm-up.

A separate thinking-off code task produced 6/6 responses passing four executable binary-tree cases per response (empty, singleton, balanced and asymmetric trees). Generated code is inspected with a restrictive AST allowlist before execution. See `code-correctness.json` for individual outcomes. This is a narrow task check, not a general evaluation.

For the first measured correctness pair, message content exact match: False. Reasoning was disabled. The baseline used a nested helper and the draft-enabled answer used direct recursive concatenation; both passed the four tree cases.

## Vulkan and the linked models

The initial Vulkan full-offload attempt failed while loading the target: `radv/amdgpu: Not enough memory for command submission`, followed by `ErrorDeviceLost`. No Vulkan throughput was recorded. Vulkan testing was deferred when the operator said a reboot and a 16 GB VRAM setting were required. The driver had reported 15,950 MiB; the target file is 16.79 GiB, and runtime buffers add memory. Recheck after reboot and measure any reduced-offload configuration separately.

[DFlash](https://huggingface.co/z-lab/Qwen3.6-35B-A3B-DFlash) and [DFlash2](https://huggingface.co/incoai/Qwen3.6-35B-A3B-DFlash2) are draft models paired with the Qwen target. Their published NVIDIA benchmarks are not measurements of this AMD APU.

[Splash](https://huggingface.co/incoai/Qwen3.6-35B-A3B-Splash) uses an Apple-specific package and engine. Its card requires Apple M3 or newer and macOS 26.4 or later, so it was not downloaded or tested here.

## Reproduction and provenance

- Target: `<models>/Qwen3.6-35B-A3B-UD-IQ4_NL.gguf`.
- Draft: the existing DFlash2 BF16 GGUF; logs confirm block size 8, convolution kernel 2, group 16, selector rank 256, top-k 16.
- Existing container: `[container]`, image identifier recorded in the original source bundle (not included); HIP compiler/runtime identifier from `hipconfig --version`: `7.15.26333-0000000`.
- Repository HEAD: `f872b591121761ac7b2af18283bd99bdc092a63a`, clean at preflight. ROCm executable reports build 0 / unknown commit, GNU 13.3.0; Vulkan executable reports build 11310 / f872b5911, GNU 15.2.0. Source identity alone does not prove binary provenance.
- Model and binary checksums, CMake caches, exact command arrays, per-request JSON, response JSON, complete server logs and metrics are saved in the original source bundle under `runs/2026-10-02-qwen/` (not included).
- Each performance configuration uses one 64-token warm-up followed by three independent 512-token requests; greedy sampling, seed 42, thinking on, cache off, one slot. Warm-up is excluded from medians and acceptance aggregates.
- Initial baseline `01-rocm-baseline` overlapped with model checksumming during later requests. Clean repeat baselines were recorded and should be preferred.
- Temperature and power readings were added after the initial runs. Frequencies, power limits and background system activity were not locked, and observed throughput varies substantially.

Start the saved DFlash2 configuration after testing or reboot with:

```bash
python3 <llm-root>/testing_resources/start_optimized_qwen.py
```

*The launcher script is not included.*

It starts a localhost server on port 8080 in the existing running container. Use `--reasoning off` for immediate answers, `--baseline` for no drafting, or `--port` / `--context` to change serving limits. The benchmark protocol uses a separate port 18080 and disables prompt caching; the interactive launcher retains normal prompt caching.

The launcher was smoke-tested on port 18082 with reasoning off. It became ready and returned exactly `OK` for the short test request. It was then stopped. No benchmark or smoke-test server was intentionally left running.

Resume saved ROCm tests with `run_qwen_sweep.py`. Completed configurations are skipped; incomplete ones are rerun. After reboot, use `run_qwen_vulkan_after_reboot.py` for a new Vulkan baseline and draft pair; it preserves the initial failures. Avoid starting a second runner while the first is still active. *These historical scripts are not included.*

## All completed configurations

- `01-rocm-baseline`: 22.40 end-to-end tokens/s median (14.68-24.76); context 16384; reasoning on; output tokens 512-512.
- `01b-rocm-baseline-clean`: 17.93 end-to-end tokens/s median (14.74-21.92); context 16384; reasoning on; output tokens 512-512.
- `01c-rocm-baseline-no-graphs`: 18.17 end-to-end tokens/s median (18.02-24.51); context 16384; reasoning on; output tokens 512-512.
- `02-vulkan-baseline`: ERROR, server exited 1; no rate recorded.
- `03-rocm-dflash2-cpu`: 32.62 end-to-end tokens/s median (28.46-34.88); context 16384; reasoning on; output tokens 512-512; draft acceptance 57.55%.
- `03b-rocm-dflash2-cpu-clean`: 19.50 end-to-end tokens/s median (18.72-26.94); context 16384; reasoning on; output tokens 512-512; draft acceptance 57.55%.
- `03c-rocm-dflash2-cpu-no-graphs`: 29.56 end-to-end tokens/s median (24.69-29.66); context 16384; reasoning on; output tokens 512-512; draft acceptance 57.55%.
- `04-rocm-dflash2-gpu`: 7.19 end-to-end tokens/s median (6.27-7.42); context 16384; reasoning on; output tokens 512-512; draft acceptance 0.45%.
- `04b-rocm-dflash2-gpu-no-graphs`: 33.84 end-to-end tokens/s median (26.77-38.83); context 16384; reasoning on; output tokens 512-512; draft acceptance 58.43%.
- `05-vulkan-dflash2-gpu`: ERROR, server exited 1; no rate recorded.
- `05b-vulkan-dflash2-cpu`: ERROR, server exited 1; no rate recorded.
- `05c-rocm-dflash1-cpu`: 20.78 end-to-end tokens/s median (18.74-21.01); context 16384; reasoning on; output tokens 512-512; draft acceptance 57.37%.
- `06-rocm-ngld-1-no-graphs`: 22.43 end-to-end tokens/s median (21.02-28.36); context 16384; reasoning on; output tokens 512-512; draft acceptance 54.30%.
- `06-rocm-ngld-2-no-graphs`: 20.18 end-to-end tokens/s median (15.82-37.81); context 16384; reasoning on; output tokens 512-512; draft acceptance 57.21%.
- `06-rocm-ngld-3-no-graphs`: 18.61 end-to-end tokens/s median (15.52-21.20); context 16384; reasoning on; output tokens 512-512; draft acceptance 54.08%.
- `06-rocm-ngld-4-no-graphs`: 24.63 end-to-end tokens/s median (21.42-35.58); context 16384; reasoning on; output tokens 512-512; draft acceptance 57.55%.
- `06-rocm-ngld-5-no-graphs`: 20.41 end-to-end tokens/s median (20.36-29.71); context 16384; reasoning on; output tokens 512-512; draft acceptance 54.08%.
- `06-rocm-ngld-6-no-graphs`: 19.34 end-to-end tokens/s median (18.78-20.92); context 16384; reasoning on; output tokens 512-512; draft acceptance 58.08%.
- `07-rocm-nmax-1-no-graphs`: 14.57 end-to-end tokens/s median (12.65-17.44); context 16384; reasoning on; output tokens 512-512; draft acceptance 93.92%.
- `07-rocm-nmax-2-no-graphs`: 16.47 end-to-end tokens/s median (13.87-27.16); context 16384; reasoning on; output tokens 512-512; draft acceptance 92.19%.
- `07-rocm-nmax-3-no-graphs`: 18.27 end-to-end tokens/s median (17.23-21.57); context 16384; reasoning on; output tokens 512-512; draft acceptance 82.79%.
- `07-rocm-nmax-4-no-graphs`: 20.14 end-to-end tokens/s median (18.77-23.41); context 16384; reasoning on; output tokens 512-512; draft acceptance 84.18%.
- `07-rocm-nmax-5-no-graphs`: 24.63 end-to-end tokens/s median (16.28-24.96); context 16384; reasoning on; output tokens 512-512; draft acceptance 81.74%.
- `07-rocm-nmax-6-no-graphs`: 24.27 end-to-end tokens/s median (19.72-25.95); context 16384; reasoning on; output tokens 512-512; draft acceptance 54.69%.
- `07-rocm-nmax-7-no-graphs`: 27.47 end-to-end tokens/s median (26.96-30.72); context 16384; reasoning on; output tokens 512-512; draft acceptance 58.43%.
- `08-rocm-baseline-16384-no-graphs`: 19.63 end-to-end tokens/s median (19.37-20.57); context 16384; reasoning on; output tokens 512-512.
- `08-rocm-baseline-32768-no-graphs`: 22.43 end-to-end tokens/s median (21.66-22.62); context 32768; reasoning on; output tokens 512-512.
- `08-rocm-baseline-65536-no-graphs`: 18.20 end-to-end tokens/s median (17.99-21.21); context 65536; reasoning on; output tokens 512-512.
- `08-rocm-baseline-8192-no-graphs`: 21.71 end-to-end tokens/s median (20.73-21.71); context 8192; reasoning on; output tokens 512-512.
- `09-rocm-dflash2-16384-no-graphs`: 26.53 end-to-end tokens/s median (24.80-26.77); context 16384; reasoning on; output tokens 512-512; draft acceptance 58.43%.
- `09-rocm-dflash2-32768-no-graphs`: 21.35 end-to-end tokens/s median (20.54-23.07); context 32768; reasoning on; output tokens 512-512; draft acceptance 58.43%.
- `09-rocm-dflash2-65536-no-graphs`: 22.34 end-to-end tokens/s median (20.85-24.07); context 65536; reasoning on; output tokens 512-512; draft acceptance 58.43%.
- `09-rocm-dflash2-8192-no-graphs`: 35.08 end-to-end tokens/s median (31.69-37.14); context 8192; reasoning on; output tokens 512-512; draft acceptance 58.43%.
- `10-rocm-baseline-correctness`: 17.90 end-to-end tokens/s median (16.00-18.41); context 16384; reasoning off; output tokens 69-69.
- `10-rocm-dflash2-correctness`: 26.77 end-to-end tokens/s median (23.94-37.77); context 16384; reasoning off; output tokens 38-38; draft acceptance 91.43%.
- `11-rocm-baseline-confirmation`: 21.26 end-to-end tokens/s median (18.52-23.54); context 16384; reasoning on; output tokens 512-512.
- `11-rocm-dflash2-confirmation`: 30.32 end-to-end tokens/s median (29.89-30.63); context 16384; reasoning on; output tokens 512-512; draft acceptance 58.43%.
- `12-rocm-dflash1-gpu-no-graphs-n15`: 28.62 end-to-end tokens/s median (27.36-31.40); context 16384; reasoning on; output tokens 512-512; draft acceptance 34.43%.
- `12-rocm-dflash1-gpu-no-graphs-n7`: 26.08 end-to-end tokens/s median (25.94-28.91); context 16384; reasoning on; output tokens 512-512; draft acceptance 54.28%.
