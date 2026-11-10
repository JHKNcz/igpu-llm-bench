# Contributing

This is a small research artifact, not a framework. Contributions are welcome
if they keep the repository honest and reproducible. The bar is: **a stranger
must be able to check your number.**

## What is useful

- **A replication on different hardware.** Same model, same protocol, your
  numbers. This is the single most valuable contribution, because the current
  claims rest on one machine.
- **A controlled backend A/B.** Same build, same carve-out, same CLI, alternating
  order, ≥5 repetitions. This would replace the weakest result in the repo.
- **A correction.** If a number is wrong, say which file, which line, and what
  the right value is. Corrections are not an insult; stale numbers are.
- **A missing measurement** from `docs/limitations.md`, with the raw log.
- **A better explanation** of a roofline hypothesis, clearly labelled as a
  hypothesis.

## What is not useful

- Throughput numbers without the model hash, build, carve-out, and protocol.
- Results that compare `tg128` to wall TPS, or a 512-token capacity setting to a
  filled 64K context.
- "It feels faster" without a paired measurement.
- Vendor benchmark slides.
- Anything containing credentials, personal paths, or someone else's data.

## Adding a run

1. Put the raw log in `data/raw/` with a name that encodes backend and date:
   `llama-bench-vulkan-YYYY-MM-DD.txt`.
2. Add a row to `data/provenance.md`: repository file, original source, date,
   transformation, what it supports.
3. If it is a new experiment type, add a section to `RESULTS.md` and a page under
   `docs/related/`.
4. Regenerate derived data:

```bash
python3 scripts/parse_logs.py
python3 scripts/roofline.py
python3 scripts/stats.py
python3 scripts/chart.py
python3 scripts/verify_results.py
```

5. Update `data/checksums.txt`:

```bash
find . -type f -not -path './.git/*' -not -path './runs/*' \
  -not -path '*/__pycache__/*' -not -path './data/checksums.txt' \
  -print0 | sort -z | xargs -0 sha256sum | sed 's#  \./#  #' > data/checksums.txt
```

6. Run the privacy scan:

```bash
python3 scripts/secret_scan.py
```

## Running a campaign

`scripts/campaign.py` runs a matrix of model / KV-type / depth / thread
configurations at whatever memory setting the machine currently has, samples
temperature and power during each run, and writes one CSV row per measurement.
It records the carve-out with every row, and it records load failures as rows
rather than hiding them.

```bash
MODELS_DIR=$HOME/LLM/LLMs \
LLAMA_BENCH=$HOME/llama.cpp/build-vulkan/bin/llama-bench \
make campaign
```

`scripts/capacity_probe.py` answers the other question at a small carve-out:
how many layers can be offloaded before the model stops loading.

```bash
make capacity LLAMA_BENCH=... MODEL=... LABEL=my-model
```

Both write to `runs/`, which is git-ignored. Promote a run into `data/` only
after sanitising it and adding a provenance row.

## Style

- **Numbers carry sources.** Every table row has a file, and ideally a line.
- **Uncertainty is stated.** A point estimate without a spread is not a result.
- **Hypotheses are labelled.** "Plausibly" and "consistent with" are fine;
  "proves" is not, unless it does.
- **Comparisons state their protocol.** If two rows use different metrics, say
  so in the table header or the surrounding prose.
- **"Not recorded" is a valid value.** Do not invent a plausible number.
- **Do not reformat unrelated files.** Small diffs are reviewable diffs.

## Commit messages

Short imperative subject, then a body explaining what changed and why. If a
number changed, say the old value, the new value, and the reason.

```
Correct KV bytes/token after the hybrid-layer check

The model has 10 full-attention layers, not 40, so the KV term is
20,480 bytes/token. Roofline effective bandwidth rises accordingly;
the 2.32x raw ratio is unchanged.
```

## Review

Because the repository is private, review happens with the owner directly.
Expect questions about provenance and about whether a difference survives its
own uncertainty.

## Licensing

By contributing you agree that code is MIT and text/data is CC BY 4.0, matching
`LICENSE` and `LICENSE-DATA`.
