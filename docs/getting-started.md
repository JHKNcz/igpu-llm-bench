# Getting started: local LLM inference on an AMD UMA laptop

For a laptop APU with unified memory (Strix Point / Ryzen AI 300, Strix Halo,
Radeon 890M or similar). Measured on a Ryzen AI 9 HX 375 with a Radeon 890M
(`gfx1150`), 32 GB LPDDR5X, Ubuntu, kernel 7.0.0-43.

Time: about 30 minutes, most of it compiling and downloading a model.

## 1. Check what your GPU can see

```bash
lscpu | grep -E 'Model name|^CPU\(s\)'
free -h
for f in /sys/class/drm/card*/device/mem_info_vram_total \
         /sys/class/drm/card*/device/mem_info_gtt_total; do
  printf '%-22s %s MiB\n' "$(basename "$f")" "$(( $(cat "$f") / 1048576 ))"
done
vulkaninfo --summary | sed -n '/GPU0/,+8p'
```

Two numbers matter:

- **VRAM** (`mem_info_vram_total`) is the dedicated carve-out.
- **GTT** (`mem_info_gtt_total`) is the shared window into system RAM.

Full explanation of all four memory numbers: [`memory.md`](memory.md).

They are not additive with host RAM: VRAM is reserved, GTT is mappable system
memory. On this machine, 16 GB carve-out gives 16,384 MiB VRAM + 7,638 MiB GTT
with 15,277 MiB left for the OS.

## 2. Set the carve-out

> **Firmware write.** The commands below change UEFI settings. Save your work,
> and read [`../DISCLAIMER.md`](../DISCLAIMER.md) first. Raising the carve-out
> takes RAM from the host; if the machine becomes unstable, reset the setting in
> UEFI.

The carve-out is a UEFI setting, but it is writable from Linux:

```bash
cat /sys/class/drm/card*/device/uma/carveout          # current index
cat /sys/class/drm/card*/device/uma/carveout_options  # the table

echo 7 | sudo tee /sys/class/drm/card*/device/uma/carveout   # 16 GB here
sudo amd-smi set -g 0 -m 7                                   # same, via amd-smi
```

Or use the wrapper, which reads the table instead of hardcoding an index:

```bash
./scripts/carveout.sh --show
sudo ./scripts/carveout.sh --set-gb 16 --yes
```

**Reboot and verify.** The write persists through `UmaCarveOutIndexDefault`.

**Which setting?**

| Your situation | Carve-out |
|---|---|
| Model up to ~16 GiB, want maximum speed | **16 GB** |
| Need host RAM for other work | 0.5 GB |
| Want ROCm's unified-memory path for a model larger than VRAM | 0.5 GB |
| Not sure | 16 GB, then measure |

At 16 GB, small models decode 1.4–3.0x faster than at 0.5 GB on this machine,
and a 17.25 GiB model loads on Vulkan. At 0.5 GB, host RAM is 30 GiB and ROCm
can oversubscribe into it.

## 3. Build llama.cpp with Vulkan

```bash
git clone https://github.com/ggml-org/llama.cpp
cd llama.cpp
cmake -B build -DCMAKE_BUILD_TYPE=Release -DGGML_VULKAN=ON
cmake --build build -j "$(nproc)" --target llama-bench llama-server
./build/bin/llama-bench --version
```

The version line must show your GPU and a build number. If it shows only CPU,
install Mesa's RADV driver (`mesa-vulkan-drivers`) and re-check `vulkaninfo`.

A CPU-only build is useful as a baseline:

```bash
cmake -B build-cpu -DCMAKE_BUILD_TYPE=Release \
  -DGGML_VULKAN=OFF -DGGML_HIP=OFF -DLLAMA_BUILD_TESTS=OFF
cmake --build build-cpu -j "$(nproc)" --target llama-bench
```

## 4. Pick a model that fits

Rule of thumb: **model size + KV cache + a few hundred MiB of buffers must fit
the memory the backend can allocate.**

Measured examples on this machine:

| Model | Size | 0.5 GB carve-out | 16 GB carve-out |
|---|---:|---|---|
| LFM2.5-8B-A1B IQ4 | 4.05 GiB | runs | runs, faster |
| LFM2.5-8B-A1B Q8 | 8.69 GiB | runs | runs, faster |
| Qwen3-VL-4B Q8 (dense) | 4.70 GiB | runs | runs, faster |
| Qwen3.6-35B-A3B IQ4 (MTP) | 17.25 GiB | ROCm or CPU only | **Vulkan: 24.19 t/s** |

