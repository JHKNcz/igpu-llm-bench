#!/usr/bin/env python3
"""Parse the archived llama-bench logs and the session summary into CSV.

Standard library only. The parser is deliberately strict: it fails loudly if a
line changes shape, rather than silently dropping a measurement.
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_LLAMA_BENCH = [
    ROOT / "data/raw/llama-bench-rocm-2026-09-30.txt",
    ROOT / "data/raw/llama-bench-vulkan-2026-10-01.txt",
]
DEFAULT_SESSION = ROOT / "data/raw/historical/session-summary-2026-10-02.txt"
DEFAULT_OUT = ROOT / "data/processed"

TABLE_ROW = re.compile(
    r"^\|\s*(?P<model>.+?)\s*\|\s*(?P<size>[\d.]+)\s*GiB\s*\|"
    r"\s*(?P<params>[\d.]+)\s*B\s*\|\s*(?P<backend>\w+)\s*\|"
    r"\s*(?P<ngl>\d+)\s*\|\s*(?P<fa>\d+)\s*\|"
    r"\s*(?P<test>.+?)\s*\|\s*(?P<tps>[\d.]+)\s*±\s*(?P<sd>[\d.]+)\s*\|$"
)
BUILD_LINE = re.compile(r"^build:\s*(?P<build>.+?)\s*$")
DEPTH = re.compile(r"@\s*d(?P<depth>\d+)")

SESSION_ROW = re.compile(
    r"^(?P<name>\S+)\s+(?P<status>\S+)\s+(?P<tps>[\d.]+)\s+wall t/s\s+"
    r"unique outputs\s+(?P<unique>\S+)\s+acceptance\s+(?P<acceptance>\S+)\s*$"
)


def parse_llama_bench(path: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    build = "not recorded"
    lines = path.read_text().splitlines()
    for line in lines:
        m = BUILD_LINE.match(line)
        if m:
            build = m.group("build")
            break
    for lineno, line in enumerate(lines, 1):
        m = TABLE_ROW.match(line)
        if not m:
            continue
        test = m.group("test").strip()
        depth_match = DEPTH.search(test)
        rows.append(
            {
                "backend": m.group("backend"),
                "model": m.group("model").strip(),
                "size_gib": float(m.group("size")),
                "params_b": float(m.group("params")),
                "ngl": int(m.group("ngl")),
                "fa": int(m.group("fa")),
                "test": test,
                "depth": int(depth_match.group("depth")) if depth_match else 0,
                "tps": float(m.group("tps")),
                "tps_sd": float(m.group("sd")),
                "build": build,
                "source_file": str(path.relative_to(ROOT)),
                "source_line": lineno,
            }
        )
    if not rows:
        raise SystemExit(f"no llama-bench table rows found in {path}")
    return rows


def parse_session(path: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for lineno, line in enumerate(path.read_text().splitlines(), 1):
        if not line.strip():
            continue
        m = SESSION_ROW.match(line)
        if not m:
            raise SystemExit(f"{path}:{lineno}: unexpected session line: {line!r}")
        acceptance = m.group("acceptance")
        rows.append(
            {
                "name": m.group("name"),
                "status": m.group("status"),
                "wall_tps": float(m.group("tps")),
                "unique_outputs": m.group("unique"),
                "draft_acceptance": "" if acceptance == "None" else float(acceptance),
                "source_file": str(path.relative_to(ROOT)),
                "source_line": lineno,
            }
        )
    return rows


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_ratios(path: Path, rows: list[dict[str, object]]) -> None:
    by_test: dict[str, dict[str, float]] = {}
    for row in rows:
        by_test.setdefault(str(row["test"]), {})[str(row["backend"])] = float(row["tps"])
    out = []
    for test, values in sorted(by_test.items(), key=lambda item: int(DEPTH.search(item[0]).group("depth")) if DEPTH.search(item[0]) else 0):
        if "Vulkan" in values and "ROCm" in values:
            out.append(
                {
                    "test": test,
                    "vulkan_tps": values["Vulkan"],
                    "rocm_tps": values["ROCm"],
                    "vulkan_over_rocm": round(values["Vulkan"] / values["ROCm"], 4),
                }
            )
    write_csv(path, out, ["test", "vulkan_tps", "rocm_tps", "vulkan_over_rocm"])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--llama-bench-raw",
        nargs="+",
        type=Path,
        default=DEFAULT_LLAMA_BENCH,
        help="llama-bench text logs (default: the two archived files)",
    )
    parser.add_argument(
        "--session-summary",
        type=Path,
        default=DEFAULT_SESSION,
        help="session summary text file",
    )
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    bench_rows: list[dict[str, object]] = []
    for path in args.llama_bench_raw:
        bench_rows.extend(parse_llama_bench(path))
    bench_rows.sort(key=lambda row: (str(row["backend"]), int(row["depth"])))

    write_csv(
        args.out_dir / "llama-bench.csv",
        bench_rows,
        [
            "backend",
            "model",
            "size_gib",
            "params_b",
            "ngl",
            "fa",
            "test",
            "depth",
            "tps",
            "tps_sd",
            "build",
            "source_file",
            "source_line",
        ],
    )
    write_ratios(args.out_dir / "llama-bench-ratios.csv", bench_rows)

    session_rows = parse_session(args.session_summary)
    write_csv(
        args.out_dir / "session-summary.csv",
        session_rows,
        [
            "name",
            "status",
            "wall_tps",
            "unique_outputs",
            "draft_acceptance",
            "source_file",
            "source_line",
        ],
    )

    print(f"llama-bench rows: {len(bench_rows)}")
    print(f"session rows:     {len(session_rows)}")
    print(f"output:           {args.out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
