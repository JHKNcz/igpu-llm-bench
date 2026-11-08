# Provenance

Every number in `README.md` and `RESULTS.md` traces to a file in this repository.
That file in turn traces to an original source path, a date, and a transformation.
Dates are the source file's modification time unless the file records a run time.
A modification time is not proof of the run time; where the run time is unknown,
the table says so.

## Included files

| Repository file | Original source | Source date | Transformation | What it supports |
|---|---|---|---|---|
| `data/raw/llama-bench-rocm-2026-09-30.txt` | `~/LLM/hip-managed-bench.txt` | mtime 2026-09-30 23:44 +0200; exact run time not recorded | Byte-for-byte copy | ROCm `tg128`, `@d16384`, `@d65536`; build `unknown (0)` |
| `data/raw/llama-bench-vulkan-2026-10-01.txt` | `~/LLM/vulkan-bench.txt` | mtime 2026-10-01 00:53 +0200; exact run time not recorded | Byte-for-byte copy | Vulkan `tg128`, `@d16384`, `@d65536`; build `f872b5911 (11310)` |
| `data/raw/vulkan-16gb-device-detection-2026-10-01.txt` | `~/LLM/vulkan-16gb-bench.txt` | mtime 2026-10-01 00:41 +0200 | Byte-for-byte copy | Vulkan device detection only; **no benchmark result** |
| `data/raw/dflash-rocm-server-2026-10-01.log` | `~/LLM/dflash-rocm.log` | mtime 2026-10-01 16:09 +0200; log uses relative timestamps | `/LLM/LLMs/` → `<models>/`; `/LLM/llama.cpp-managed/` → `<llama.cpp>/`; bind address → `[IP_ADDRESS]` | Older DFlash (block 16) ROCm server run: 15.54 t/s, 18.091% acceptance; second request incomplete |
| `data/raw/build-config-2026-10-02.txt` | `~/LLM/testing_resources/historical/2026-10-02-qwen/evidence/build-cache-excerpts.txt` | 2026-10-02 bundle | `/home/<user>/LLM/...` → `<llm-root>/...` | CMake caches for the ROCm and Vulkan builds |
| `data/raw/historical/session-summary-2026-10-02.txt` | `.../runs/2026-10-02-qwen/summary.txt` | 2026-10-02 | Byte-for-byte copy | 56-run session index: status, wall t/s, unique outputs, acceptance |
| `data/raw/historical/model-binary-sha256-2026-10-02.txt` | `.../runs/2026-10-02-qwen/model-binary-sha256.txt` | 2026-10-02 | Paths → `<llm-root>/...`; hashes unchanged | Target, DFlash1/2, and server binary SHA256 values |
| `data/raw/historical/post-reboot-memory-2026-10-02.json` | `.../runs/2026-10-02-qwen/post-reboot-memory.json` | recorded 2026-10-02T15:31:18+0200 | Byte-for-byte copy | 512 MiB VRAM / 15.08 GiB GTT record |
| `data/raw/historical/vulkan-nmax6-runs-2026-10-02.json` | `.../runs/2026-10-02-qwen/selected-vulkan-config.json` | started 2026-10-02T16:14:00+0200 | Byte-for-byte copy | Per-run Vulkan DFlash2 nmax6: 37.98, 42.20, 43.14 t/s; 91–94 °C; 45–52 W |
| `data/raw/historical/rocm-dflash2-runs-2026-10-02.json` | `.../runs/2026-10-02-qwen/selected-performance-config.json` | started 2026-10-02T11:44:03+0200 | Byte-for-byte copy | Per-run ROCm DFlash2 no-graphs: 26.77, 33.84, 38.83 t/s |
| `config/dflash2-config.json` | `.../evidence/dflash2-config.json` | 2026-10-02 bundle | Byte-for-byte copy | Draft architecture: block size 8, 6 layers, 8 target layers |
| `config/models.json` | New synthesis of `find`, `model-binary-sha256.txt`, and the 2026-10-18 manifests | 2026-11-05 (presence check) | New JSON; no paths with a username | Expected model files, sizes, SHA256, and current presence |
| `data/processed/llama-bench.csv` | The two raw llama-bench logs | 2026-09-30 / 2026-10-01 | Parsed by `scripts/parse_logs.py` | Six rows: backend × depth |
| `data/processed/llama-bench-ratios.csv` | Same | Same | Computed by `scripts/parse_logs.py` | Vulkan/ROCm ratio per depth |
| `data/processed/session-summary.csv` | `session-summary-2026-10-02.txt` | 2026-10-02 | Parsed by `scripts/parse_logs.py` | 56 server runs |
| `data/processed/speculative-summary.json` | `~/LLM/testing_resources/speculative_compare/results/20261018-200821-488233/summary.json` | started 2026-10-18T18:08:21Z | Byte-for-byte copy | Baseline / DFlash2 / MTP-off / MTP medians and paired speedups |
| `data/processed/speculative-measurements.csv` | Same run, `measurements.csv` | 2026-10-18 | Byte-for-byte copy | 24 measured requests |
| `data/processed/long-context-summary.json` | `~/LLM/testing_resources/speculative_compare/long-context-results/20261018-203923-240284/summary.json` | started 2026-10-18T18:39:23Z | Byte-for-byte copy | 4K / 32K / 61.4K, MTP/DFlash2, F16/Q8 KV |
| `data/processed/long-context-measurements.csv` | Same run, `measurements.csv` | 2026-10-18 | Byte-for-byte copy | 24 measured requests |
| `data/processed/agent-bench-summary.csv` | `~/LLM/testing_resources/llama-agent-bench/runs/20261013-213047-183018/summary.csv` | run directory 2026-10-13 21:30:47 local (UTC+2) | Byte-for-byte copy | 12 configurations, wall TPS, pass rates |
| `data/processed/roofline.csv` | `llama-bench.csv` + `config/models.json` | 2026-11-05 (computation) | Computed by `scripts/roofline.py` | First-order bandwidth model; 10 attention layers, 20,480 bytes/token; SSM state excluded |
| `docs/historical/2026-10-02-rocm-server.md` | `.../07_SESSION_RESULTS.md` | 2026-10-02 16:19 +0200 | Paths → `<llm-root>` / `<models>`; container name → `[container]`; “the user” → “the operator” | ROCm session narrative and 39-config table |
| `docs/historical/2026-10-02-vulkan-post-reboot.md` | `.../08_VULKAN_POST_REBOOT_RESULTS.md` | 2026-10-02 16:18 +0200 | Location → `UTC+2`; paths → `<llm-root>` | Vulkan post-reboot results, 25.63 baseline, 42.20 DFlash2 |
| `docs/historical/2026-10-02-rocm-512mb.md` | `.../11_ROCM_SHARED_MEMORY_COMPARISON.md` | 2026-10-02 22:20 +0200 | Performance section retained; unrelated generated-code quality review removed | ROCm 512 MiB vs historical Vulkan 16 GiB comparison |
| `docs/related/coding-quality.md` | `.../coder_benchmark/REVIEW.md` | 2026-10-02 run; review 2026-10-03 | Header added; body unchanged | Four ROCm coding conditions, 27 checks |
| `docs/related/speculative-decoding.md` | `~/LLM/testing_resources/speculative_compare/README.md` + the 2026-10-18 summary | 2026-10-18 | New distillation; paths removed | DFlash2/MTP method and results |
| `docs/related/long-context.md` | `~/LLM/testing_resources/speculative_compare/LONG_CONTEXT.md` + the 2026-10-18 long-context summary | 2026-10-18 | New distillation; paths removed | Long-context method and results |
| `docker/rocm-ubuntu26.04.Dockerfile` | `~/LLM/Dockerfile` | mtime 2026-09-30 00:52 +0200 | Non-English comments translated to English; commands unchanged | ROCm 10.0 / gfx1150 build recipe |

