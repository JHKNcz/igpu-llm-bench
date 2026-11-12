# Hardware and build

## Current machine snapshot

Collected 2026-11-05 on the source machine. Commands are listed at the end.

| Component | Value |
|---|---|
| CPU | AMD Ryzen AI 9 HX 375 w/ Radeon 890M |
| CPU topology | 12 cores / 24 threads, 1 socket, 1 NUMA node |
| CPU clocks | 605 MHz–5.16 GHz reported; boost enabled |
| CPU cache | L1d 576 KiB, L1i 384 KiB, L2 12 MiB, L3 24 MiB |
| System memory | 30 GiB visible to the OS; 15 GiB swap |
| iGPU | AMD Radeon 890M Graphics, `gfx1150`, device ID `0x150e` |
| Vulkan driver | RADV STRIX1, Mesa 26.0.8-1ubuntu0.3, Vulkan 1.4.341 |
| Kernel | `7.0.0-42-generic` |
| NPU | `amdxdna` loaded; `/dev/accel/accel0` present |
| Dedicated VRAM (current) | 512 MiB (`mem_info_vram_total` = 536,870,912 bytes) |
| GTT / shared graphics (current) | 15.08 GiB (`mem_info_gtt_total` = 16,188,944,384 bytes) |

### What is not recorded

- **RAM type, speed, and part number.** `dmidecode` requires interactive sudo on
  this machine, so the exact LPDDR5X speed is not recorded. The roofline uses
  120 GB/s as a central assumption (LPDDR5X-7500, 128-bit) and reports 102.4 and
  128 GB/s as sensitivity bounds. Confirm with `sudo dmidecode -t memory`.
- **BIOS version, and which carve-out each archived run used.** Both settings
  are documented below, but the per-run mapping is not recorded in the logs.
- **Mesa/Vulkan driver version at the time of the archived runs.** The current
  Mesa is 26.0.8; the archived logs do not record the Mesa version.

## Archived hardware records

The ROCm llama-bench log reports:

```text
Device 0: AMD Radeon 890M Graphics, gfx1150 (0x1150), VMM: no, Wave Size: 32, VRAM: 15438 MiB
```

The Vulkan llama-bench log reports:

```text
ggml_vulkan: 0 = AMD Radeon 890M Graphics (RADV STRIX1) (radv) | uma: 1 | fp16: 1 | bf16: 0 | fp4: 0
  | warp size: 64 | shared memory: 65536 | int dot: 1 | matrix cores: KHR_coopmat
```

The 2026-10-02 Vulkan note reports 16 GiB reserved VRAM, approximately 7.46 GiB
GTT, a Vulkan budget of 24,022 MiB total / 22,996 MiB free, and approximately
14 GiB host-visible RAM after the reservation. A JSON recorded earlier that day
(15:31 +0200) reports the other setting: 512 MiB VRAM and 15.08 GiB GTT. Both
are correct; see the two-setting table below.

### The 15,438 MiB figure is not a 15.4 GB dedicated carve-out

`15438 MiB` is 16,187,916,288 bytes, which matches the **GTT/UMA total** after
rounding, not a dedicated VRAM carve-out. The current `mem_info_gtt_total` is
16,188,944,384 bytes (15,438.98 MiB); the 2026-10-02 JSON records 16,188,948,480
bytes. The ROCm device therefore reports the shared UMA/GTT pool, not a 15.4 GB
dedicated allocation. At the 0.5 GB setting the dedicated carve-out is
**512 MiB, with ~15.08 GiB GTT**, matching the 15:31 JSON and the 2026-10-02 ROCm
comparison note.

### Changing the carve-out and GTT from Linux

The carve-out is a UEFI setting, but on kernel 7.0.0-43 it is also writable at
runtime. Two interfaces exist; both were confirmed on 2026-11-12.

**Raw sysfs** (index, writable; the option table is read-only):

```bash
cat /sys/class/drm/card*/device/uma/carveout
cat /sys/class/drm/card*/device/uma/carveout_options

# 16 GB on this model is index 7
echo 7 | sudo tee /sys/class/drm/card*/device/uma/carveout
```

**amd-smi** (same operation, higher-level tool):

```bash
amd-smi static --mem-carveout
sudo amd-smi set -g 0 -m 7
```

