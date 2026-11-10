#!/usr/bin/env python3
"""Depth-0 roofline for the campaign models.

At depth 0 the KV cache is negligible, so the per-token traffic is dominated by
the active weights. That makes depth 0 the cleanest place to ask: how much of
the assumed memory bandwidth is this configuration actually using?

    active_weight_bytes = model_bytes x (active_params / total_params)
    effective_GB/s      = active_weight_bytes x tps / 1e9

The active-parameter counts come from `config/models.json` and are vendor
labels, not measured activation counts. The peak bandwidth is an assumption.
Both are stated in the output so the numbers cannot be read as measurements of
memory traffic.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# model label in the campaign CSV -> key in config/models.json
MODEL_KEYS = {
    ("LFM2.5-8B-A1B", "UD-IQ4_NL"): "lfm_iq4_nl",
    ("LFM2.5-8B-A1B", "UD-Q8_K_XL"): "lfm_q8_k_xl",
    ("Qwen3-VL-4B-Instruct", "UD-Q8_K_XL"): "qwen3vl_4b_q8",
    ("Qwen3.6-35B-A3B-MTP", "UD-IQ4_NL"): "mtp_qwen35",
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("campaign_csv", type=Path)
    parser.add_argument("--config", type=Path, default=ROOT / "config/models.json")
    parser.add_argument("--peak-gbps", type=float, default=120.0)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    config = json.loads(args.config.read_text())
    peak = args.peak_gbps

    with args.campaign_csv.open(newline="") as handle:
        rows = [r for r in csv.DictReader(handle) if r.get("status") == "ok"]

    out: list[dict[str, object]] = []
    for row in rows:
        if row["test"] != "tg128" or row["depth"] != "0" or row["threads"] != "12":
            continue
        key = MODEL_KEYS.get((row["model"], row["quant"]))
        if not key:
            continue
        entry = config["models"].get(key, {})
        total = float(row["params_b"])
        active = entry.get("active_params_b")
        if active is None:
            active = config["roofline"]["models"].get(key, {}).get("active_params_b")
        if active is None:
            continue
        size_bytes = float(row["size_gib"]) * 2**30
        active_bytes = size_bytes * (float(active) / total)
        tps = float(row["tps"])
        effective = active_bytes * tps / 1e9
        out.append(
            {
                "model": row["model"],
                "quant": row["quant"],
                "kv": row["kv"],
                "size_gib": row["size_gib"],
                "total_params_b": total,
                "active_params_b": float(active),
                "active_weight_gb": round(active_bytes / 1e9, 3),
                "tg128_tps": tps,
                "effective_gbps": round(effective, 2),
                "pct_of_peak": round(100 * effective / peak, 1),
                "peak_gbps": peak,
                "noisy": row.get("noisy", ""),
            }
        )

    if not out:
        raise SystemExit("no depth-0 tg128 rows with thread=12")

    print(f"peak assumed: {peak:.0f} GB/s\n")
    print("| model | quant | size GiB | active/total | active GB/tok | t/s | effective GB/s | % peak |")
    print("|---|---|---:|---:|---:|---:|---:|---:|")
    for r in out:
        print(
            f"| {r['model']} | {r['quant']} | {r['size_gib']} | "
            f"{r['active_params_b']:.1f}/{r['total_params_b']:.2f} B | "
            f"{r['active_weight_gb']:.3f} | {r['tg128_tps']:.2f} | "
            f"{r['effective_gbps']:.2f} | {r['pct_of_peak']:.1f}% |"
        )

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(out[0].keys()))
            writer.writeheader()
            writer.writerows(out)
        print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
