# FAQ and troubleshooting

Practical answers for someone running this on their own laptop. If a symptom is
not here, open an issue on the private repository or add a row to
`docs/reproduction-checklist.md` once you have solved it.

## Questions people actually ask

### What is UMA, and why does it matter for local LLMs?

UMA (unified memory architecture) means the CPU and GPU share one pool of
physical RAM. On an AMD APU the BIOS reserves part of that pool as dedicated
VRAM and exposes the rest to the GPU through the GTT aperture. A large model can
therefore run without a discrete GPU, but what fits depends on the carve-out,
and throughput depends on which path the weights take. The four numbers and how
they relate: [`memory.md`](memory.md).

### How do I run a 35B model on an AMD laptop?

Use the 16 GB carve-out and Vulkan. On this machine a 17.25 GiB
mixture-of-experts model runs at 24.19 tokens/s at depth 0, 20.45 at 16K and
14.68 at 64K. ROCm cannot fully offload it at that setting because a single
16,679.34 MiB allocation does not fit the 16,384 MiB device pool. Step by step:
[`getting-started.md`](getting-started.md).

### Why is my iGPU slower than my CPU?

Decode generates one token at a time, so it is limited by memory bandwidth, and
the CPU and iGPU read the same LPDDR5X through the same controller. The CPU
adds no driver or command-submission overhead. On this machine the CPU beat the
iGPU at short context for every model tested: 36.7 t/s against 30.6 (ROCm) and
24.0 (Vulkan) on an 8.69 GiB model. Prefill is compute-dense and the GPU wins
there by about 4x.

### How much memory do I need for a model?

Roughly the file size plus the KV cache plus a few hundred MiB of buffers. A
4 GiB quant runs at the 0.5 GB carve-out; an 8.7 GiB quant runs at either; a
17.25 GiB model needs the 16 GB carve-out and, on this machine, Vulkan rather
than ROCm. Check the real numbers with
`./scripts/carveout.sh --show` before downloading.

### Does the VRAM carve-out affect speed, or only what fits?

Both. At 16 GB the same small models decoded 1.4–3.0x faster than at 0.5 GB,
and the 35B became runnable on Vulkan. The cost is host RAM: 15,277 MiB instead
of 30,877 MiB, which made CPU inference of the 35B slower (13.78 vs 18.38 t/s).

## Before you run anything

### "Which model do I actually need?"

For the headline reproduction: `Qwen3.6-35B-A3B-UD-IQ4_NL.gguf`, exactly
18,040,888,288 bytes, SHA256 starting `0d17e255`. Any other quant is a different
experiment. Verify before benchmarking:

```bash
sha256sum "$MODEL"
stat -c '%s' "$MODEL"
```

For a harness smoke test you only need a small model; the LFM2.5-8B-A1B IQ4_NL
in `config/models.json` works on 4 GiB.

### "Why does my number differ from yours?"

Most likely, in rough order:

1. **VRAM carve-out.** 512 MiB vs 16 GiB changes whether the model fits on the
   GPU at all. Check `/sys/class/drm/card*/device/mem_info_vram_total`.
2. **Swap.** If `free -h` shows swap in use during a run, the measurement is
   contaminated. Close other workloads.
3. **Thermals and clocks.** An iGPU in a thin laptop throttles. The archived
   Vulkan runs sat at 91–94 °C.
4. **Build.** A different llama.cpp commit, or a different backend build of the
   same commit, can move decode speed by tens of percent.
5. **Depth.** `tg128` at depth 0 and `tg128 @ d65536` differ by roughly 45% here.
   Compare like with like.

### "Do I need ROCm installed?"

Only for the ROCm arm. The Vulkan arm needs just Mesa's RADV driver, which is
present on a stock Ubuntu install. The source machine no longer has `/opt/rocm`,
so its ROCm numbers cannot be re-run without a rebuild or the original container.

### "How do I change the VRAM carve-out without going into BIOS?"

On kernel 7.0.0-43 the carve-out is writable at runtime:

```bash
cat /sys/class/drm/card*/device/uma/carveout          # current index
cat /sys/class/drm/card*/device/uma/carveout_options  # index table

echo 7 | sudo tee /sys/class/drm/card*/device/uma/carveout   # 16 GB
sudo amd-smi set -g 0 -m 7                                   # same, via amd-smi
```

Two traps, both hit in practice: the GPU is `card1` (not `card0`), and valid
indices are 0–7. Reboot and verify with
`echo $(( $(cat /sys/class/drm/card*/device/mem_info_vram_total) / 1048576 ))`.
`scripts/carveout.sh --show` prints the current state and
`sudo scripts/carveout.sh --set-gb 16 --yes` picks the index for you.

GTT is a separate knob (`amd-smi set -g 0 -G <GB>`); see `docs/hardware.md`.

