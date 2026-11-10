#!/usr/bin/env python3
"""Randomised, multi-backend campaign for the depth-crossover experiments.

Unlike ``campaign.py``, which runs one backend through a fixed matrix, this
interleaves backends and shuffles the order of every round. That matters when
the question is whether an observed difference is real or an artefact of run
order and thermal drift.

Design:

* Each round is a shuffled permutation of the whole cell list, so a backend
  cannot systematically run first (cold) or last (hot).
* Every row records its round and its position within the round, so an order
  effect can be tested after the fact.
* Sensors are sampled per run.
* A CPU fallback from a GPU backend is recorded as an error, never as data.

Suites:

  a     the depth-crossover replication (0 and 16K, three backends)
  b     the crossover location (0, 4K, 8K, 12K, 16K, two backends)
  cpu   CPU baselines for every model
  all   a, then b, then cpu
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

from campaign import (  # noqa: E402
    MODELS,
    SensorSampler,
    carveout,
    model_path,
    parse_output,
)

FALLBACK = re.compile(
    r"no ROCm-capable device|failed to initialize ROCm|no usable GPU|falling back to CPU",
    re.I,
)


def build_suite(name: str) -> list[tuple[str, str, str, int, int]]:
    """Return (backend, model_key, kv, depth, reps) cells for a suite."""
    cells: list[tuple[str, str, str, int, int]] = []
    if name in ("a", "all"):
        for backend in ("vulkan", "rocm", "cpu"):
            for depth in (0, 16384):
                cells.append((backend, "lfm_q8_k_xl", "f16", depth, 3))
    if name in ("b", "all"):
        for backend in ("vulkan", "rocm"):
            for depth in (0, 4096, 8192, 12288, 16384):
                cells.append((backend, "lfm_q8_k_xl", "f16", depth, 3))
    if name in ("quant", "all"):
        for backend in ("vulkan", "rocm", "cpu"):
            for model in ("lfm_iq4_nl", "lfm_q8_k_xl"):
                cells.append((backend, model, "f16", 0, 3))
    if name in ("stability", "all"):
        for backend in ("vulkan", "rocm"):
            cells.append((backend, "lfm_q8_k_xl", "f16", 0, 2))
    if name in ("cpu", "all"):
        for model in ("lfm_iq4_nl", "lfm_q8_k_xl", "qwen3vl_4b_q8"):
            for depth in (0, 16384):
                cells.append(("cpu", model, "f16", depth, 2))
        # The 35B on CPU is slow to prefill; depth 0 is the headline number.
        cells.append(("cpu", "qwen35_mtp", "f16", 0, 1))
    return cells


class Backend:
    def __init__(self, name: str, bench: Path, container: list[str], mapper) -> None:
        self.name = name
        self.bench = bench
        self.container = container
        self.map = mapper

    def command(self, model: Path, depth: int, reps: int, kv: str, threads: int) -> list[str]:
        args = [
            self.map(self.bench), "-m", self.map(model), "-ngl", "0" if self.name == "cpu" else "999",
            "-fa", "on", "-t", str(threads), "-b", "2048", "-ub", "512",
            "-p", "512", "-n", "128", "-r", str(reps), "-d", str(depth),
        ]
        if kv != "f16":
            args += ["-ctk", kv, "-ctv", kv]
        return self.container + args


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vulkan-bench", required=True)
    parser.add_argument("--rocm-bench", required=True)
    parser.add_argument("--cpu-bench", required=True)
    parser.add_argument("--rocm-container", required=True)
    parser.add_argument("--rocm-mount", required=True, help="HOST:CONTAINER")
    parser.add_argument("--rocm-model-root", required=True, help="HOST:CONTAINER")
    parser.add_argument(
        "--suite", default="all", choices=["a", "b", "cpu", "stability", "quant", "all"]
    )
    parser.add_argument("--rounds", type=int, default=3)
    parser.add_argument("--seed", type=int, default=20261110)
    parser.add_argument("--threads", type=int, default=12)
    parser.add_argument("--out-dir", type=Path, default=ROOT / "runs")
    args = parser.parse_args()

    host_mount, cont_mount = args.rocm_mount.split(":", 1)
    host_root, cont_root = args.rocm_model_root.split(":", 1)
    host_mount = str(Path(host_mount).resolve())
    host_root = str(Path(host_root).resolve())

    def rocm_map(path: Path) -> str:
        resolved = str(path.resolve())
        if resolved.startswith(host_mount):
            return cont_mount.rstrip("/") + resolved[len(host_mount):]
        if resolved.startswith(host_root):
            return cont_root.rstrip("/") + resolved[len(host_root):]
        raise SystemExit(f"path not covered by mounts: {resolved}")

    def identity(path: Path) -> str:
        return str(path)

    container = [
        "podman", "run", "--rm",
        "--device", "/dev/dri", "--device", "/dev/kfd",
        "--security-opt", "seccomp=unconfined", "--group-add", "keep-groups",
        "--entrypoint", "/repo/scripts/rocm-entry.sh",
        "-v", f"{host_mount}:{cont_mount}",
        "-v", f"{ROOT}:/repo:ro",
        args.rocm_container,
    ]

    backends = {
        "vulkan": Backend("vulkan", Path(args.vulkan_bench), [], identity),
        "rocm": Backend("rocm", Path(args.rocm_bench), container, rocm_map),
        "cpu": Backend("cpu", Path(args.cpu_bench), [], identity),
    }

    cells = build_suite(args.suite)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = args.out_dir / f"ab-{args.suite}-{stamp}"
    run_dir.mkdir(parents=True, exist_ok=True)
    log = run_dir / "ab.log"

    meta = {
        "started_utc": datetime.now(timezone.utc).isoformat(),
        "suite": args.suite,
        "rounds": args.rounds,
        "seed": args.seed,
        "carveout": carveout(),
        "cells": len(cells),
    }
    (run_dir / "metadata.json").write_text(json.dumps(meta, indent=2) + "\n")
    print(json.dumps(meta["carveout"], indent=2))
    print(f"{len(cells)} cells x {args.rounds} rounds = {len(cells) * args.rounds} runs")

    rng = random.Random(args.seed)
    records: list[dict[str, object]] = []
    for rnd in range(1, args.rounds + 1):
        order = list(cells)
        rng.shuffle(order)
        for pos, (backend_name, model_key, kv, depth, reps) in enumerate(order, 1):
            backend = backends[backend_name]
            path = model_path(MODELS[model_key][0])
            label, quant = MODELS[model_key][1], MODELS[model_key][2]
            if not path.exists():
                continue
            cmd = backend.command(path, depth, reps, kv, args.threads)
            print(f"[r{rnd} {pos:>2}/{len(order)}] {backend_name:<6} {model_key:<12} d{depth}")
            sampler = SensorSampler()
            sampler.start()
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=7200)
            sensors = sampler.stop()
            text = proc.stdout + proc.stderr
            with log.open("a") as handle:
                handle.write(f"\n### r{rnd} pos={pos} {backend_name} {model_key} d{depth}\n{text}")

            if FALLBACK.search(text):
                records.append(
                    {
                        "round": rnd, "position": pos, "backend": backend_name,
                        "model": label, "quant": quant, "kv": kv, "depth": depth,
                        "status": "error", "error": "CPU fallback", "tps": None,
                    }
                )
                print("  REFUSED: CPU fallback")
                continue

            rows, build = parse_output(text)
            if proc.returncode != 0 or not rows:
                err = next(
                    (l.strip() for l in text.splitlines() if re.search(r"error|Not enough", l, re.I)),
                    "no table row",
                )[:200]
                records.append(
                    {
                        "round": rnd, "position": pos, "backend": backend_name,
                        "model": label, "quant": quant, "kv": kv, "depth": depth,
                        "status": "error", "error": err, "tps": None,
                    }
                )
                print(f"  FAILED: {err[:90]}")
                continue

            for row in rows:
                ratio = float(row["tps_sd"]) / max(float(row["tps"]), 1e-9)
                records.append(
                    {
                        "round": rnd, "position": pos, "backend": backend_name,
                        "model": label, "quant": quant, "kv": kv,
                        "depth": row["depth"], "test": row["test"],
                        "tps": row["tps"], "tps_sd": row["tps_sd"],
                        "noisy": "yes" if ratio > 0.15 else "",
                        "status": "ok", "error": "",
                        "gpu_temp_c_max": sensors.get("gpu_temp_c_max"),
                        "cpu_temp_c_max": sensors.get("cpu_temp_c_max"),
                        "gpu_power_w_max": sensors.get("gpu_power_w_max"),
                        "build": build,
                    }
                )
                flag = "  <-- noisy" if ratio > 0.15 else ""
                print(f"  {row['test']:<16}{float(row['tps']):>8.2f} ±{float(row['tps_sd']):>5.2f}{flag}")

    out = run_dir / "ab.csv"
    fields = [
        "round", "position", "backend", "model", "quant", "kv", "depth", "test",
        "tps", "tps_sd", "noisy", "status", "error", "gpu_temp_c_max",
        "cpu_temp_c_max", "gpu_power_w_max", "build",
    ]
    with out.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(records)
    ok = sum(1 for r in records if r["status"] == "ok")
    print(f"\nwrote {out}  ({ok} measurements, {len(records) - ok} failures)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
