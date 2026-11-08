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
- **BIOS version and the per-run VRAM carve-out.** See the conflict below.
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
(15:31 +0200) reports 512 MiB VRAM and 15.08 GiB GTT.

### The 15,438 MiB figure is not a 15.4 GB dedicated carve-out

`15438 MiB` is 16,187,916,288 bytes, which matches the **GTT/UMA total** after
rounding, not a dedicated VRAM carve-out. The current `mem_info_gtt_total` is
16,188,944,384 bytes (15,438.98 MiB); the 2026-10-02 JSON records 16,188,948,480
bytes. The ROCm device therefore reports the shared UMA/GTT pool, not a 15.4 GB
dedicated allocation. The dedicated carve-out at the time of the
ROCm run is best described as **512 MiB, with ~15.08 GiB GTT**, matching the
15:31 JSON and the 2026-10-02 ROCm comparison note.

### The carve-out records conflict

| Record | Dedicated VRAM | GTT | When |
|---|---:|---:|---|
| `post-reboot-memory-2026-10-02.json` | 512 MiB | 15.08 GiB | 2026-10-02 15:31 +0200 |
| `2026-10-02-vulkan-post-reboot.md` | 16 GiB | ~7.46 GiB | 2026-10-02 16:08 run |
| `vulkan-16gb-device-detection-2026-10-01.txt` | not recorded | not recorded | 2026-10-01 00:41 |
| Current sysfs | 512 MiB | 15.08 GiB | 2026-11-05 |

The 15:31 JSON and the 16:08 note disagree. The machine may have been rebooted
between them, or the note may describe a different boot. **The exact carve-out
for each archived run is unresolved.** This is one of the reasons the Vulkan vs
ROCm comparison is not a controlled A/B.

## Build provenance

| Item | Value |
|---|---|
| llama.cpp commit | `f872b591121761ac7b2af18283bd99bdc092a63a` |
| Commit date | 2026-09-30 22:33:22 +0200 |
| Commit subject | `cuda: guard the iq4_nl dequantize row kernel against short rows (#29683)` |
| Working tree | Clean at inspection |
| Vulkan build | build 11310, commit `f872b5911`, GNU 15.2.0 |
| ROCm build | build 0 / unknown commit, GNU 13.3.0 |
| ROCm runtime in notes | HIP compiler/runtime `7.15.26333-0000000` |
| Dockerfile target | Ubuntu 26.04, ROCm 10.0 `amdrocm-core-dev10.0-gfx1150` |
| Current ROCm runtime | **absent** (`/opt/rocm` missing; `libhipblas.so.3` missing) |

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
