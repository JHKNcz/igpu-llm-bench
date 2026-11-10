#!/usr/bin/env python3
"""Probe how much of a model can be offloaded at the current memory setting.

At a small VRAM carve-out, the interesting question is not "how fast" but "can
it load at all". This script tries a list of ``-ngl`` values with a minimal
workload and records, for each: whether the model loaded, the backend's error
if not, and the decode rate if it did.

It never changes the carve-out. It reports what the current setting allows.

Output: a CSV and a JSON summary under the given run directory.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ROW = re.compile(r"\|\s*[\w.]+.*\|\s*(?P<test>tg128|pp512)\s*\|\s*(?P<tps>[\d.]+)")
ERROR = re.compile(r"(Not enough memory[^\n]*|error:[^\n]*|failed to allocate[^\n]*|out of memory[^\n]*)", re.I)


def mem(field: str) -> int | None:
    for p in Path("/sys/class/drm").glob(f"card*/device/mem_info_{field}"):
        try:
            return round(int(p.read_text().strip()) / 2**20)
        except (OSError, ValueError):
            continue
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--llama-bench", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--label", required=True)
    parser.add_argument("--ngl", default="0,8,16,22,28,34,40")
    parser.add_argument("--out-dir", type=Path, default=ROOT / "runs")
    parser.add_argument("--timeout", type=int, default=900)
    args = parser.parse_args()

    bench = Path(args.llama_bench)
    model = Path(args.model)
    if not bench.exists() or not model.exists():
        raise SystemExit("llama-bench or model not found")

    ngl_values = [int(v) for v in args.ngl.split(",")]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = args.out_dir / f"capacity-{stamp}"
    run_dir.mkdir(parents=True, exist_ok=True)
    log = run_dir / "probe.log"
    rows: list[dict[str, object]] = []

    base = {
        "label": args.label,
        "model": f"<models>/{model.name}",
        "model_gib": round(model.stat().st_size / 2**30, 2),
        "carveout_mib": mem("vram_total"),
        "gtt_mib": mem("gtt_total"),
        "started_utc": datetime.now(timezone.utc).isoformat(),
    }

    for ngl in ngl_values:
        before_vram, before_gtt = mem("vram_used"), mem("gtt_used")
        cmd = [
            str(bench), "-m", str(model), "-ngl", str(ngl), "-fa", "on",
            "-t", "12", "-b", "2048", "-ub", "512", "-p", "0", "-n", "8",
            "-r", "1", "-d", "0",
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=args.timeout)
        text = proc.stdout + proc.stderr
        with log.open("a") as handle:
            handle.write(f"\n### ngl={ngl} rc={proc.returncode}\n{text}")

        match = ROW.search(proc.stdout)
        err = ERROR.search(text)
        ok = proc.returncode == 0 and match is not None
        rows.append(
            {
                **base,
                "ngl": ngl,
                "status": "loaded" if ok else "failed",
                "tg128_tps": match.group("tps") if ok and match.group("test") == "tg128" else "",
                "error": (err.group(1).strip()[:200] if err else "") if not ok else "",
                "vram_used_before_mib": before_vram,
                "gtt_used_before_mib": before_gtt,
                "vram_used_after_mib": mem("vram_used"),
                "gtt_used_after_mib": mem("gtt_used"),
            }
        )
        print(f"ngl={ngl:<3} {'loaded ' + (match.group('tps') if match else '') if ok else 'FAILED ' + (rows[-1]['error'] or '')[:90]}")

    csv_path = run_dir / "capacity.csv"
    with csv_path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    (run_dir / "capacity.json").write_text(json.dumps(rows, indent=2) + "\n")
    print(f"\nwrote {csv_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