Backends differ in how they allocate:

- **Vulkan** can place tensors across two heaps (dedicated + GTT), so a model
  slightly larger than the dedicated pool can still load.
- **ROCm** needs the allocation to fit one device pool. A 16,679.34 MiB buffer
  does not fit a 16,384 MiB pool, which is why ROCm fails on the 35B at 16 GB.

Start with a 4–8 GiB quant. Move up only after a baseline works.

Exact repositories, revisions and licences for the models measured here:
[`models.md`](models.md). Note that LFM2.5 is **LFM1.0**, not Apache-2.0.

## 5. Run your first benchmark

```bash
BENCH=~/llama.cpp/build/bin/llama-bench
MODEL=~/models/your-model.gguf

"$BENCH" -m "$MODEL" -ngl 999 -fa on -t 12 -b 2048 -ub 512 \
  -p 512 -n 128 -r 3 -d 0
```

What the flags mean:

| Flag | Meaning |
|---|---|
| `-ngl 999` | offload all layers to the GPU |
| `-fa on` | flash attention |
| `-p 512` | prefill test: 512-token prompt |
| `-n 128` | decode test: 128 generated tokens |
| `-r 3` | repeat 3 times; the `±` is the spread |
| `-d 0` | context depth; try `-d 16384` and `-d 65536` |

This repository's wrapper records the carve-out, hashes, and thermals with the
result:

```bash
LLAMA_BENCH="$BENCH" MODEL="$MODEL" ./scripts/bench.sh --backend vulkan
```

## 6. Run a server

```bash
./build/bin/llama-server -m "$MODEL" -ngl 999 -fa on -c 16384 \
  --host 127.0.0.1 --port 8080
```

Then `curl http://127.0.0.1:8080/v1/chat/completions` or point any OpenAI-compatible
client at it.

## 7. Read the numbers honestly

- **`tg128` is decode only.** It is not the speed you will feel in a chat app.
- **`pp512` is prefill.** Long prompts are dominated by this.
- **`@ d16384` is a real filled context**, not a capacity setting.
- **Wall tokens/s** (tokens divided by full request time) is always lower than
  decode throughput.
- **The `±` is within-run spread**, not a confidence interval over reboots.

On this machine, decode falls with depth: the 35B goes from 24.19 t/s at depth 0
to 20.45 at 16K and 14.68 at 64K. Prefill falls much harder, from 367 to 66 t/s.

## 8. Common failures

| Symptom | Cause | Fix |
|---|---|---|
| `No such file or directory` writing `carveout` | wrong card number | use `card*`, or `./scripts/carveout.sh --show` |
| carve-out write rejected | index out of range | read `carveout_options`; 0–7 here |
| `Not enough memory for command submission` | desktop is holding VRAM | close GPU apps; retry when idle |
| Model loads sometimes, fails sometimes | VRAM fragmentation | retry; the 35B is not deterministic under desktop load |
| ROCm reports numbers but they are slow | HIP fell back to CPU | pass `--device /dev/kfd` in containers; check for "no ROCm-capable device" |
| Throughput drops after 10 minutes | thermal throttling | watch `gpu_temp`; this machine reached 99 °C |
| `libhipblas.so.3` missing | no ROCm runtime on the host | use the container, or install ROCm |

## 9. Optional: ROCm

The measured ROCm was 10.0.0 inside `rocm/dev-ubuntu-24.04:10.0.0-full`. A
container is the reproducible route:

```bash
podman run --rm -it \
  --device /dev/dri --device /dev/kfd \
  --security-opt seccomp=unconfined --group-add keep-groups \
  -v "$HOME/models:/models:ro" \
  --entrypoint /bin/bash \
  docker.io/rocm/dev-ubuntu-24.04:10.0.0-full
```

`/dev/kfd` is required. Without it, HIP prints numbers while running on the CPU.

## 10. Where to go next

- [`docs/faq.md`](faq.md) — troubleshooting and interpretation
- [`docs/hardware.md`](hardware.md) — the carve-out, GTT, and model architecture
- [`docs/limitations.md`](limitations.md) — what this does not establish
- [`RESULTS.md`](../RESULTS.md) — every table with its source
