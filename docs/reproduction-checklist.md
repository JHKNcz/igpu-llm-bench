# Reproduction checklist

A step-by-step path from a fresh clone to numbers you can compare with
`RESULTS.md`. Tick each box; the failure modes are ordered roughly by how often
they bite.

Estimated time: 20–40 minutes, dominated by the model download and load.

---

## 0. Know what you are reproducing

- [ ] Pick a target. The headline needs the exact 35B IQ4_NL file. A harness
      smoke test needs only a small model.
- [ ] Decide which comparison you want:
      - Vulkan vs ROCm `tg128` → section 1–3
      - speculative decoding (DFlash2 / MTP) → section 4
      - long context → section 5
- [ ] Read `docs/limitations.md` first. It explains what a difference of 5%
      means here, and what it does not.

## 1. Machine preflight

```bash
lscpu | sed -n '1,12p'
free -h
uname -r
vulkaninfo --summary | sed -n '/GPU0/,+8p'
```

- [ ] CPU and iGPU match (or note the difference; results will not transfer).
- [ ] `free -h` shows no swap in use, and at least 20 GiB available before load.
- [ ] Record the kernel. A kernel change between runs is a confound.
- [ ] Check the VRAM carve-out:

```bash
for f in /sys/class/drm/card*/device/mem_info_vram_total \
         /sys/class/drm/card*/device/mem_info_gtt_total; do
  [ -r "$f" ] && printf '%s = %s\n' "$f" "$(cat "$f")"
done
./scripts/carveout.sh --show
```

- [ ] If it is the wrong setting, change it (no BIOS needed on kernel 7.0.0-43):

```bash
sudo ./scripts/carveout.sh --set-gb 16 --yes
# then reboot and re-check
```

- [ ] Write down whether it is 512 MiB or ~16 GiB. This is the single largest
      source of "why is my number different".

## 2. Close the machine down

- [ ] Stop other inference servers (`ss -ltnp | grep -E '8080|18080|11434'`).
- [ ] Stop browsers, Electron apps, and anything using the GPU.
- [ ] Plug in power; set the performance profile if the laptop has one.
- [ ] Let it idle two minutes so clocks settle.

## 3. Verify the model

```bash
sha256sum "$MODEL"
stat -c '%s' "$MODEL"
```

- [ ] Size and hash match `config/models.json`. If not, stop: it is a different
      experiment.

## 4. Record the build

```bash
"$LLAMA_BENCH" --version
sha256sum "$LLAMA_BENCH" "$(dirname "$LLAMA_BENCH")/libllama-bench-impl.so"
git -C "$LLAMA_CPP" log -1 --format='%H %cd %s'
git -C "$LLAMA_CPP" status --short
```

- [ ] Commit matches `f872b5911…` (or note the difference).
- [ ] Working tree is clean.

## 5. Run the decode benchmark

```bash
LLAMA_BENCH=$HOME/llama.cpp/build-vulkan/bin/llama-bench \
MODEL=$HOME/models/Qwen3.6-35B-A3B-UD-IQ4_NL.gguf \
LLAMA_CPP=$HOME/llama.cpp \
./scripts/bench.sh --backend vulkan --reps 2 --llama-cpp "$LLAMA_CPP"
```

- [ ] Command echoes one invocation per depth.
- [ ] `.metadata.txt` exists next to the output and contains the hashes and
      `lscpu`.
- [ ] Output has three rows (`tg128`, `@ d16384`, `@ d65536`).
- [ ] Sanity check: depth-0 should be the fastest of the three. If not, suspect
      thermal throttling or contention.

Repeat with `--backend rocm` and the ROCm binary. If ROCm is unavailable, that
arm is simply missing; do not substitute a different build and call it a
comparison.

## 6. Parse and compare

```bash
python3 scripts/parse_logs.py
python3 scripts/roofline.py
```

- [ ] `data/processed/llama-bench.csv` has six rows (or three per backend you
      actually ran).
- [ ] `data/processed/roofline.csv` has matching rows.
- [ ] Compare with `RESULTS.md` §1 and §6. A difference under ~10% is expected
      on the same hardware class; a difference over ~25% means something
      material changed.

## 7. If you are running the speculative suite

The full suite is not included in this repository. To reproduce it you need the
harness from the original source bundle, the 35B target, the DFlash2 draft, and
the MTP file.

- [ ] All three model files present and hashed.
- [ ] Server starts on a free port; no other server owns it.
- [ ] Each mode reports a non-zero draft token count when speculation is on. A
      run where speculation silently did nothing must be discarded, not
      published.
- [ ] Three rounds completed, mode order rotated.
- [ ] Then:

```bash
python3 scripts/stats.py
```

- [ ] The paired CI for MTP excludes 1.00. If it does not, your sample is too
      small or your machine is noisy.

## 8. Before you publish your numbers

- [ ] `python3 scripts/verify_results.py` passes if you edited the docs.
- [ ] `python3 scripts/secret_scan.py` passes on anything you copied.
- [ ] Every number in your write-up has a file and a line.
- [ ] You have stated the carve-out, the build, the kernel, and the number of
      repetitions.
- [ ] You have not compared rows from different tables as if they were one
      experiment.

## 9. If something goes wrong

| Symptom | First thing to check |
|---|---|
| `libllama-bench-impl.so` missing | `LD_LIBRARY_PATH` includes the binary's directory |
| `libhipblas.so.3` missing | ROCm runtime incomplete; `/opt/rocm` present? |
| 0 t/s or immediate exit | Model failed to load; run once with `llama-cli --verbose` |
| Depth-0 slower than 64K | Thermal throttling, swap, or another GPU process |
| Results 2x off | Carve-out changed, or a different build/quant |
| Swap in use | Close workloads; the run is contaminated |
| Vulkan device not found | `vulkaninfo` works? `MESA_VK_DEVICE_SELECT` unset? |

More in `docs/faq.md`.
