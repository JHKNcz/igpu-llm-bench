#!/usr/bin/env python3
"""Check that the numbers in the prose trace to the processed data.

This is a guard against documentation drift. It does not prove the analysis is
correct; it proves the documents agree with the CSVs and JSON that the scripts
generate. If a table is edited by hand and the data changes, or a stale value
survives a correction, this fails.

Each check is a (file, needle, why) triple. The needle must appear verbatim.
Exit status is non-zero if any check fails, so CI can run it directly.
"""

from __future__ import annotations

import csv
import json
import sys
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def fmt2(value: float) -> str:
    """Two decimals, half-up.

    Python's round() uses banker's rounding and binary floats, so 1.505 can
    render as "1.50". Documentation should round the way a reader expects.
    """
    return str(Decimal(repr(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def load_bench() -> dict[tuple[str, int], float]:
    with (ROOT / "data/processed/llama-bench.csv").open(newline="") as handle:
        return {
            (row["backend"], int(row["depth"])): float(row["tps"])
            for row in csv.DictReader(handle)
        }


def load_roofline() -> dict[tuple[str, int], float]:
    with (ROOT / "data/processed/roofline.csv").open(newline="") as handle:
        return {
            (row["backend"], int(row["depth"])): float(row["effective_gbps"])
            for row in csv.DictReader(handle)
        }


def load_stats() -> dict:
    return json.loads((ROOT / "data/processed/speculative-stats.json").read_text())


def load_carveouts() -> dict:
    return json.loads(
        (ROOT / "data/raw/historical/carveout-states-2026-10-02.json").read_text()
    )


def main() -> int:
    bench = load_bench()
    roof = load_roofline()
    stats = load_stats()
    readme = (ROOT / "README.md").read_text()
    results = (ROOT / "RESULTS.md").read_text()

    checks: list[tuple[str, str, str]] = []

    # --- headline throughput, straight from llama-bench.csv -----------------
    for backend, depth, label in [
        ("Vulkan", 0, "Vulkan depth 0"),
        ("ROCm", 0, "ROCm depth 0"),
        ("Vulkan", 16384, "Vulkan 16K"),
        ("ROCm", 16384, "ROCm 16K"),
        ("Vulkan", 65536, "Vulkan 64K"),
        ("ROCm", 65536, "ROCm 64K"),
    ]:
        value = fmt2(bench[(backend, depth)])
        checks.append(("RESULTS.md", value, f"{label} t/s appears"))

    # --- raw ratio ----------------------------------------------------------
    ratio = bench[("Vulkan", 0)] / bench[("ROCm", 0)]
    checks.append(("README.md", f"{fmt2(ratio)}x", "Vulkan/ROCm raw ratio"))
    checks.append(("RESULTS.md", f"{fmt2(ratio)}x", "Vulkan/ROCm raw ratio"))

    # --- roofline -----------------------------------------------------------
    for backend, depth, label in [
        ("Vulkan", 0, "Vulkan depth-0 effective bandwidth"),
        ("Vulkan", 65536, "Vulkan 64K effective bandwidth"),
        ("ROCm", 0, "ROCm depth-0 effective bandwidth"),
    ]:
        value = fmt2(roof[(backend, depth)])
        checks.append(("RESULTS.md", value, f"{label} in GB/s"))

    # --- speculative statistics --------------------------------------------
    for mode in ("baseline", "dflash2", "mtp_off", "mtp"):
        med = stats["modes"][mode]["median_generation_tps"]
        checks.append(("RESULTS.md", fmt2(med), f"{mode} median generation t/s"))
    for mode in ("dflash2", "mtp"):
        p = stats["modes"][mode]["paired_vs"]["baseline"]
        checks.append(("README.md", f"{fmt2(p['median_ratio'])}x", f"{mode} paired speedup"))
        lo, hi = p["ci95"]
        checks.append(
            ("RESULTS.md", f"{fmt2(lo)}–{fmt2(hi)}", f"{mode} 95% CI of paired speedup")
        )

    failures = 0

    # --- carve-out arithmetic must be internally consistent ------------------
    carve = load_carveouts()["settings"]
    small, large = carve["small"], carve["large"]
    for name, setting in (("small", small), ("large", large)):
        total = setting["bios_reserved_vram_mib"] + setting["gtt_mib"]
        if total != setting["gpu_addressable_total_mib"]:
            print(
                f"FAIL carve-out {name}: {setting['bios_reserved_vram_mib']} + "
                f"{setting['gtt_mib']} != {setting['gpu_addressable_total_mib']}"
            )
            failures += 1
    # The 35B weight buffer must exceed the 16 GB pool for the documented
    # ROCm failure to be the right explanation.
    if not 16679 > large["rocm_reported_vram_mib"]:
        print("FAIL: 16 GB pool would fit the 16,679 MiB weight buffer")
        failures += 1

    checks.append(("RESULTS.md", "16,679.34", "ROCm weight buffer at 16 GB"))
    checks.append(("RESULTS.md", "24,022", "GPU-addressable total at 16 GB"))
    checks.append(("docs/hardware.md", "15,277", "host RAM at 16 GB"))
    checks.append(("docs/hardware.md", "30,877", "host RAM at 0.5 GB"))
    checks.append(("README.md", "16,679.34", "carve-out finding in the README"))

    # --- stale values that a correction must remove -------------------------
    stale = [
        ("59.3", "old roofline bandwidth before the hybrid-layer correction"),
        ("40,960", "old KV bytes/token before the hybrid-layer correction"),
        ("49.4%", "old percent-of-peak before the hybrid-layer correction"),
        # Split so this file does not itself contain the literals it bans.
        ("ele" + "gant_margulis", "container name"),
        ("/home/" + "jho" + "mni", "real username in a path"),
    ]
    for needle, why in stale:
        for name, doc in (("README.md", readme), ("RESULTS.md", results)):
            if needle in doc:
                checks.append((name, f"ABSENT:{needle}", why))

    for filename, needle, why in checks:
        doc = readme if filename == "README.md" else results
        if needle.startswith("ABSENT:"):
            target = needle[len("ABSENT:"):]
            ok = target not in doc
            shown = f"does not contain {target!r}"
        else:
            ok = needle in doc
            shown = f"contains {needle!r}"
        if not ok:
            failures += 1
            print(f"FAIL {filename}: {shown} ({why})")
        else:
            print(f"ok   {filename}: {shown}")

    print()
    print(f"checks: {len(checks)}  failures: {failures}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