## Running the benchmark

### "llama-bench says `error while loading shared libraries: libllama-bench-impl.so`"

The binary and its shared libraries were split into separate files. Run from the
directory that contains them, or set the loader path:

```bash
export LD_LIBRARY_PATH="$(dirname "$LLAMA_BENCH"):${LD_LIBRARY_PATH:-}"
```

`scripts/bench.sh` does this for the ROCm case when `ROCM_PATH` is set. If it
still fails with `libhipblas.so.3`, the ROCm runtime is incomplete.

### "The benchmark exits immediately or reports 0 t/s"

Usually the model did not load. Run the same command with `--verbose`, or load
the model once with `llama-cli` to see the real error. On a 16 GiB-class iGPU a
16.79 GiB model plus runtime buffers does not fit unless the carve-out is large
or offload is reduced.

### "How long should a run take?"

`tg128` at three depths, two repetitions each, on this model: a few minutes plus
model load. The 35B model load dominates; the LFM smoke test is under two
minutes. Anything much longer suggests swap or CPU fallback.

### "Why does `bench.sh` run one command per depth instead of one `-d` list?"

llama-bench accepts a single depth per invocation in the build used here. One
invocation per depth keeps each result attributable and makes a partial failure
obvious. The wrapper writes each command into the `.metadata.txt` file.

### "Can I change the repetitions?"

Yes, `--reps N`. Two is the archived protocol and is **not** enough for a
confidence interval. If you intend to publish a comparison, use at least five
and run both arms on the same boot.

## Interpreting the results

### "Is 2.32x the real Vulkan advantage?"

No. It is the raw ratio of two archived runs that differ in build, memory
carve-out, and runtime. The defensible statement is "Vulkan was faster in every
archived same-machine comparison, by roughly 1.4x–2.3x." See
`docs/limitations.md`.

### "Why is the ROCm depth-0 number lower than its 16K number?"

It should not be, if the machine were steady. The non-monotonic series
(10.89 → 12.63 → 7.84) suggests run-to-run noise, a first-run effect, or
contention during the depth-0 run. It is one reason the depth-0 ratio is treated
as a lower bound.

### "Why do the speculative speedups differ (1.28x, 1.65x, 1.51x)?"

They are three different workloads, not three estimates of one number:

- 1.28x: paired, 3 prompts × 3 rounds, 256-token outputs, 32K capacity.
- 1.65x: short-prompt note, 512-token outputs, different acceptance.
- 1.51x: the same paired run but for MTP, not DFlash2.

Do not average them. Pick the protocol that matches your workload.

### "The DFlash2 confidence interval includes 1.00. Is DFlash2 useless?"

No. It means that with 9 paired cells the effect is not distinguishable from
noise for every prompt. The point estimate is 1.28x and the per-cell range is
0.94–1.69, so it plausibly helps on some prompts and not others. More
repetitions and more prompts would settle it.

### "Why is the roofline only about a third of peak?"

Because the model is not purely bandwidth-bound. Dequantization, expert routing,
kernel occupancy, and synchronization all consume time that a bytes-per-second
model does not see. `analysis/roofline.md` lists five hypotheses and what would
test each. None is confirmed.

### "My GPU reports 15,438 MiB. Is that 15.4 GB of VRAM?"

Probably not. On this platform that figure matches the GTT/UMA aperture, i.e.
shared system memory the GPU can address, not a dedicated pool. Check
`mem_info_vram_total` for the carve-out.

## Data and provenance

### "Where did a specific number come from?"

Search `data/provenance.md` for the file, then open the file and look at the line
number in the table. Every table row in `RESULTS.md` carries a source path.

### "How do I know the docs still match the data?"

```bash
python3 scripts/verify_results.py
```

It checks that each headline number in `README.md` and `RESULTS.md` appears in
the generated CSVs/JSON, and that known stale values are gone. It fails loudly.

### "How do I regenerate the derived files?"

```bash
python3 scripts/parse_logs.py    # raw logs -> CSV
python3 scripts/roofline.py      # CSV + config -> roofline.csv
python3 scripts/stats.py         # measurements -> confidence intervals
python3 scripts/chart.py         # data -> docs/figures/*.svg
python3 scripts/verify_results.py
```

All five are standard-library only and deterministic.

## Privacy

### "Can I publish my own results using this repo?"

Yes, but check your own logs first. `scripts/secret_scan.py` is a starting
point: it looks for tokens, emails, IPs, MACs, UUIDs, hostnames, and usernames.
It is a regex pass, not a guarantee. Read `docs/privacy.md` for the categories
this repository had to redact.

### "Why are paths written as `<models>/...`?"

Absolute paths on the source machine contained a username. They were replaced
with placeholders so the artifacts stay portable and anonymous.
