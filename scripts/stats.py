#!/usr/bin/env python3
"""Statistics for the archived measurements.

Two jobs:

1. Summarise each mode in the speculative comparison (median, MAD, IQR).
2. Compute *paired* speedups and a bootstrap confidence interval for them.

The pairing matters. Each of the 9 samples per mode is a (prompt, round) cell,
and every mode ran in every cell. Comparing two medians taken independently
throws that structure away and overstates the uncertainty. The paired ratio
divides within a cell first, then summarises the 9 ratios, which is the
comparison the experiment actually supports.

Bootstrap: resample the 9 paired ratios with replacement, 20,000 times, seeded,
and report the 2.5th and 97.5th percentiles. With n=9 this interval is wide and
that is the point; it is not a claim of precision.

Standard library only.
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUT = ROOT / "data/processed/speculative-measurements.csv"
DEFAULT_OUT = ROOT / "data/processed/speculative-stats.json"

MODES = ["baseline", "dflash2", "mtp_off", "mtp"]
BASELINES = ["baseline", "mtp_off"]


def median_mad(values: list[float]) -> tuple[float, float]:
    """Median and median absolute deviation (unscaled)."""
    med = statistics.median(values)
    mad = statistics.median([abs(v - med) for v in values])
    return med, mad


def quartiles(values: list[float]) -> tuple[float, float]:
    """Simple quartiles via linear interpolation between order statistics."""
    ordered = sorted(values)
    n = len(ordered)

    def at(p: float) -> float:
        pos = p * (n - 1)
        lo = int(pos)
        hi = min(lo + 1, n - 1)
        frac = pos - lo
        return ordered[lo] * (1 - frac) + ordered[hi] * frac

    return at(0.25), at(0.75)


def bootstrap_ci(
    values: list[float], iterations: int = 20_000, seed: int = 20261018
) -> tuple[float, float]:
    """Percentile bootstrap CI for the median of ``values``."""
    rng = random.Random(seed)
    n = len(values)
    medians = []
    for _ in range(iterations):
        sample = [values[rng.randrange(n)] for _ in range(n)]
        medians.append(statistics.median(sample))
    medians.sort()
    lo = medians[int(0.025 * iterations)]
    hi = medians[int(0.975 * iterations) - 1]
    return lo, hi


def load_cells(path: Path) -> dict[tuple[str, int], dict[str, float]]:
    """Map (case, repeat) -> {mode: generation_tps}."""
    cells: dict[tuple[str, int], dict[str, float]] = {}
    with path.open(newline="") as handle:
        for row in csv.DictReader(handle):
            key = (row["case"], int(row["repeat"]))
            cells.setdefault(key, {})[row["mode"]] = float(row["generation_tps"])
    return cells


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--iterations", type=int, default=20_000)
    args = parser.parse_args()

    cells = load_cells(args.input)
    if not cells:
        raise SystemExit(f"no measurements in {args.input}")

    incomplete = [k for k, v in cells.items() if set(v) != set(MODES)]
    if incomplete:
        raise SystemExit(f"incomplete cells, refusing to pair: {incomplete}")

    summary: dict[str, dict[str, object]] = {}
    for mode in MODES:
        values = [cell[mode] for cell in cells.values()]
        med, mad = median_mad(values)
        q1, q3 = quartiles(values)
        lo, hi = bootstrap_ci(values, args.iterations)
        summary[mode] = {
            "samples": len(values),
            "median_generation_tps": round(med, 3),
            "mad": round(mad, 3),
            "iqr": [round(q1, 3), round(q3, 3)],
            "median_ci95": [round(lo, 3), round(hi, 3)],
            "min": round(min(values), 3),
            "max": round(max(values), 3),
        }

    # Paired ratios: divide inside each cell, then summarise across cells.
    for baseline in BASELINES:
        for mode in MODES:
            if mode == baseline:
                continue
            ratios = [cell[mode] / cell[baseline] for cell in cells.values()]
            med, mad = median_mad(ratios)
            lo, hi = bootstrap_ci(ratios, args.iterations)
            summary[mode].setdefault("paired_vs", {})[baseline] = {
                "median_ratio": round(med, 3),
                "mad": round(mad, 3),
                "ci95": [round(lo, 3), round(hi, 3)],
                "min": round(min(ratios), 3),
                "max": round(max(ratios), 3),
                "cells": len(ratios),
            }

    payload = {
        "source": str(args.input.relative_to(ROOT)),
        "bootstrap_iterations": args.iterations,
        "seed": 20261018,
        "method": "paired within (case, repeat); percentile bootstrap of the median",
        "modes": summary,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2) + "\n")

    print(f"{'mode':10} {'median':>8} {'MAD':>7} {'IQR':>16} {'95% CI of median':>22}")
    for mode in MODES:
        s = summary[mode]
        iqr = f"{s['iqr'][0]:.2f}-{s['iqr'][1]:.2f}"
        ci = f"{s['median_ci95'][0]:.2f}-{s['median_ci95'][1]:.2f}"
        print(f"{mode:10} {s['median_generation_tps']:>8.2f} {s['mad']:>7.2f} {iqr:>16} {ci:>22}")

    print()
    print("paired speedups (ratio computed inside each cell, then median):")
    for baseline in BASELINES:
        for mode in MODES:
            if mode == baseline:
                continue
            p = summary[mode]["paired_vs"][baseline]
            print(
                f"  {mode:9} vs {baseline:9} "
                f"{p['median_ratio']:.3f}x  95% CI {p['ci95'][0]:.3f}-{p['ci95'][1]:.3f}  "
                f"range {p['min']:.2f}-{p['max']:.2f}  n={p['cells']}"
            )

    print()
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