## Excluded sources

| Source | Reason |
|---|---|
| `testing_resources/OpenCodeAutoIteration/` | Private repository copy; explicitly excluded by rule 7 |
| `testing_resources/local_qwen_worker/`, `cursor_qwen_trial/`, `implementation/` | Unrelated private work |
| `testing_archive/` | Cleanup archive; not a benchmark source |
| `llama.cpp/`, `llama.cpp-managed/` | Vendored source and build artifacts |
| `LLMs/` | Model weights; only filenames, sizes, and quant labels were read |
| `coder_benchmark/runner.py`, `grader/`, `runs/` | Local container name/image ID and model outputs; not needed for the reported result |
| `speculative_compare/benchmark.py`, `long_context.py`, tests, manifests | Local paths, hostname, prompts; results are summarized |
| `llama-agent-bench/bench.py`, `run.sh`, `runs/` | Harness code and model outputs; only `summary.csv` is used |
| `historical/2026-10-02-qwen/06_SOURCE_CONVERSATION.md`, `evidence/source-thread.json` | Conversation export; personal material |
| `historical/2026-10-02-qwen/09_*`, `10_*` | Unrelated generated-code quality reviews |
| `historical/2026-10-02-qwen/01_*`, `03_*`, `05_*`, `04_*`, `02_*` | Research narrative, test plan, mixed proposed commands; distilled into methodology and provenance |
| `evidence/speculative-source-excerpts.txt` | Upstream source excerpts; no vendored source |
| `SHA256SUMS` | References excluded files; new checksums are generated in `data/checksums.txt` |
| `mtp-draft-sweep-results/`, `mtp-64k-q8-draft-comparison/`, `lfm24b-quick-results/` | Additional experiments outside the first version's scope |

## Missing or untraceable

| Item | Status | What would be needed |
|---|---|---|
| Target GGUF `Qwen3.6-35B-A3B-UD-IQ4_NL.gguf` | Not present on 2026-11-05 | Re-download the exact Unsloth artifact; verify 18,040,888,288 bytes and SHA256 `0d17e255…` |
| DFlash2 draft GGUF | Not present | Re-convert from the retained BF16 safetensors/config; verify SHA256 `3aa9bae5…` |
| DFlash1 draft GGUF | Not present | Re-download/convert; SHA256 `6ce38bc6…` |
| Exact archived `llama-bench` CLI | Not recorded | The wrapper reconstructs the flags from the log header; a fresh run is the only proof |
| BIOS version and per-run VRAM carve-out | Conflicting records | A BIOS screenshot or `dmidecode`/vendor tool output at run time |
| RAM type/speed/part number | Not recorded | `sudo dmidecode -t memory` or the laptop specification |
| ROCm runtime/image version | Unresolved | The original container image digest and `hipconfig --version` output |
| Wall power and locked clocks | Not recorded | A wall meter and fixed power/clock settings |
| Agent smoke run `20261013-211138` | Referenced but absent | The original run directory; the present run is `20261013-213047-183018` |
| NPU comparison | Not attempted | A working `amdxdna`/XRT stack and an NPU-capable inference path |

## Hash verification

`data/checksums.txt` contains SHA256 values for every file in the repository
except itself. The archived `model-binary-sha256-2026-10-02.txt` values for the
Vulkan and ROCm `llama-server` binaries match the binaries on the source machine
on 2026-11-05. The target model hash is recorded but the file is absent, so it
cannot be re-verified here.
