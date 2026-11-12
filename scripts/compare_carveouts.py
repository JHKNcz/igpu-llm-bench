#!/usr/bin/env python3
"""Compare the same configuration measured at two VRAM carve-outs.

Joins two campaign CSVs on (backend, model, quant, kv, depth, test, threads)
and reports the ratio between them. Nothing is compared across different
configurations, and a missing side stays missing.

Ratio is new/old, so >1 means the new carve-out is faster.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load(paths: list[Path]) -> dict[tuple, dict[str, str]]:
    best: dict[tuple, dict[str, str]] = {}
    for path in paths:
        with path.open(newline="") as handle:
            for row in csv.DictReader(handle):
                if row.get("status") != "ok":
                    continue
                key = (
                    row.get("backend", "").lower(), row["model"], row["quant"],
                    row["kv"], int(row["depth"]), row["test"], row["threads"],
                )
                # prefer a clean row over a noisy one
                if key in best and best[key].get("noisy") == "yes" and row.get("noisy") != "yes":
                    best[key] = row
                elif key not in best:
                    best[key] = row
    return best


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--old", nargs="+", type=Path, required=True, help="0.5 GB run")
    parser.add_argument("--new", nargs="+", type=Path, required=True, help="16 GB run")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    old = load(args.old)
    new = load(args.new)
    keys = sorted(set(old) & set(new), key=lambda k: (k[1], k[2], k[3], k[4], k[5]))

    print("| model | quant | KV | depth | test | thr | 0.5 GB | 16 GB | ratio |")
    print("|---|---|---|---:|---|---:|---:|---:|---:|")
    rows = []
    for key in keys:
        backend, model, quant, kv, depth, test, threads = key
        a = float(old[key]["tps"])
        b = float(new[key]["tps"])
        ratio = b / a
        print(f"| {model} | {quant} | {kv} | {depth} | {test} | {threads} | {a:.2f} | {b:.2f} | {ratio:.2f}x |")
        rows.append(
            {
                "backend": backend, "model": model, "quant": quant, "kv": kv,
                "depth": depth, "test": test, "threads": threads,
                "tps_0_5gb": a, "tps_16gb": b, "ratio": round(ratio, 3),
            }
        )

    if args.out and rows:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        print(f"\nwrote {args.out}")
    print(f"\n{len(rows)} matched configurations")
    return 0


if __name__ == "__main__":
    sys.exit(main())
