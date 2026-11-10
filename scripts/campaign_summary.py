#!/usr/bin/env python3
"""Summarise a campaign CSV into tables and a cleaned dataset.

Reads ``runs/campaign-*/campaign.csv`` and produces:

* ``data/processed/campaign-<stamp>.csv`` — the measurements, promoted as-is
  apart from column ordering.
* a markdown report on stdout, ready to paste into ``docs/related/``.

The summaries deliberately avoid modelled KV bytes. Throughput retention with
depth is measured directly, and the F16-vs-Q8_0 delta is measured directly, so
neither depends on guessing a model's attention geometry.
"""

from __future__ import annotations

import argparse
import csv
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return [r for r in csv.DictReader(handle) if r.get("status") == "ok"]


def fnum(value: str | None) -> float | None:
    try:
        return float(value) if value not in (None, "") else None
    except ValueError:
        return None


def md_table(headers: list[str], rows: list[list[str]]) -> str:
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(headers)) + "|"]
    out += ["| " + " | ".join(r) + " |" for r in rows]
    return "\n".join(out)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", type=Path)
    parser.add_argument("--out-dir", type=Path, default=ROOT / "data/processed")
    args = parser.parse_args()

    rows = load(args.csv)
    if not rows:
        raise SystemExit("no successful rows")

    stamp = args.csv.parent.name.replace("campaign-", "")
    out_csv = args.out_dir / f"campaign-{stamp}.csv"
    args.out_dir.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    carveout = rows[0].get("carveout_mib", "?")
    gtt = rows[0].get("gtt_mib", "?")
    host = rows[0].get("host_mib", "?")

    print(f"# Campaign {stamp}\n")
    print(f"Carve-out: {carveout} MiB VRAM, {gtt} MiB GTT, {host} MiB host RAM. "
          f"{len(rows)} successful measurements.\n")

    # 1. depth-0 decode and prefill
    zero = [r for r in rows if r["depth"] == "0"]
    table = []
    for r in sorted(zero, key=lambda x: (x["model"], x["quant"], x["kv"], x["threads"])):
        if r["test"] not in ("tg128", "pp512"):
            continue
        table.append([
            r["model"], r["quant"], r["kv"], r["threads"],
            f"{fnum(r['tps']):.2f}", f"±{fnum(r['tps_sd']):.2f}", r["test"],
        ])
    print("## Depth 0\n")
    print(md_table(["model", "quant", "KV", "threads", "t/s", "spread", "test"], table))

    # 2. throughput retention with depth, per model/quant/kv
    print("\n## Retention with depth (tg128 relative to depth 0)\n")
    base: dict[tuple[str, str, str], float] = {}
    for r in rows:
        if r["test"] == "tg128" and r["depth"] == "0" and r["threads"] == "12":
            base[(r["model"], r["quant"], r["kv"])] = fnum(r["tps"]) or 0.0
    depths = sorted({int(r["depth"]) for r in rows})
    header = ["model", "quant", "KV"] + [f"d{d}" for d in depths]
    table = []
    for key in sorted(base):
        line = list(key)
        for d in depths:
            match = [
                r for r in rows
                if r["test"] == "tg128" and r["depth"] == str(d)
                and (r["model"], r["quant"], r["kv"]) == key and r["threads"] == "12"
            ]
            line.append(f"{fnum(match[0]['tps']):.2f}" if match else "—")
        table.append(line)
    print(md_table(header, table))

    # 3. KV type effect at each depth
    print("\n## KV cache: F16 vs Q8_0\n")
    table = []
    for model, quant in sorted({(r["model"], r["quant"]) for r in rows}):
        for d in depths:
            f16 = [r for r in rows if r["test"] == "tg128" and r["depth"] == str(d)
                   and r["model"] == model and r["quant"] == quant and r["kv"] == "f16"]
            q8 = [r for r in rows if r["test"] == "tg128" and r["depth"] == str(d)
                  and r["model"] == model and r["quant"] == quant and r["kv"] == "q8_0"]
            if f16 and q8:
                a, b = fnum(f16[0]["tps"]), fnum(q8[0]["tps"])
                table.append([model, quant, str(d), f"{a:.2f}", f"{b:.2f}", f"{b / a:.3f}x"])
    print(md_table(["model", "quant", "depth", "F16 t/s", "Q8_0 t/s", "ratio"], table) if table else "_no paired KV runs_")

    # 4. thread scaling
    print("\n## Thread scaling (depth 0, tg128)\n")
    table = []
    for model, quant, kv in sorted({(r["model"], r["quant"], r["kv"]) for r in rows}):
        vals = {}
        for r in rows:
            if (r["test"] == "tg128" and r["depth"] == "0"
                    and (r["model"], r["quant"], r["kv"]) == (model, quant, kv)):
                vals[r["threads"]] = fnum(r["tps"])
        if len(vals) > 1:
            table.append([model, quant, kv] + [f"{t}:{v:.2f}" for t, v in sorted(vals.items(), key=lambda x: int(x[0]))])
    print(md_table(["model", "quant", "KV", "threads:t/s"], [[t[0], t[1], t[2], "  ".join(t[3:])] for t in table]) if table else "_no thread sweep_")

    # 4b. data quality
    noisy = [r for r in rows if (r.get("noisy") or "") == "yes"]
    print("\n## Data quality\n")
    if noisy:
        table = [[r["model"], r["quant"], r["kv"], r["test"], str(r["depth"]),
                  r["tps"], r["tps_sd"]] for r in noisy]
        print("Rows with spread above 15% of the mean. Treat these as noisy; "
              "a clean re-run is preferable to averaging them.")
        print()
        print(md_table(["model", "quant", "KV", "test", "depth", "t/s", "spread"], table))
    else:
        print("No row exceeded a 15% relative spread.")

    # 5. thermals
    print("\n## Thermals and power (max observed per configuration)\n")
    table = []
    seen = set()
    for r in rows:
        key = (r["model"], r["quant"], r["kv"], r["threads"])
        if key in seen:
            continue
        seen.add(key)
        table.append([
            r["model"], r["quant"], r["kv"], r["threads"],
            r.get("cpu_temp_c_max") or "—", r.get("gpu_temp_c_max") or "—",
            r.get("gpu_power_w_max") or "—",
        ])
    print(md_table(["model", "quant", "KV", "threads", "CPU °C", "GPU °C", "GPU W"], table))

    print(f"\nPromoted to `{out_csv.relative_to(ROOT)}`.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
