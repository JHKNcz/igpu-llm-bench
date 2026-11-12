# Models: exact sources and licences

Every model used here is a public Hugging Face release. This page records the
exact repository, revision, quantizer and licence, taken from the GGUF metadata
and verified against the Hugging Face API.

Model weights are **not** included in this repository. You must download them
and accept each licence yourself.

## What was measured

| File used | Base model (HF) | Published by (HF repo) | Revision | Licence | Size | Present |
|---|---|---|---|---|---|---|
| `Qwen3.6-35B-A3B-UD-IQ4_NL.gguf` | [Qwen/Qwen3.6-35B-A3B](https://huggingface.co/Qwen/Qwen3.6-35B-A3B) | [unsloth/Qwen3.6-35B-A3B-GGUF](https://huggingface.co/unsloth/Qwen3.6-35B-A3B-GGUF) | not recorded | Apache-2.0 | 16.79 GiB | **absent** |
| `Qwen3.6-35B-A3B-UD-IQ4_NL.gguf` (MTP) | [Qwen/Qwen3.6-35B-A3B](https://huggingface.co/Qwen/Qwen3.6-35B-A3B) | [unsloth/Qwen3.6-35B-A3B-MTP-GGUF](https://huggingface.co/unsloth/Qwen3.6-35B-A3B-MTP-GGUF) | `5bc3e238d916` | Apache-2.0 | 17.25 GiB | yes |
| `Qwen3.6-35B-A3B-DFlash2-BF16.gguf` | [incoai/Qwen3.6-35B-A3B-DFlash2](https://huggingface.co/incoai/Qwen3.6-35B-A3B-DFlash2) | converted locally from `model.safetensors` | `51ef7b6923ad` | Apache-2.0 | 0.99 GiB | **absent** |
| `Qwen3.6-35B-A3B-DFlash-BF16.gguf` | [z-lab/Qwen3.6-35B-A3B-DFlash](https://huggingface.co/z-lab/Qwen3.6-35B-A3B-DFlash) | converted locally from `model.safetensors` | `f181eece646a` | Apache-2.0 | 736 MiB | **absent** |
| `LFM2.5-8B-A1B-UD-IQ4_NL.gguf` | [LiquidAI/LFM2.5-8B-A1B](https://huggingface.co/LiquidAI/LFM2.5-8B-A1B) | [unsloth/LFM2.5-8B-A1B-GGUF](https://huggingface.co/unsloth/LFM2.5-8B-A1B-GGUF) | `37563684c4a6` | LFM1.0 | 4.06 GiB | yes |
| `LFM2.5-8B-A1B-UD-Q8_K_XL.gguf` | [LiquidAI/LFM2.5-8B-A1B](https://huggingface.co/LiquidAI/LFM2.5-8B-A1B) | [unsloth/LFM2.5-8B-A1B-GGUF](https://huggingface.co/unsloth/LFM2.5-8B-A1B-GGUF) | `37563684c4a6` | LFM1.0 | 8.70 GiB | yes |
| `Qwen3-VL-4B-Instruct-UD-Q8_K_XL.gguf` | [Qwen/Qwen3-VL-4B-Instruct](https://huggingface.co/Qwen/Qwen3-VL-4B-Instruct) | [unsloth/Qwen3-VL-4B-Instruct-GGUF](https://huggingface.co/unsloth/Qwen3-VL-4B-Instruct-GGUF) | `00c00da0690c` | Apache-2.0 | 4.71 GiB | yes |

Revision is the Hugging Face commit the local file was downloaded from, read
from `.cache/huggingface/download/*.metadata`. It is not the current head of the
repository; the repositories have moved on since.

## Two files with the same name

`Qwen3.6-35B-A3B-UD-IQ4_NL.gguf` exists in both
`unsloth/Qwen3.6-35B-A3B-GGUF` and `unsloth/Qwen3.6-35B-A3B-MTP-GGUF`. They are
different files:

| | Plain | MTP |
|---|---|---|
| Layers | 40 | 41 (`nextn_predict_layers = 1`) |
| Parameters | 34.66 B | 35.51 B |
| Size | 16.79 GiB | 17.25 GiB |
| SHA256 | `0d17e255…` | not recorded |

All 35B results in this repository use the **MTP** file. The archived 25.31 /
10.89 comparison used the plain file, which is not on disk, so the two are not
directly comparable.

## How these were verified

1. Read the local GGUF metadata:

```bash
PYTHONPATH=path/to/llama.cpp/gguf-py python3 - <<'EOF'
from gguf import GGUFReader
r = GGUFReader("model.gguf")
for k in ("general.quantized_by", "general.repo_url",
          "general.base_model.0.repo_url", "general.license"):
    if k in r.fields:
        print(k, "=", r.fields[k].contents())
EOF
```

2. Read the download revision from the Hugging Face cache:

```bash
head -1 ~/.cache/huggingface/download/<file>.gguf.metadata
```

3. Check that the revision exists in the candidate repository:

```bash
curl -s -o /dev/null -w '%{http_code}\n' \
  https://huggingface.co/api/models/unsloth/Qwen3.6-35B-A3B-MTP-GGUF/revision/5bc3e238d916f48a861bac2f8a1990a0e9b7e98d
# 200 means the revision is real
```

All five repositories above returned `200` for their recorded revision. The
plain 35B file has no recorded revision, because the file was removed before it
could be checked.

## Not verified

These appear in the archived historical table but were not used in the current
measurements, and their exact repositories were not verified:

- `Qwen3-Coder-30B-A3B-Instruct` Q5_K_M
- `Gemma 4 12B IT` UD-Q6_K_XL

If you reproduce those rows, record the repository and revision yourself.

## Licence summary

- Qwen models: Apache-2.0.
- DFlash / DFlash2 draft models: Apache-2.0.
- LFM2.5: **LFM1.0**, not Apache-2.0. Check the terms before commercial use.

Model licences are separate from this repository's licences (MIT for code,
CC BY 4.0 for text and data). See [`../DISCLAIMER.md`](../DISCLAIMER.md).
