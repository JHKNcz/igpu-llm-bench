# Glossary

Terms used in this repository, in the order a newcomer is likely to meet them.
Where a term has a precise definition in the measurement, the definition here
matches the one used in `docs/methodology.md`.

## Measurement terms

**tg128** — llama-bench's "text generation, 128 tokens" test. It measures decode
speed: generate 128 tokens after a short prompt, report tokens/second. This is
the headline metric here. It does **not** include prompt processing.

**pp512** — llama-bench's "prompt processing, 512 tokens" test. Measures prefill
speed. Appears in the historical tables but not in the headline comparison.

**`@ d16384` / `@ d65536`** — llama-bench's depth setting. Before timing, the
benchmark fills the context with that many tokens, then generates at that depth.
This is an actual filled context, not merely a capacity setting. A server started
with `-c 65536` but a 35-token prompt is **not** a 64K test.

**±** — in the archived llama-bench logs, the spread reported across the
measured repetitions. It is not a confidence interval over boots, and the logs
do not define it. Treat it as a within-run spread.

**Wall TPS** — output tokens divided by the full HTTP request duration. Includes
prefill, reasoning tokens, generation, and transport. Always lower than pure
decode throughput, and not comparable to `tg128`.

**Generation t/s** — in the speculative and long-context suites, the decode rate
reported by the server for the generation phase only. Comparable across modes
within those suites, not to `tg128` or wall TPS.

**Paired speedup** — divide mode A by mode B *within the same experimental cell*
(same prompt, same round), then summarise the ratios. Removes cell-to-cell
variation that would otherwise inflate the uncertainty. See `scripts/stats.py`.

**Bootstrap CI** — resample the measured values with replacement, recompute the
statistic many times, and take percentiles. Used here with 20,000 resamples and a
fixed seed so the interval is reproducible. With n=9 the interval is wide; that
is the honest result, not a defect.

**MAD** — median absolute deviation. A spread measure that, unlike the standard
deviation, is not dominated by one outlier.

## Hardware terms

**iGPU / APU** — graphics built into the CPU package and sharing system memory.
The Radeon 890M here has no dedicated VRAM pool worth the name.

**UMA** — unified memory architecture. CPU and GPU address the same physical
memory. `uma: 1` in the Vulkan device line means the driver reports this.

**GTT** — Graphics Translation Table. On AMD, the aperture through which the GPU
can address system memory. The ROCm log's "15,438 MiB VRAM" matches the GTT
total, not a dedicated carve-out.

**VRAM carve-out** — the BIOS setting that reserves part of system RAM as
dedicated GPU memory. Both 512 MiB and 16 GiB were used on this machine. The
setting is a capacity trade-off: 16 GiB gives ~23.5 GiB of GPU-addressable
memory but leaves only ~14.9 GiB for the host, while 512 MiB leaves ~30 GiB of
host RAM. It decides which backend can load the model, not just how fast it
runs.

**gfx1150** — the AMD GPU architecture target for Strix Point (Ryzen AI 300
series) integrated graphics. It determines which ROCm/HIP kernels are compiled.

**RADV** — Mesa's open-source Vulkan driver for AMD GPUs. The alternative is
AMD's proprietary `amdvlk`/`amd-proprietary` driver.

**Wave size** — how many threads execute together on the GPU. Vulkan reports 64
here; ROCm reports 32. Different compilation targets, so equal source code does
not mean equal scheduling.

**NPU / XDNA** — the neural processing unit in Ryzen AI chips, exposed via
`amdxdna` and `/dev/accel/accel0`. Present on this machine, **not used** in any
measurement here.

## Model terms

**MoE (mixture of experts)** — a model with many expert subnetworks where only a
few activate per token. This model has 256 experts and activates 8.

**A3B** — vendor shorthand for "about 3 billion active parameters" in a 35B-class
MoE model. It is a label, not an independently measured activation count. The
roofline depends on it, which is why the assumption is stated explicitly.

**IQ4_NL** — a 4-bit llama.cpp quantization ("i-quant, 4-bit, non-linear"). The
target is `UD-IQ4_NL` at 4.5 bits per weight. Lower bits mean less memory traffic
but more dequantization work, which is one of the roofline hypotheses.

**GGUF** — the file format llama.cpp loads. A GGUF carries weights plus metadata
(architecture, tokenizer, quantization). Hashes in `config/models.json` identify
exact files.

**KV cache** — stored keys and values for attention, so each new token does not
recompute the past. Grows with context depth and consumes bandwidth on every
decode step. This model's hybrid architecture keeps it smaller than a
conventional 40-layer transformer.

**SSM / recurrent layers** — state-space layers that carry a fixed-size state
instead of a growing KV cache. This model has 30 SSM layers and 10 full-attention
layers, which is why the KV term is 20,480 bytes/token rather than 40,960.

**Hybrid attention** — a model that mixes full attention with another sequence
mechanism (here SSM). Important for benchmarking because the memory profile
differs sharply from a plain transformer.

**DFlash / DFlash2** — draft models used for speculative decoding with a Qwen
target. DFlash2 is the newer generation. They are **different files** with
different block sizes (16 vs 8); do not treat one as evidence for the other.

**MTP (multi-token prediction)** — a target model with extra prediction layers
that propose several tokens ahead. Speculation can be turned on or off with the
same weights, which gives a clean on/off control.

**Speculative decoding** — a small draft model proposes tokens, the large target
verifies them in one pass. Faster only when the acceptance rate is high enough to
pay for the draft.

**Draft acceptance** — accepted draft tokens divided by proposed draft tokens.
High acceptance is necessary but not sufficient for a speedup; the draft and
verification still cost time.

**Mean accepted length** — average number of tokens advanced per verification
step. In the llama.cpp logs this includes the target's own step, so it is not a
speedup multiplier. `1 + accepted/calls` is the formula used in the archived
notes.

**Thinking / reasoning tokens** — tokens the model spends on internal reasoning
before the answer. They count toward wall time and token budgets but may not
appear in the final answer. A "512-token" run that stops mid-reasoning has no
usable answer.

## Benchmark-quality terms

**Controlled A/B** — both arms differ only in the variable under test. The
Vulkan-vs-ROCm comparison here is **not** one: build, carve-out, and runtime
differ.

**Confound** — a difference between arms other than the variable under test. The
coding-quality matrix has several (test-freeze policy, tool-protocol overhead).

**Provenance** — the chain from a number back to the file and command that
produced it. `data/provenance.md` is the chain for this repository.

**Stale value** — a number left over from an earlier analysis after a correction.
`scripts/verify_results.py` checks for the specific stale values this repository
has already had to fix.
