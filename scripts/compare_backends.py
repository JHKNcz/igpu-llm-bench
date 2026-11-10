#!/usr/bin/env python3
"""Join Vulkan and ROCm campaign CSVs into a backend comparison.

Rules that keep this honest:

* Rows are matched on (model, quant, kv, depth, test, threads). Nothing is
  compared across different configurations.
* When the same key appears more than once, a row flagged ``noisy`` is
  discarded in favour of a clean one. If both are clean, the later file wins.
* A ratio is only printed when both sides exist. Missing cells stay missing;
  they are not filled in from another depth or another model.
* The ratio is Vulkan / ROCm, so >1 means Vulkan faster, <1 means ROCm faster.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load(paths: list[Path]) -> dict[tuple, dict]:
    best: dict[tuple, dict] = {}
    for order, path in enumerate(paths):
        with path.open(newline="") as handle:
            for row in csv.DictReader(handle):
                if row.get("status") != "ok":
                    continue
                key = (
                    row["model"], row["quant"], row["kv"],
                    int(row["depth"]), row["test"], row["threads"],
                )
                noisy = (row.get("noisy") or "") == "yes"
                candidate = {"row": row, "noisy": noisy, "order": order}
                current = best.get(key)
                if current is None:
                    best[key] = candidate
                elif current["noisy"] and not noisy:
                    best[key] = candidate
                elif current["noisy"] == noisy and order >= current["order"]:
                    best[key] = candidate
    return best


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vulkan", nargs="+", type=Path, required=True)
    parser.add_argument("--rocm", nargs="+", type=Path, required=True)
    parser.add_argument("--test", default="tg128")
    parser.add_argument("--threads", default="12")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    v = load(args.vulkan)
    r = load(args.rocm)

    keys = sorted(
        {k for k in set(v) | set(r) if k[4] == args.test and k[5] == args.threads},
        key=lambda k: (k[0], k[1], k[2], k[3]),
    )

    out_rows = []
    print(f"| model | quant | KV | depth | Vulkan t/s | ROCm t/s | Vulkan/ROCm | winner |")
    print("|---|---|---|---:|---:|---:|---:|---|")
    for key in keys:
        model, quant, kv, depth, _, _ = key
        a = v.get(key)
        b = r.get(key)
        av = float(a["row"]["tps"]) if a else None
        bv = float(b["row"]["tps"]) if b else None
        ratio = (av / bv) if (av and bv) else None
        if ratio is None:
            winner = "Vulkan only" if av else "ROCm only"
        elif ratio > 1.05:
            winner = "Vulkan"
        elif ratio < 0.95:
            winner = "ROCm"
        else:
            winner = "tie"
        a_txt = f"{av:.2f}" if av is not None else "—"
        b_txt = f"{bv:.2f}" if bv is not None else "—"
        r_txt = f"{ratio:.2f}x" if ratio is not None else "—"
        print(f"| {model} | {quant} | {kv} | {depth} | {a_txt} | {b_txt} | {r_txt} | {winner} |")
        out_rows.append(
            {
                "model": model, "quant": quant, "kv": kv, "depth": depth,
                "vulkan_tps": av, "rocm_tps": bv,
                "vulkan_over_rocm": round(ratio, 3) if ratio else None,
                "winner": winner,
            }
        )

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(out_rows[0].keys()))
            writer.writeheader()
            writer.writerows(out_rows)
        print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
