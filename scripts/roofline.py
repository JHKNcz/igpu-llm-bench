#!/usr/bin/env python3
"""Compute a first-order memory roofline for the archived decode measurements.

The model is a mixture-of-experts model. Only the active experts are read for a
given token, so the per-token weight traffic is approximated as

    active_weight_bytes = model_bytes * (active_params / total_params)

The attention KV cache is read once per generated token in this first-order
model; the 30 SSM layers' recurrent state is excluded:

    kv_bytes = depth * kv_bytes_per_token

Both terms are lower/upper-bound approximations, not measured memory counters.
The output is a hypothesis-generating table, not a performance proof.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUT = ROOT / "data/processed/llama-bench.csv"
DEFAULT_CONFIG = ROOT / "config/models.json"
DEFAULT_OUT = ROOT / "data/processed/roofline.csv"


def load_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--peak-gbps", type=float, default=None)
    parser.add_argument("--kv-bytes-per-token", type=int, default=None)
    args = parser.parse_args()

    config = json.loads(args.config.read_text())
    roof = config["roofline"]
    peak = args.peak_gbps if args.peak_gbps is not None else float(roof["peak_gbps"])
    kv_per_token = (
        args.kv_bytes_per_token
        if args.kv_bytes_per_token is not None
        else int(roof["kv_bytes_per_token"])
    )
    total_params = float(roof["total_params_b"])
    active_params = float(roof["active_params_b"])
    active_fraction = active_params / total_params

    rows = load_rows(args.input)
    out: list[dict[str, object]] = []
    for row in rows:
        size_gib = float(row["size_gib"])
        depth = int(row["depth"])
        tps = float(row["tps"])
        model_bytes = size_gib * (2**30)
        active_weight_bytes = model_bytes * active_fraction
        kv_bytes = depth * kv_per_token
        total_bytes = active_weight_bytes + kv_bytes
        effective_gbps = total_bytes * tps / 1e9
        out.append(
            {
                "backend": row["backend"],
                "test": row["test"],
                "depth": depth,
                "tps": tps,
                "active_weight_gb": round(active_weight_bytes / 1e9, 4),
                "kv_gb": round(kv_bytes / 1e9, 4),
                "total_gb_per_token": round(total_bytes / 1e9, 4),
                "effective_gbps": round(effective_gbps, 3),
                "peak_gbps": peak,
                "pct_peak": round(100.0 * effective_gbps / peak, 1),
                "source_file": row["source_file"],
                "source_line": row["source_line"],
            }
        )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(out[0].keys()))
        writer.writeheader()
        writer.writerows(out)

    print(f"peak: {peak:.1f} GB/s")
    print(f"active fraction: {active_fraction:.6f} ({active_params:.2f}/{total_params:.2f} B)")
    print(f"KV: {kv_per_token} bytes/token")
    print()
    print("| backend | test | t/s | weight GB/tok | KV GB/tok | total GB/tok | effective GB/s | % peak |")
    print("|---|---|---:|---:|---:|---:|---:|---:|")
    for row in out:
        print(
            f"| {row['backend']} | {row['test']} | {row['tps']:.2f} | "
            f"{row['active_weight_gb']:.3f} | {row['kv_gb']:.3f} | "
            f"{row['total_gb_per_token']:.3f} | {row['effective_gbps']:.2f} | "
            f"{row['pct_peak']:.1f}% |"
        )
    print()
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
