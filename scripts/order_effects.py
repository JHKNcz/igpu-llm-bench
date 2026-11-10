#!/usr/bin/env python3
"""Test whether a measured difference is order or thermal drift.

Reads one or more ``ab.csv`` files from ``ab_campaign.py`` and reports:

1. the per-round ratio between backends, so a claim has to hold in every round,
   not just on average;
2. the rank correlation between a run's position in its round and its
   throughput, which detects warm-up or drift within a round;
3. the rank correlation between round number and throughput, which detects
   drift across rounds.

A difference that reverses sign between rounds, or that correlates with
position rather than with the variable under test, is not a result.
"""

from __future__ import annotations

import argparse
import csv
import statistics
import sys
from pathlib import Path


def spearman(xs: list[float], ys: list[float]) -> float | None:
    """Rank correlation, no dependencies."""
    n = len(xs)
    if n < 4:
        return None

    def ranks(values: list[float]) -> list[float]:
        order = sorted(range(n), key=lambda i: values[i])
        out = [0.0] * n
        i = 0
        while i < n:
            j = i
            while j + 1 < n and values[order[j + 1]] == values[order[i]]:
                j += 1
            avg = (i + j) / 2 + 1
            for k in range(i, j + 1):
                out[order[k]] = avg
            i = j + 1
        return out

    rx, ry = ranks(xs), ranks(ys)
    mx, my = statistics.mean(rx), statistics.mean(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = (sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry)) ** 0.5
    return num / den if den else None


def load(paths: list[Path]) -> list[dict[str, str]]:
    rows = []
    for path in paths:
        with path.open(newline="") as handle:
            for row in csv.DictReader(handle):
                if row.get("status") == "ok" and row.get("test") == "tg128":
                    rows.append(row)
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", nargs="+", type=Path)
    args = parser.parse_args()

    rows = load(args.csv)
    if not rows:
        raise SystemExit("no tg128 rows")

    groups: dict[tuple, list[dict[str, str]]] = {}
    for row in rows:
        key = (row["model"], row["quant"], row["kv"], int(row["depth"]))
        groups.setdefault(key, []).append(row)

    for key in sorted(groups):
        model, quant, kv, depth = key
        print(f"\n## {model} {quant} KV={kv} depth={depth}\n")
        data = groups[key]
        backends = sorted({r["backend"] for r in data})
        rounds = sorted({int(r["round"]) for r in data})

        print("| round | " + " | ".join(backends) + " |")
        print("|---:|" + "|".join(["---:"] * len(backends)) + "|")
        per_round: dict[int, dict[str, float]] = {}
        for rnd in rounds:
            cells = {}
            for backend in backends:
                vals = [
                    float(r["tps"]) for r in data
                    if int(r["round"]) == rnd and r["backend"] == backend
                ]
                if vals:
                    cells[backend] = statistics.median(vals)
            per_round[rnd] = cells
            print(
                f"| {rnd} | "
                + " | ".join(f"{cells[b]:.2f}" if b in cells else "—" for b in backends)
                + " |"
            )

        if "vulkan" in backends and "rocm" in backends:
            ratios = [
                per_round[r]["vulkan"] / per_round[r]["rocm"]
                for r in rounds
                if "vulkan" in per_round[r] and "rocm" in per_round[r]
            ]
            if ratios:
                sign = {"Vulkan" if r > 1.05 else "ROCm" if r < 0.95 else "tie" for r in ratios}
                print(
                    f"\nVulkan/ROCm per round: "
                    + ", ".join(f"{r:.2f}x" for r in ratios)
                    + f" — winner per round: {', '.join(sorted(sign))}"
                )
                if len(sign) == 1:
                    print("**Consistent across rounds.**")
                else:
                    print("**Inconsistent across rounds — do not claim a winner.**")

        positions = [float(r["position"]) for r in data]
        tps = [float(r["tps"]) for r in data]
        rho_pos = spearman(positions, tps)
        rho_round = spearman([float(r["round"]) for r in data], tps)
        print(
            f"\nrank correlation tps~position: "
            f"{rho_pos:+.2f}" if rho_pos is not None else "\nrank correlation tps~position: n/a",
            end="",
        )
        print(
            f"   tps~round: {rho_round:+.2f}" if rho_round is not None else "   tps~round: n/a"
        )
        print("(|rho| > 0.6 suggests the run order, not the variable, is driving the number)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