Observed table on this machine (`card1`):

```text
0: Minimum (512 MB)     4: (6 GB)
1: (1 GB)               5: Medium (8 GB)
2: (2 GB)               6: (12 GB)
3: (4 GB)               7: High (16 GB)
```

The write persists across a reboot: it goes through the EFI variable
`UmaCarveOutIndexDefault`, which held `0` before the change and `7` after.

**Pitfalls, both observed:**

- The GPU is `card1`, not `card0`. `card0` does not exist and the write fails
  with `No such file or directory`.
- Valid indices are 0–7. `echo 8` is out of range.
- The table is model-specific. Read `carveout_options` first; do not assume
  index 7 means 16 GB on another laptop.

Verify after a reboot:

```bash
cat /sys/class/drm/card*/device/uma/carveout
echo $(( $(cat /sys/class/drm/card*/device/mem_info_vram_total) / 1048576 )) MiB
amd-smi static --mem-carveout
```

`scripts/carveout.sh --show` prints all of the above, and
`sudo scripts/carveout.sh --set-gb 16 --yes` maps a size to the right index
without hardcoding one.

#### GTT size

GTT is the shared aperture the GPU can address, separate from the dedicated
carve-out. At the 16 GB setting it is **7,638 MiB**; at 0.5 GB it was
**15,438 MiB**. The two are a trade-off: the carve-out takes memory out of the
host, and GTT is the remaining GPU-addressable window.

There is no `uma/gtt` sysfs node. Two interfaces were tested on 2026-11-12:

| Attempt | Result |
|---|---|
| `sudo amd-smi set -G 12` | **Rejected when combined with `-g`.** `-G` is system-wide: `--gtt/-G: not allowed with argument --gpu/-g`. The correct form is `amd-smi set -G 12` with no `-g`. |
| `echo 3145728 > /sys/module/ttm/parameters/pages_limit` | Write succeeds (value changes to 3,145,728) but `mem_info_gtt_total` stays **7,638 MiB**. `pages_limit` is a TTM allocation cap, not the GTT aperture. |

So `ttm.pages_limit` is **not** the GTT control. The remaining candidate is
`amd-smi set -G <GB>` without `-g`, which was not exercised because the write
needs interactive sudo and a reboot to confirm persistence.

Fallback if that does not persist: the kernel command line,
`amdgpu.gttsize=12288` (MB), which is applied at module load.

```bash
# correct form (system-wide, no -g)
sudo amd-smi set -G 12

# fallback, requires reboot
# add to GRUB_CMDLINE_LINUX: amdgpu.gttsize=12288
```

`scripts/gtt-test.sh` runs both candidates, restores `pages_limit` afterwards,
and logs before/after GTT and host RAM so the result can be recorded rather
than assumed.

### Measured state at 16 GB (2026-11-12)

After writing index 7 and rebooting: VRAM 16,384 MiB, GTT 7,638 MiB, host
15,277 MiB, GPU-addressable 24,022 MiB. Vulkan reports two heaps: 7.82 GiB
host-visible and 14.92 GiB device-local. The 35B (17.25 GiB) loads because it
spans both.

### Two carve-out settings, and why the records looked contradictory

The records do not contradict each other. They are two different BIOS settings,
both of which the operator used, each with its own memory profile:

| Setting | GPU pool | GTT | Host-visible RAM | GPU-addressable total | 35B full offload |
|---|---:|---:|---:|---:|---|
| **0.5 GB** | 512 MiB | 15,438 MiB | 30,877 MiB | 15,950 MiB (15.58 GiB) | ROCm works, via unified memory into host RAM |
| **16 GB** | 16,384 MiB | 7,638 MiB | 15,277 MiB | 24,022 MiB (23.46 GiB) | ROCm full offload **fails**; Vulkan loads at 25.24 t/s |

The 24,022 MiB figure is the "24 GB usable for inference" the operator reports,
and it matches the Vulkan budget recorded in
[`2026-10-02-vulkan-post-reboot.md`](historical/2026-10-02-vulkan-post-reboot.md)
("Vulkan reports 24,022 MiB total budget and 22,996 MiB free before the run").

The cost of that 24 GB is host RAM: raising the carve-out from 0.5 GB to 16 GB
moves roughly 15.5 GiB out of the host and into the GPU pool, leaving 14.92 GiB
for everything else.

