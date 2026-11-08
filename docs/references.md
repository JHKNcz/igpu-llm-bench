# References

Grouped by what they are used for, with the confidence appropriate to each.
This repository makes no claim beyond what its own measurements show; external
material is cited so a reader can check the context, not to borrow authority.

## Software measured

- **llama.cpp**, commit `f872b591121761ac7b2af18283bd99bdc092a63a`
  (2026-09-30), commit subject "cuda: guard the iq4_nl dequantize row kernel
  against short rows (#29683)". Local checkout; not vendored here.
  <https://github.com/ggml-org/llama.cpp>
- **llama-bench**, the `llama-bench` target in that checkout. The Vulkan binary
  reports build 11310; the ROCm binary reports build 0 / unknown commit.
- **Mesa / RADV** 26.0.8, Vulkan 1.4.341, as reported by `vulkaninfo --summary`
  on 2026-11-05. The driver version at the time of the archived runs is not
  recorded.
- **ROCm** 10.0 in the archived Dockerfile (`amdrocm-core-dev10.0-gfx1150`).
  The runtime actually used for the ROCm runs is unresolved; see
  `docs/hardware.md`.

## Models

- **Qwen3.6-35B-A3B**, Apache-2.0, quantized to `UD-IQ4_NL` by Unsloth.
  Metadata read from the GGUF, not from an external card. The exact file is
  identified by size and SHA256 in `config/models.json`.
- **Qwen3.6-35B-A3B-DFlash2** (BF16 draft), Apache-2.0. Configuration read from
  the checkpoint: 6 hidden layers, block size 8, 8 target layers.
  Referenced in the archived notes as `incoai/Qwen3.6-35B-A3B-DFlash2`.
- **Qwen3.6-35B-A3B-DFlash** (BF16 draft, older generation), block size 16.
  Used only by `data/raw/dflash-rocm-server-2026-10-01.log`. Do not conflate it
  with DFlash2.
- **Qwen3.6 MTP** variant, `Qwen3.6-35B-A3B-UD-IQ4_NL.gguf` with
  `qwen35moe.nextn_predict_layers = 1`. Used by the 2026-10-18 speculative
  comparison.
- **LFM2.5-8B-A1B**, `UD-IQ4_NL` and `UD-Q8_K_XL`. Used for the harness smoke
  test and the coding-agent workload.

## Hardware documentation

- **AMD Ryzen AI 9 HX 375** and **Radeon 890M**, `gfx1150`. Vendor product
  pages describe the 890M as a 16-CU RDNA 3.5 iGPU; the core count is **not**
  measured in this repository, so it is cited as vendor specification only.
- **LPDDR5X**. The 120 GB/s peak used in the roofline is an assumption for
  LPDDR5X-7500 on a 128-bit bus. The exact memory part and speed on this machine
  were not recorded (`dmidecode` needs interactive sudo). The 102.4 and
  128 GB/s bounds correspond to LPDDR5X-6400 and -8000.
- **JEDEC JESD209-5**, LPDDR5/LPDDR5X standard, for the signalling-rate to
  bandwidth relationship. Used as background, not as a measurement.

## Measurement practice

- **llama.cpp `llama-bench` documentation** for the meaning of `-p`, `-n`,
  `-d`, `-r`, `-ngl`, `-fa`, `-b`, `-ub`. Flags are also visible in
  `scripts/bench.sh`.
- **Efron & Tibshirani, *An Introduction to the Bootstrap* (1993)** for the
  percentile bootstrap used in `scripts/stats.py`. The implementation is 30
  lines of standard library; the reference explains the assumption (resampling
  approximates the sampling distribution) and its limits at n=9.
- **Hoefler & Belli, "Scientific Benchmarking of Parallel Computing Systems"
  (SC'15)** for why repeated, paired, order-randomised runs matter and why a
  single number without spread is not a result. This repository's protocols are
  a small-scale application of those ideas, not a full implementation.

## Prior art and context

- **Speculative decoding**: Leviathan et al., "Fast Inference from Transformers
  via Speculative Decoding" (2023); Chen et al., "Accelerating Large Language
  Model Decoding with Speculative Sampling" (2023). Background for why draft
  acceptance and verification cost both matter.
- **Mixture-of-experts inference**: Shazeer et al. (2017) and the Switch
  Transformer (Fedus et al., 2022) for the routing idea. Neither paper measures
  this hardware.
- **Roofline model**: Williams, Waterman & Patterson, "Roofline: An Insightful
  Visual Performance Model for Multicore Architectures" (CACM 2009). The
  analysis in `analysis/roofline.md` is a memory-roofline sketch, not a full
  roofline with compute ceilings.

## What is deliberately not cited

- Vendor benchmark slides and marketing throughput for the 890M. They are not
  measurements of this machine or this model.
- Upstream issue and PR numbers quoted in the archived conversation, except the
  one that appears in the measured commit subject. They were not verified
  against upstream during this work.
- Other machines' `gfx1151` results that circulated in the source notes. They
  are neither this machine nor a transferable reference, and the archived
  research bundle already flags them as unverified.

## How to cite this repository

See `CITATION.cff`. The short form:

> igpu-llm-bench contributors. *igpu-llm-bench: Vulkan vs ROCm decode throughput
> on an AMD Strix Point iGPU.* 2026. Private repository.
