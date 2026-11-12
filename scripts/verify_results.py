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
import statistics
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


def load_ab(names: list[str]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for name in names:
        with (ROOT / "data/processed" / name).open(newline="") as handle:
            rows += [r for r in csv.DictReader(handle) if r.get("status") == "ok"]
    return rows


def medians(rows: list[dict[str, str]], test: str = "tg128") -> dict[tuple, float]:
    grouped: dict[tuple, list[float]] = {}
    for row in rows:
        if row.get("test") != test:
            continue
        grouped.setdefault(
            (row["backend"].lower(), row["model"], row["quant"], int(row["depth"])), []
        ).append(float(row["tps"]))
    return {k: statistics.median(v) for k, v in grouped.items()}


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

    # --- randomised three-backend comparison at 0.5 GB ----------------------
    # Each claim is checked against the suite it came from, not a pooled set.
    def median_of(file_name: str, backend: str, model: str, quant: str,
                  depth: int, test: str = "tg128") -> float | None:
        rows = load_ab([file_name])
        return medians(rows, test).get((backend, model, quant, depth))

    expectations = [
        ("ab-stability-20261110.csv", "vulkan", "LFM2.5-8B-A1B", "UD-Q8_K_XL", 0, "23.97"),
        ("ab-stability-20261110.csv", "rocm", "LFM2.5-8B-A1B", "UD-Q8_K_XL", 0, "30.61"),
        ("ab-cpu-20261110.csv", "cpu", "LFM2.5-8B-A1B", "UD-Q8_K_XL", 0, "36.70"),
        ("ab-a-20261110.csv", "vulkan", "LFM2.5-8B-A1B", "UD-Q8_K_XL", 16384, "16.31"),
        ("ab-a-20261110.csv", "rocm", "LFM2.5-8B-A1B", "UD-Q8_K_XL", 16384, "26.14"),
        ("ab-a-20261110.csv", "cpu", "LFM2.5-8B-A1B", "UD-Q8_K_XL", 16384, "23.85"),
        ("ab-cpu-20261110.csv", "cpu", "LFM2.5-8B-A1B", "UD-IQ4_NL", 0, "51.99"),
        ("ab-cpu-20261110.csv", "cpu", "Qwen3-VL-4B-Instruct", "UD-Q8_K_XL", 0, "14.81"),
        ("ab-cpu-20261110.csv", "cpu", "Qwen3.6-35B-A3B-MTP", "UD-IQ4_NL", 0, "18.38"),
        ("campaign-rocm-20261110.csv", "rocm", "Qwen3.6-35B-A3B-MTP", "UD-IQ4_NL", 0, "17.66"),
    ]
    for file_name, backend, model, quant, depth, expected in expectations:
        actual = median_of(file_name, backend, model, quant, depth)
        if actual is None or fmt2(actual) != expected:
            print(f"FAIL ab: {backend} {model} {quant} d{depth} "
                  f"{fmt2(actual) if actual is not None else 'missing'} != {expected}")
            failures += 1
            continue
        checks.append(("README.md", expected, f"{backend} {model} d{depth} median"))
        checks.append(("RESULTS.md", expected, f"{backend} {model} d{depth} median"))

    # --- quantization at depth 0, same session ------------------------------
    quant = medians(load_ab(["ab-quant-20261110.csv"]))
    quant_expect = [
        ("vulkan", "UD-IQ4_NL", "49.30"),
        ("vulkan", "UD-Q8_K_XL", "25.63"),
        ("rocm", "UD-IQ4_NL", "44.86"),
        ("rocm", "UD-Q8_K_XL", "28.93"),
        ("cpu", "UD-IQ4_NL", "51.50"),
        ("cpu", "UD-Q8_K_XL", "36.64"),
    ]
    for backend, quant_name, expected in quant_expect:
        actual = quant.get((backend, "LFM2.5-8B-A1B", quant_name, 0))
        if actual is None or fmt2(actual) != expected:
            print(f"FAIL quant: {backend} {quant_name} "
                  f"{fmt2(actual) if actual is not None else 'missing'} != {expected}")
            failures += 1
            continue
        checks.append(("RESULTS.md", expected, f"{backend} {quant_name} d0"))
        checks.append(("README.md", expected, f"{backend} {quant_name} d0"))

    # --- 16 GB carve-out claims --------------------------------------------
    def median_campaign(file_name: str, backend: str, model: str,
                        quant: str, depth: int, test: str = "tg128",
                        kv: str = "f16") -> float | None:
        rows = [
            r for r in csv.DictReader((ROOT / "data/processed" / file_name).open(newline=""))
            if r.get("status") == "ok"
        ]
        vals = [
            float(r["tps"]) for r in rows
            if r.get("backend", "").lower() == backend
            and r["model"] == model and r["quant"] == quant
            and int(r["depth"]) == depth and r["test"] == test
            and r.get("threads") == "12" and r.get("kv") == kv
        ]
        return statistics.median(vals) if vals else None

    checks_16 = [
        ("campaign-vulkan-35b-16gb-5rep-20261112.csv", "vulkan", "Qwen3.6-35B-A3B-MTP", "UD-IQ4_NL", 0, "24.19"),
        ("campaign-vulkan-35b-16gb-5rep-20261112.csv", "vulkan", "Qwen3.6-35B-A3B-MTP", "UD-IQ4_NL", 16384, "20.45"),
        ("campaign-vulkan-35b-16gb-64k-20261112.csv", "vulkan", "Qwen3.6-35B-A3B-MTP", "UD-IQ4_NL", 65536, "14.68"),
        ("campaign-cpu-35b-16gb-20261112.csv", "cpu", "Qwen3.6-35B-A3B-MTP", "UD-IQ4_NL", 0, "13.78"),
        ("campaign-vulkan-16gb-20261112.csv", "vulkan", "LFM2.5-8B-A1B", "UD-IQ4_NL", 0, "71.97"),
        ("campaign-vulkan-16gb-20261112.csv", "vulkan", "LFM2.5-8B-A1B", "UD-IQ4_NL", 65536, "44.17"),
        ("campaign-vulkan-16gb-20261112.csv", "vulkan", "LFM2.5-8B-A1B", "UD-Q8_K_XL", 65536, "28.87"),
    ]
    for file_name, backend, model, quant, depth, expected in checks_16:
        actual = median_campaign(file_name, backend, model, quant, depth)
        if actual is None or fmt2(actual) != expected:
            print(f"FAIL 16gb: {model} {quant} d{depth} "
                  f"{fmt2(actual) if actual is not None else 'missing'} != {expected}")
            failures += 1
            continue
        checks.append(("RESULTS.md", expected, f"16 GB {model} d{depth}"))
        checks.append(("README.md", expected, f"16 GB {model} d{depth}"))

    # The 16 GB campaign must use the MTP variant, not the absent headline file.
    for name in ("campaign-vulkan-35b-16gb-20261112.csv",
                 "campaign-cpu-35b-16gb-20261112.csv"):
        rows = list(csv.DictReader((ROOT / "data/processed" / name).open(newline="")))
        labels = {r["model"] for r in rows if "35B" in r.get("model", "")}
        if labels != {"Qwen3.6-35B-A3B-MTP"}:
            print(f"FAIL: {name} 35B labels {labels}")
            failures += 1

    # The 35B must have no Vulkan measurement in any suite.
    for name in ("ab-a-20261110.csv", "ab-b-20261110.csv",
                 "campaign-vulkan-20261110.csv", "campaign-vulkan-20261110-kv-recheck.csv"):
        if any(
            r["backend"] == "vulkan" and r["model"] == "Qwen3.6-35B-A3B-MTP"
            for r in load_ab([name])
        ):
            print(f"FAIL: unexpected Vulkan 35B measurement in {name}")
            failures += 1

    # --- carve-out control surface must stay documented ---------------------
    hw = (ROOT / "docs/hardware.md").read_text()
    for needle, why in [
        ("uma/carveout", "raw sysfs carve-out node"),
        ("carveout_options", "index table"),
        ("amd-smi set -g 0 -m", "amd-smi carve-out command"),
        ("amd-smi set -G", "GTT command"),
        ("amd-smi reset --gtt", "GTT reset command"),
        ("Reboot required", "GTT is a boot-time setting"),
        ("card1", "the card-number pitfall"),
    ]:
        if needle not in hw:
            print(f"FAIL hardware doc: missing {needle!r} ({why})")
            failures += 1
        else:
            print(f"ok   hardware doc: {needle!r}")
    if not (ROOT / "data/raw/hardware/uma-carveout-2026-11-12.txt").exists():
        print("FAIL: missing raw carve-out capture")
        failures += 1

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