#### Why ROCm cannot fully offload the 35B model at 16 GB

This is a measured capability difference, not a speed difference. At the 16 GB
setting, ROCm reports a 16,384 MiB device pool with 16,210 MiB free, and the
target's weight buffer is 16,679.34 MiB:

```text
ROCm0 : AMD Radeon 890M Graphics (16384 MiB, 16210 MiB free)
CPU   : AMD Ryzen AI 9 HX 375 w/ Radeon 890M (15277 MiB, 15277 MiB free)
...
E ggml_backend_cuda_buffer_type_alloc_buffer: allocating 16679.34 MiB on device 0: cudaMalloc failed: out of memory
E alloc_tensor_range: failed to allocate ROCm0 buffer of size 17489553920
E llama_model_load: error loading model: unable to allocate ROCm0 buffer
```

The buffer is 295 MiB larger than the entire pool, and host RAM is only 15,277
MiB, so the unified-memory fallback has nothing to fall back to. At the 0.5 GB
setting the same model loads, because HIP unified memory can oversubscribe into
30 GiB of host RAM. That is why the *smaller* carve-out is the one that works for
ROCm on this model.

Source: `data/raw/historical/rocm-16gb-load-failure-2026-10-02.log` lines 6–7 and
159–161; `data/raw/historical/carveout-states-2026-10-02.json`.

> **Hypothesis, not measured:** the 16,679 MiB allocation must be contiguous
> within one pool and cannot span VRAM and GTT. The OOM message shows the
> allocation failing as a single buffer; it does not show why the allocator did
> not split it. Treat the mechanism as plausible and the failure as observed.

### What this means for the headline comparison

The carve-out is a capacity trade-off, not a quality setting, and it is a real
confound for any cross-setting comparison. The two archived `llama-bench` files
do not record which setting they ran under, so the 2.32x ratio cannot be
attributed to the backend alone. The defensible statement remains: Vulkan was
faster in every archived same-machine comparison, by roughly 1.4x–2.3x.

## Build provenance

| Item | Value |
|---|---|
| llama.cpp commit | `f872b591121761ac7b2af18283bd99bdc092a63a` |
| Commit date | 2026-09-30 22:33:22 +0200 |
| Commit subject | `cuda: guard the iq4_nl dequantize row kernel against short rows (#29683)` |
| Working tree | Clean at inspection |
| Vulkan build | build 11310, commit `f872b5911`, GNU 15.2.0 |
| ROCm build | build 0 / unknown commit, GNU 13.3.0 |
| ROCm runtime used for the measurements | **ROCm 10.0.0**, image `rocm/dev-ubuntu-24.04:10.0.0-full` (HIP 7.15.26333-0000000) |
| Archived container image ID | `518ced857e9bc4f27392985257dcdf19c43d28918ff6e60074ea09ceb9edd19d` |
| Same image still local | Yes — the `:latest` image ID matches byte-for-byte |
| Dockerfile target | Ubuntu 26.04, ROCm 10.0 `amdrocm-core-dev10.0-gfx1150` |
| Host ROCm runtime | **absent** (`/opt/rocm` missing; `libhipblas.so.3` missing) |

### Which ROCm version the numbers came from

The measured runtime is **ROCm 10.0.0**, not ROCm 7.x. Three records agree:

1. `container-provenance.txt` records image
   `518ced857e9bc4f27392985257dcdf19c43d28918ff6e60074ea09ceb9edd19d`.
2. The local `docker.io/rocm/dev-ubuntu-24.04:10.0.0-full` image has that exact
   ID, and so does `:latest` — they are the same image.
3. That image reports `HIP version: 7.15.26333-0000000`, which is the HIP
   version bundled inside ROCm 10.0.0. The 2026-10-02 session note recorded the
   same HIP string from `hipconfig --version`.

**The "7.15" in the logs is the HIP version, not the ROCm version.** An earlier
revision of this document read it as "ROCm 7.15, not ROCm 10"; that was wrong.
The tag mapping is the evidence: `10.0.0-full` and `latest` resolve to the same
image ID, so every ROCm measurement here is ROCm 10.0.0.

The archived `model-binary-sha256.txt` records:

