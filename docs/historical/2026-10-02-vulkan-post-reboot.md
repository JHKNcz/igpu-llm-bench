# Vulkan results after the 16 GiB VRAM reboot

*Historical source document. The memory note below conflicts with a JSON recorded at 15:31 the same day (512 MiB VRAM / 15.08 GiB GTT); see `docs/hardware.md`. The GGUFs and scripts referenced here are not included.*

2026-10-02 (local time, UTC+2). New results are stored under run names containing `20261002-160806`; earlier ROCm and pre-reboot Vulkan records are preserved.

## Result

The fastest observed Vulkan configuration was DFlash2 with all draft layers on the GPU and 6 draft tokens: **42.20 output tokens/s** end to end, versus **25.63** without drafting (1.65x, 64.6% faster). This is the short-prompt benchmark, not a general workload guarantee.

## Measured comparison

- `02r-vulkan-after-reboot-20261002-160806-ngl999`: median 25.63 output tokens/s, range 25.58-26.01.
- `05r-vulkan-after-reboot-20261002-160806-cpu-ngl999`: median 35.62 output tokens/s, range 35.45-37.23; acceptance 65.78%.
- `05r-vulkan-after-reboot-20261002-160806-gpu-ngl999`: median 40.81 output tokens/s, range 40.32-41.21; acceptance 65.78%.
- `14-vulkan-post-reboot-20261002-160806-nmax5`: median 41.23 output tokens/s, range 40.22-41.33; acceptance 78.47%.
- `14-vulkan-post-reboot-20261002-160806-nmax6`: median 42.20 output tokens/s, range 37.98-43.14; acceptance 72.74%.

## Correctness and limits

Completed-code test: 6/6 responses passed four executable tree cases each. Reasoning was disabled for this complete-answer task. Exact code text match in the first baseline/draft pair: True.

The main thinking-on throughput responses differed between the baseline and draft-enabled runs. CPU and GPU drafting with seven draft tokens produced matching messages in corresponding repetitions, but this does not prove general losslessness for the quantized target and runtime.

Every performance configuration used one 64-token warm-up and three 512-token measured requests, the same 35-token prompt, 16K context capacity, temperature 0, seed 42, one slot and prompt caching disabled. Medians exclude warm-up; acceptance aggregates only the measured requests. The benchmark commonly reaches its output limit during reasoning. No filled long-context benchmark was added in this stage.

Five-, six- and seven-token draft settings are close in throughput. Power, temperatures and background activity were not locked; the small ranking differences may include normal variation. Six is the fastest observed, not a settled universal optimum.

The earlier ROCm result was measured before the reboot with a different memory allocation. It is historical context, not a controlled backend comparison under the new settings.

## Memory and setup

The kernel reports exactly 16 GiB reserved VRAM and approximately 7.46 GiB GTT/shared graphics memory. Vulkan reports 24,022 MiB total budget and 22,996 MiB free before the run. Host-visible RAM is approximately 14 GiB after the reservation. Full target offload now loads successfully with default Vulkan memory behavior; the pre-reboot memory failures remain archived.

The target is the existing Qwen3.6-35B-A3B UD-IQ4_NL GGUF; the draft is the existing DFlash2 BF16 GGUF. No model download or rebuild was required. *The GGUFs are not included in this repository.* The same Vulkan executable and standard batch/thread settings were used throughout.

## Start the tested configuration

```bash
python3 <llm-root>/testing_resources/start_vulkan_qwen.py
```

*The launcher script is not included.*

This starts a localhost OpenAI-compatible server on port 8080 with 16K context, full target/draft GPU offload, the selected draft length, and reasoning enabled. Use `--reasoning off` for immediate answers or `--baseline` to disable drafting. Normal prompt caching is enabled in the interactive launcher.

Launcher verification passed on port 18082: the server became ready and replied exactly `OK` to the short test request. The temporary server was then stopped.

Raw requests, responses, per-run timing, logs and selected configuration are in the original source bundle under `runs/2026-10-02-qwen/` (not included). The reboot preflight and progress logs are in its `post-reboot/` directory.
