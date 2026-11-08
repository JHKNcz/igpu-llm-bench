# Long-context KV-cache comparison

*Source: `~/LLM/testing_resources/speculative_compare/long-context-results/20261018-203923-240284/`,
started 2026-10-18T18:39:23Z. The harness and prompts are not included; the
summary and measurements are. This is a separate experiment from the
`llama-bench` depth rows.*

## Method

| Setting | Value |
|---|---|
| Backend | Vulkan, build `f872b5911 (11310)` |
| Context capacity | 65,536 tokens |
| Actual input depths | approximately 4,096, 32,768, 61,440 tokens |
| Modes | MTP (2 draft tokens), DFlash2 (6 draft tokens) |
| Main K/V cache | F16, then Q8_0 |
| Draft K/V cache | F16 |
| Rounds | 2 |
| Output | 256 tokens per request |
| Sampling | greedy |
| Thinking | off |
| Prompt-prefix reuse | disabled |
| Measured requests | 24 |
| Retrieval check | 9 fields near the beginning, middle, and end of the prompt |

The suite tests actual long inputs, not only a 64K context allocation. It is a
throughput and retrieval check, not a general long-context quality benchmark.

## Results

| Depth | Mode | KV | Generation t/s | Prompt t/s | Draft acceptance | Retrieval |
|---:|---|---|---:|---:|---:|---:|
| 4,096 | MTP | F16 | 33.67 | 334.80 | 81.4% | 9/9 |
| 4,096 | MTP | Q8_0 | 38.15 | 430.77 | 84.2% | 9/9 |
| 4,096 | DFlash2 | F16 | 32.24 | 339.90 | 57.3% | 9/9 |
| 4,096 | DFlash2 | Q8_0 | 32.66 | 370.70 | 57.0% | 9/9 |
| 32,768 | MTP | F16 | 25.40 | 195.04 | 82.8% | 9/9 |
| 32,768 | MTP | Q8_0 | 29.47 | 362.03 | 82.8% | 9/9 |
| 32,768 | DFlash2 | F16 | 27.76 | 224.72 | 57.4% | 9/9 |
| 32,768 | DFlash2 | Q8_0 | 23.52 | 313.36 | 52.4% | 9/9 |
| 61,440 | MTP | F16 | 21.99 | 133.21 | 83.2% | 9/9 |
| 61,440 | MTP | Q8_0 | 22.00 | 270.13 | 81.4% | 9/9 |
| 61,440 | DFlash2 | F16 | 22.13 | 155.00 | 54.8% | 9/9 |
| 61,440 | DFlash2 | Q8_0 | 18.65 | 265.08 | 52.6% | 9/9 |

## What the table shows

- Generation throughput falls with depth for every mode. MTP F16: 33.67 → 25.40
  → 21.99 t/s; DFlash2 F16: 32.24 → 27.76 → 22.13 t/s. This is consistent with
  KV/recurrent-state traffic consuming memory bandwidth, but it is not proof;
  see `analysis/roofline.md`.
- Q8_0 KV substantially improves **prompt processing** at 32K and 61K (for
  example, MTP 195 → 362 t/s at 32K, 133 → 270 t/s at 61K), but its effect on
  **generation** is mixed: it helps MTP at 4K/32K, is neutral for MTP at 61K,
  and hurts DFlash2 at 61K (18.65 vs 22.13 t/s).
- Retrieval accuracy is 9/9 in every cell. This is a narrow synthetic check, not
  evidence of general long-context quality.

## Caveats

- Two rounds, one prompt per depth, 24 measured requests.
- Speculative modes only; there is no 61K baseline without drafting.
- The 61K depth is a filled context, but the prompt is synthetic.
- VRAM peak was approximately 14.7–15.2 GiB, consistent with a 16 GiB carve-out
  at the time; the current machine is at 512 MiB, so this is not reproducible
  without changing the carve-out.
- Generation t/s is not end-to-end request time and does not include answer
  quality.