```text
8277bb4239251b4198514e7febcfee0a0733bef98076ade09ecb764736f5f934  <llama.cpp>/build-rocm/bin/llama-server
936fd4c733d6f7608fd0105b0027a6983f572e2fd681e16d2182948119b16af5  <llama.cpp>/build-vulkan/bin/llama-server
0d17e255dc257a11f398ed4bc8d62412d8ce9ca24b3fce2947d962e4bfed5758  <models>/Qwen3.6-35B-A3B-UD-IQ4_NL.gguf
6ce38bc63e6b622ce1c6fff4ac8eb5fa08dfab802b1bf1841890abcca1bb46fd  <models>/Qwen3.6-35B-A3B-DFlash-BF16.gguf
3aa9bae5332415f5563918a8b31c82e913add862446159f41a20e756c49b065f  <models>/Qwen3.6-35B-A3B-DFlash2-BF16.gguf
```

The Vulkan and ROCm `llama-server` hashes on the source machine on 2026-11-05
match these values exactly. The archived `llama-bench` binary hash was not
recorded; the current Vulkan `llama-bench` hash is
`932de2472c76af83afaa29920a3758fb0ca7b9d9ad23b8f86423fafa2f8f8d79`, and its
implementation library is
`79fb4bea7fe7d742583b73051fb00db80108d77c621c591a695bc99e87aa3428`.

## Model files

| Model | Expected file | Size | SHA256 | Present 2026-11-05 |
|---|---|---:|---|---|
| Qwen3.6-35B-A3B UD-IQ4_NL target | `<models>/Qwen3.6-35B-A3B-UD-IQ4_NL.gguf` | 18,040,888,288 | `0d17e255…` | **No** |
| DFlash2 BF16 draft | `<models>/Qwen3.6-35B-A3B-DFlash2-BF16.gguf` | 1,063,708,928 | `3aa9bae5…` | **No** (safetensors/config only) |
| DFlash1 BF16 draft | `<models>/Qwen3.6-35B-A3B-DFlash-BF16.gguf` | 736.12 MiB (log) | `6ce38bc6…` | **No** |
| Qwen3.6 MTP UD-IQ4_NL | `<models>/Qwen3.6-MTP/Qwen3.6-35B-A3B-UD-IQ4_NL.gguf` | 18,536,192,288 | not recorded | Yes |
| LFM2.5-8B-A1B UD-IQ4_NL | `<models>/LFM2.5-8B-A1B/LFM2.5-8B-A1B-UD-IQ4_NL.gguf` | 4,358,844,000 | not recorded | Yes |
| LFM2.5-8B-A1B UD-Q8_K_XL | `<models>/LFM2.5-8B-A1B/LFM2.5-8B-A1B-UD-Q8_K_XL.gguf` | 9,340,497,504 | not recorded | Yes |

The target and draft GGUFs are **not included** in this repository. The sizes
and hashes are recorded so a re-download can be checked. The target and DFlash2
files were absent from the source machine on 2026-11-05, so the 35B headline
cannot be re-run without downloading them.

### Model architecture (from the ROCm server log)

- 40 layers total; `full_attention_interval=4` means 10 full-attention layers
  and 30 SSM/recurrent layers.
- 256 experts, 8 active per token; embedding 2048; 16 heads, 2 KV heads;
  key/value length 256.
- At 16K context the attention KV cache is 320 MiB (10 layers, F16 K/V); the
  recurrent state is 1,067.81 MiB.
- 320 MiB / 16,384 tokens = 20,480 bytes/token, the value used in the roofline.

## Commands used for this snapshot

```bash
lscpu
free -h
uname -r
vulkaninfo --summary
lsmod | grep -i amdxdna
ls -l /dev/accel
for f in /sys/class/drm/card*/device/mem_info_vram_total \
         /sys/class/drm/card*/device/mem_info_gtt_total; do
  [ -r "$f" ] && printf '%s = %s\n' "$f" "$(cat "$f")"
done
git -C "$LLAMA_CPP" log -1 --format='%H%n%cd%n%s'
git -C "$LLAMA_CPP" status --short
sha256sum "$VULKAN_SERVER" "$ROCM_SERVER"
"$VULKAN_BENCH" --version
```

`rocminfo` is not installed on the current machine, and `/opt/rocm` is absent.
`dmidecode` requires sudo and was not run.
