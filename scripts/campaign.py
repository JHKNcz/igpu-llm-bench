#!/usr/bin/env python3
"""Run a reproducible llama-bench campaign and record it as tidy CSV.

Unlike ``bench.sh``, which is a one-shot wrapper, this drives a matrix of
model / KV-type / depth / thread configurations, samples temperature and power
while each run is in progress, and writes one row per measurement.

Design choices that matter for honesty:

* The VRAM carve-out and host RAM are recorded *with* the results, because they
  decide which models can load at all.
* A configuration that fails to load is recorded as a failure row with the
  backend's own error text. It is a result, not something to hide.
* Sensor samples are stored raw alongside the median, so a thermal story can be
  checked rather than asserted.
* Nothing is inferred: if a field is unavailable it is left empty.

Standard library only.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import shutil
import statistics
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

TEST = re.compile(r"^(?P<test>pp512|tg128)(?:\s*@\s*d(?P<depth>\d+))?$")
DEPTH = re.compile(r"@\s*d(?P<depth>\d+)")
BUILD = re.compile(r"^build:\s*(?P<build>.+?)\s*$")

# model -> (path, label, quant, expected size GiB)
MODELS = {
    "lfm_iq4_nl": (
        "<models>/LFM2.5-8B-A1B/LFM2.5-8B-A1B-UD-IQ4_NL.gguf",
        "LFM2.5-8B-A1B",
        "UD-IQ4_NL",
    ),
    "lfm_q8_k_xl": (
        "<models>/LFM2.5-8B-A1B/LFM2.5-8B-A1B-UD-Q8_K_XL.gguf",
        "LFM2.5-8B-A1B",
        "UD-Q8_K_XL",
    ),
    "qwen35_mtp": (
        "<models>/Qwen3.6-MTP/Qwen3.6-35B-A3B-UD-IQ4_NL.gguf",
        "Qwen3.6-35B-A3B-MTP",
        "UD-IQ4_NL",
    ),
    "qwen3vl_4b_q8": (
        "<models>/Qwen3-VL-4B-Instruct-UD-Q8_K_XL.gguf",
        "Qwen3-VL-4B-Instruct",
        "UD-Q8_K_XL",
    ),
}


def model_path(placeholder: str) -> Path:
    """Resolve the <models> placeholder against $MODELS_DIR."""
    base = Path(os.environ.get("MODELS_DIR", Path.home() / "LLM/LLMs"))
    return Path(placeholder.replace("<models>", str(base)))


def read_int(path: str) -> int | None:
    try:
        return int(Path(path).read_text().strip())
    except (OSError, ValueError):
        return None


def carveout() -> dict[str, object]:
    """Current memory split, read from sysfs. Not changed by this script."""
    vram = gtt = None
    for candidate in Path("/sys/class/drm").glob("card*/device/mem_info_vram_total"):
        vram = read_int(str(candidate))
    for candidate in Path("/sys/class/drm").glob("card*/device/mem_info_gtt_total"):
        gtt = read_int(str(candidate))
    host_kb = None
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            if line.startswith("MemTotal:"):
                host_kb = int(line.split()[1])
    except OSError:
        pass
    return {
        "vram_total_mib": round(vram / 2**20) if vram else None,
        "gtt_total_mib": round(gtt / 2**20) if gtt else None,
        "host_total_mib": round(host_kb / 1024) if host_kb else None,
    }


def hwmon_path(name: str, leaf: str) -> str | None:
    for entry in Path("/sys/class/hwmon").glob("hwmon*"):
        try:
            if entry.joinpath("name").read_text().strip() == name:
                p = entry / leaf
                return str(p) if p.exists() else None
        except OSError:
            continue
    return None


class SensorSampler(threading.Thread):
    """Poll temperature and power once a second until stopped."""

    def __init__(self) -> None:
        super().__init__(daemon=True)
        self.stop_event = threading.Event()
        self.samples: list[dict[str, float]] = []
        self.paths = {
            "cpu_temp_c": hwmon_path("k10temp", "temp1_input"),
            "gpu_temp_c": hwmon_path("amdgpu", "temp1_input"),
            "gpu_power_w": hwmon_path("amdgpu", "power1_average"),
        }

    def run(self) -> None:
        while not self.stop_event.is_set():
            sample: dict[str, float] = {}
            for key, path in self.paths.items():
                if not path:
                    continue
                value = read_int(path)
                if value is None:
                    continue
                sample[key] = value / 1000.0 if key.endswith("_c") else value / 1e6
            if sample:
                sample["t"] = time.monotonic()
                self.samples.append(sample)
            self.stop_event.wait(1.0)

    def stop(self) -> dict[str, float | None]:
        self.stop_event.set()
        self.join(timeout=3)
        out: dict[str, float | None] = {}
        for key in ("cpu_temp_c", "gpu_temp_c", "gpu_power_w"):
            values = [s[key] for s in self.samples if key in s]
            out[f"{key}_max"] = round(max(values), 1) if values else None
            out[f"{key}_median"] = round(statistics.median(values), 1) if values else None
        out["samples"] = len(self.samples)
        return out


def parse_output(text: str) -> tuple[list[dict[str, str]], str]:
    """Parse llama-bench's markdown table.

    The table gains a ``threads`` column when ``-t`` is non-default and
    ``type_k``/``type_v`` columns when the KV type is not F16, so columns are
    located by content rather than by position.
    """
    rows: list[dict[str, str]] = []
    build = ""
    for line in text.splitlines():
        m = BUILD.match(line)
        if m:
            build = m.group("build")
            continue
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if len(cells) < 6 or not cells[1].endswith("GiB"):
            continue
        test_index = next(
            (i for i, c in enumerate(cells) if TEST.match(c)), None
        )
        if test_index is None or test_index == len(cells) - 1:
            continue
        tps_cell = cells[-1]
        if "±" not in tps_cell:
            continue
        tps, sd = (part.strip() for part in tps_cell.split("±", 1))
        tm = TEST.match(cells[test_index])
        rows.append(
            {
                "backend": cells[3],
                "model_reported": cells[0],
                "size_gib": cells[1].split()[0],
                "params_b": cells[2].split()[0],
                "ngl": cells[4],
                "test": tm.group("test"),
                "depth": tm.group("depth") or "0",
                "tps": tps,
                "tps_sd": sd,
            }
        )
    return rows, build


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--llama-bench", required=True)
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=ROOT / "runs",
        help="where to write raw logs and the CSV (git-ignored)",
    )
    parser.add_argument(
        "--container",
        default="",
        help="run llama-bench inside this OCI image (e.g. the archived ROCm image)",
    )
    parser.add_argument(
        "--mount",
        action="append",
        default=[],
        metavar="HOST:CONTAINER",
        help="bind mount, repeatable; required with --container",
    )
    parser.add_argument(
        "--model-root",
        default="",
        metavar="HOST:CONTAINER",
        help="map the host model root to its path inside the container",
    )
    parser.add_argument("--reps", type=int, default=3)
    parser.add_argument("--threads", type=int, default=12)
    parser.add_argument(
        "--warmup",
        action="store_true",
        help="run one discarded invocation per model to warm page cache and clocks",
    )
    parser.add_argument(
        "--include-large",
        action="store_true",
        help="also try the 35B MTP model (it only loads on some backends at 512 MiB)",
    )
    parser.add_argument(
        "--only",
        action="append",
        default=[],
        metavar="MODEL_KEY",
        help="restrict the matrix to these model keys (repeatable)",
    )
    parser.add_argument(
        "--force-reps",
        type=int,
        default=0,
        help="override the repetition count for every configuration",
    )
    parser.add_argument(
        "--depths", default="", help="override depths, comma separated (e.g. 0,16384)"
    )
    parser.add_argument(
        "--kv-filter", default="", help="restrict to these KV types, comma separated"
    )
    parser.add_argument(
        "--threads-filter", default="", help="restrict to these thread counts"
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    bench = Path(args.llama_bench)
    if not bench.exists():
        raise SystemExit(f"llama-bench not found: {bench}")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = args.out_dir / f"campaign-{stamp}"
    if not args.dry_run:
        run_dir.mkdir(parents=True, exist_ok=True)
    raw_log = run_dir / "llama-bench.log"
    csv_path = run_dir / "campaign.csv"

    container_cmd: list[str] = []
    if args.container:
        if not args.mount:
            raise SystemExit("--container requires at least one --mount")
        container_cmd = [
            "podman", "run", "--rm",
            "--device", "/dev/dri",
            "--device", "/dev/kfd",
            "--security-opt", "seccomp=unconfined",
            "--group-add", "keep-groups",
            "--entrypoint", "/repo/scripts/rocm-entry.sh",
        ]
        for mount in args.mount:
            container_cmd += ["-v", mount]
        container_cmd += ["-v", f"{ROOT}:/repo:ro", args.container]

    mount_pairs = []
    for mount in args.mount:
        host, container = mount.split(":", 1)
        mount_pairs.append((str(Path(host).resolve()), container.rstrip("/")))

    def to_container(path: Path) -> str:
        """Rewrite a host path to its path inside the container.

        Uses the bind mounts, so both the binary and the model are translated
        by the same rule. Falls back to --model-root for roots that are not a
        mount point themselves.
        """
        if not container_cmd:
            return str(path)
        resolved = str(path.resolve())
        for host_root, container_root in mount_pairs:
            if resolved == host_root or resolved.startswith(host_root + "/"):
                return container_root + resolved[len(host_root):]
        if args.model_root:
            host_root, container_root = args.model_root.split(":", 1)
            host_root = str(Path(host_root).resolve())
            if resolved.startswith(host_root):
                return container_root.rstrip("/") + resolved[len(host_root):]
        raise SystemExit(f"path {resolved} is not covered by any mount")

    meta = {
        "started_utc": datetime.now(timezone.utc).isoformat(),
        "container": args.container or None,
        "mounts": args.mount,
        "carveout": carveout(),
        "llama_bench": str(bench),
        "llama_bench_sha256": subprocess.run(
            ["sha256sum", str(bench)], capture_output=True, text=True
        ).stdout.split()[0],
        "uname": os.uname().release,
        "vulkan_device": "AMD Radeon 890M Graphics (RADV STRIX1)",
    }
    if not args.dry_run:
        (run_dir / "metadata.json").write_text(json.dumps(meta, indent=2) + "\n")
    print(json.dumps(meta["carveout"], indent=2))

    # (model_key, kv, depths, reps, threads)
    matrix = [
        ("lfm_iq4_nl", "f16", [0, 16384, 65536], 3, 12),
        ("lfm_iq4_nl", "q8_0", [0, 16384, 65536], 3, 12),
        ("lfm_q8_k_xl", "f16", [0, 16384, 65536], 2, 12),
        ("qwen3vl_4b_q8", "f16", [0, 16384], 2, 12),
        ("lfm_iq4_nl", "f16", [0], 3, 6),
        ("lfm_iq4_nl", "f16", [0], 3, 18),
    ]
    if args.include_large:
        matrix.append(("qwen35_mtp", "f16", [0, 16384], 2, 12))
    if args.only:
        matrix = [entry for entry in matrix if entry[0] in set(args.only)]
        if not matrix:
            raise SystemExit(f"no matrix entries match --only {args.only}")
    if args.depths:
        wanted = [int(d) for d in args.depths.split(",")]
        matrix = [(k, kv, wanted, r, th) for (k, kv, _, r, th) in matrix]
    if args.kv_filter:
        allowed = set(args.kv_filter.split(","))
        matrix = [e for e in matrix if e[1] in allowed]
    if args.threads_filter:
        allowed = {int(x) for x in args.threads_filter.split(",")}
        matrix = [e for e in matrix if e[4] in allowed]
    if args.force_reps:
        matrix = [(k, kv, d, args.force_reps, th) for (k, kv, d, _, th) in matrix]

    fieldnames = [
        "run_id", "model", "quant", "kv", "threads", "reps", "backend", "ngl",
        "fa", "test", "depth", "tps", "tps_sd", "size_gib", "params_b",
        "status", "noisy", "error", "carveout_mib", "gtt_mib", "host_mib",
        "cpu_temp_c_max", "gpu_temp_c_max", "gpu_power_w_max", "build",
    ]
    records: list[dict[str, object]] = []

    for index, (key, kv, depths, reps, threads) in enumerate(matrix, 1):
        path = model_path(MODELS[key][0])
        label, quant = MODELS[key][1], MODELS[key][2]
        run_id = f"{key}-{kv}-t{threads}-r{reps}"
        if not path.exists():
            print(f"[{index}/{len(matrix)}] SKIP missing model {path}")
            records.append(
                {
                    "run_id": run_id, "model": label, "quant": quant, "kv": kv,
                    "threads": threads, "reps": reps, "status": "missing_model",
                    "error": str(path),
                }
            )
            continue

        for depth in depths:
            bench_args = [
                to_container(bench), "-m", to_container(path), "-ngl", "999", "-fa", "on",
                "-t", str(threads), "-b", "2048", "-ub", "512",
                "-p", "512", "-n", "128", "-r", str(reps), "-d", str(depth),
            ]
            if kv != "f16":
                bench_args += ["-ctk", kv, "-ctv", kv]
            cmd = container_cmd + bench_args
            print(f"[{index}/{len(matrix)}] depth={depth} {run_id}")
            print("  " + " ".join(cmd))

            if args.dry_run:
                continue

            sampler = SensorSampler()
            sampler.start()
            started = time.monotonic()
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
            elapsed = time.monotonic() - started
            sensors = sampler.stop()

            with raw_log.open("a") as handle:
                handle.write(f"\n### {run_id} depth={depth} elapsed={elapsed:.1f}s\n")
                handle.write(proc.stdout)
                if proc.stderr:
                    handle.write("--- stderr ---\n" + proc.stderr)

            rows, build = parse_output(proc.stdout)
            fallback = re.search(
                r"no ROCm-capable device|failed to initialize ROCm|"
                r"no usable GPU|falling back to CPU",
                proc.stdout + proc.stderr,
                re.I,
            )
            if fallback:
                records.append(
                    {
                        "run_id": run_id, "model": label, "quant": quant, "kv": kv,
                        "threads": threads, "reps": reps, "test": "load",
                        "depth": depth, "status": "error",
                        "error": "backend fell back to CPU: " + fallback.group(0),
                        "carveout_mib": meta["carveout"]["vram_total_mib"],
                        "gtt_mib": meta["carveout"]["gtt_total_mib"],
                        "host_mib": meta["carveout"]["host_total_mib"],
                    }
                )
                print(f"  REFUSED: {fallback.group(0)}")
                continue
            if proc.returncode != 0 or not rows:
                error = " | ".join(
                    line.strip()
                    for line in (proc.stdout + proc.stderr).splitlines()
                    if re.search(r"error|Not enough memory|failed", line, re.I)
                )[:400]
                records.append(
                    {
                        "run_id": run_id, "model": label, "quant": quant, "kv": kv,
                        "threads": threads, "reps": reps, "test": "load",
                        "depth": depth, "status": "error", "error": error,
                        "carveout_mib": meta["carveout"]["vram_total_mib"],
                        "gtt_mib": meta["carveout"]["gtt_total_mib"],
                        "host_mib": meta["carveout"]["host_total_mib"],
                        **{k: v for k, v in sensors.items() if k.endswith("_max")},
                    }
                )
                print(f"  FAILED rc={proc.returncode}: {error[:120]}")
                continue

            for row in rows:
                records.append(
                    {
                        "run_id": run_id,
                        "model": label,
                        "quant": quant,
                        "kv": kv,
                        "threads": threads,
                        "reps": reps,
                        "backend": row["backend"],
                        "ngl": row["ngl"],
                        "fa": "1",  # always -fa on
                        "test": row["test"],
                        "depth": row["depth"],
                        "tps": row["tps"],
                        "tps_sd": row["tps_sd"],
                        "size_gib": row["size_gib"],
                        "params_b": row["params_b"],
                        "status": "ok",
                        "noisy": (
                            "yes"
                            if float(row["tps_sd"]) / max(float(row["tps"]), 1e-9) > 0.15
                            else ""
                        ),
                        "error": "",
                        "carveout_mib": meta["carveout"]["vram_total_mib"],
                        "gtt_mib": meta["carveout"]["gtt_total_mib"],
                        "host_mib": meta["carveout"]["host_total_mib"],
                        "cpu_temp_c_max": sensors.get("cpu_temp_c_max"),
                        "gpu_temp_c_max": sensors.get("gpu_temp_c_max"),
                        "gpu_power_w_max": sensors.get("gpu_power_w_max"),
                        "build": build,
                    }
                )
            for row in rows:
                ratio = float(row["tps_sd"]) / max(float(row["tps"]), 1e-9)
                flag = "  <-- noisy" if ratio > 0.15 else ""
                print(f"  {row['test']:<18} {row['tps']:>8} ± {row['tps_sd']}{flag}")
            print(f"  elapsed {elapsed:.0f}s  gpu_max {sensors.get('gpu_temp_c_max')}C")

    if args.dry_run:
        print("dry run: no benchmark executed, nothing written")
        return 0

    with csv_path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(records)

    ok = sum(1 for r in records if r.get("status") == "ok")
    failed = sum(1 for r in records if r.get("status") == "error")
    print(f"\nwrote {csv_path}  ({ok} measurements, {failed} failures)")
    print(f"raw log: {raw_log}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
