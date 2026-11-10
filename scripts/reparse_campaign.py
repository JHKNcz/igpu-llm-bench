#!/usr/bin/env python3
"""Rebuild a campaign CSV from a saved llama-bench log, without re-running.

Useful when the parser gains support for another llama-bench output shape.
The raw log is the source of truth; the CSV is derived.

Sensor columns cannot be recovered from the log and are left empty.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from campaign import MODELS, parse_output  # noqa: E402

SECTION = re.compile(r"^### (?P<run_id>\S+) depth=(?P<depth>\d+) elapsed=(?P<elapsed>[\d.]+)s$")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path, help="runs/campaign-<stamp>")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    run_dir = args.run_dir
    log = run_dir / "llama-bench.log"
    meta = json.loads((run_dir / "metadata.json").read_text())
    carveout = meta.get("carveout", {})
    out = args.out or (run_dir / "campaign.csv")

    sections: list[tuple[str, str, list[str]]] = []
    current: tuple[str, str, list[str]] | None = None
    for line in log.read_text().splitlines():
        m = SECTION.match(line)
        if m:
            if current:
                sections.append(current)
            current = (m.group("run_id"), m.group("depth"), [])
        elif current:
            current[2].append(line)
    if current:
        sections.append(current)

    fieldnames = [
        "run_id", "model", "quant", "kv", "threads", "reps", "backend", "ngl",
        "fa", "test", "depth", "tps", "tps_sd", "size_gib", "params_b",
        "status", "noisy", "error", "carveout_mib", "gtt_mib", "host_mib",
        "cpu_temp_c_max", "gpu_temp_c_max", "gpu_power_w_max", "build",
    ]
    records: list[dict[str, object]] = []
    for run_id, depth, lines in sections:
        key, kv, thread_part, rep_part = run_id.split("-")
        threads = thread_part.lstrip("t")
        reps = rep_part.lstrip("r")
        label, quant = MODELS.get(key, (key, ""))[1], MODELS.get(key, (key, ""))[2]
        rows, build = parse_output("\n".join(lines))
        if not rows:
            records.append(
                {
                    "run_id": run_id, "model": label, "quant": quant, "kv": kv,
                    "threads": threads, "reps": reps, "test": "load",
                    "depth": depth, "status": "error", "error": "no table row parsed",
                    "carveout_mib": carveout.get("vram_total_mib"),
                    "gtt_mib": carveout.get("gtt_total_mib"),
                    "host_mib": carveout.get("host_total_mib"),
                }
            )
            continue
        for row in rows:
            records.append(
                {
                    "run_id": run_id, "model": label, "quant": quant, "kv": kv,
                    "threads": threads, "reps": reps, "backend": row["backend"],
                    "ngl": row["ngl"], "fa": "1", "test": row["test"],
                    "depth": row["depth"], "tps": row["tps"], "tps_sd": row["tps_sd"],
                    "size_gib": row["size_gib"], "params_b": row["params_b"],
                    "status": "ok", "error": "",
                    "carveout_mib": carveout.get("vram_total_mib"),
                    "gtt_mib": carveout.get("gtt_total_mib"),
                    "host_mib": carveout.get("host_total_mib"),
                    "build": build,
                }
            )

    with out.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(records)

    ok = sum(1 for r in records if r["status"] == "ok")
    print(f"reparsed {len(sections)} sections -> {ok} measurements, {len(records) - ok} failures")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
