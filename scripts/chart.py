#!/usr/bin/env python3
"""Generate the repository's figures as dependency-free SVG.

No matplotlib, no numpy, no browser. The charts are plain SVG written with the
standard library, so they render on GitHub, in an editor preview, or in a
terminal image viewer, and they stay diffable as text.

Three figures:

  backend-depth.svg   Vulkan vs ROCm decode throughput at 0 / 16K / 64K depth
  roofline.svg        effective bandwidth vs the assumed 120 GB/s peak
  speculative.svg     median generation t/s per mode, with 95% CI whiskers

Colours are chosen to survive greyscale printing: the two series differ in
lightness as well as hue, and every bar is labelled with its value.
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIGDIR = ROOT / "docs/figures"

W, H = 760, 380
PAD_L, PAD_R, PAD_T, PAD_B = 64, 24, 48, 56
PLOT_W = W - PAD_L - PAD_R
PLOT_H = H - PAD_T - PAD_B

INK = "#1b1b1b"
MUTED = "#6b6b6b"
GRID = "#e4e4e4"
VULKAN = "#2f6f8f"
ROCM = "#b5732a"
ACCENT = "#1f7a4d"


def esc(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def text(x: float, y: float, s: str, size: int = 12, anchor: str = "start",
         fill: str = INK, weight: str = "normal") -> str:
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" font-family="ui-sans-serif, system-ui, '
        f'-apple-system, Segoe UI, Helvetica, Arial, sans-serif" font-size="{size}" '
        f'fill="{fill}" text-anchor="{anchor}" font-weight="{weight}">{esc(s)}</text>'
    )


def line(x1, y1, x2, y2, stroke=GRID, width=1, dash=None) -> str:
    d = f' stroke-dasharray="{dash}"' if dash else ""
    return (
        f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
        f'stroke="{stroke}" stroke-width="{width}"{d}/>'
    )


def rect(x, y, w, h, fill) -> str:
    return f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" fill="{fill}"/>'


def svg_open(title: str, desc: str) -> list[str]:
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'viewBox="0 0 {W} {H}" role="img" aria-labelledby="title desc">',
        f'<title id="title">{esc(title)}</title>',
        f'<desc id="desc">{esc(desc)}</desc>',
        f'<rect width="{W}" height="{H}" fill="#ffffff"/>',
        text(PAD_L, 26, title, size=15, weight="600"),
        text(PAD_L, 44, desc, size=11, fill=MUTED),
    ]


def y_axis(max_value: float, ticks: int = 5, unit: str = "") -> tuple[list[str], float]:
    """Return gridline elements and a value->y mapper."""
    step = max_value / ticks
    out = []
    for i in range(ticks + 1):
        value = step * i
        y = PAD_T + PLOT_H - (value / max_value) * PLOT_H
        out.append(line(PAD_L, y, PAD_L + PLOT_W, y))
        label = f"{value:g}{unit}"
        out.append(text(PAD_L - 10, y + 4, label, size=10, anchor="end", fill=MUTED))

    def mapper(v: float) -> float:
        return PAD_T + PLOT_H - (v / max_value) * PLOT_H

    return out, mapper


def load_bench() -> list[dict[str, str]]:
    with (ROOT / "data/processed/llama-bench.csv").open(newline="") as handle:
        return list(csv.DictReader(handle))


def fig_backend_depth() -> str:
    rows = load_bench()
    depths = [0, 16384, 65536]
    labels = ["depth 0", "16K", "64K"]
    by = {(r["backend"], int(r["depth"])): float(r["tps"]) for r in rows}
    peak = max(by.values())

    parts = svg_open(
        "Decode throughput by backend and context depth",
        "Qwen3.6-35B-A3B IQ4_NL, tg128, ngl=999, flash attention on, 2 measured repetitions.",
    )
    grid, ymap = y_axis(30, ticks=6, unit=" t/s")
    parts += grid

    group_w = PLOT_W / len(depths)
    bar_w = group_w * 0.26
    for i, depth in enumerate(depths):
        cx = PAD_L + group_w * (i + 0.5)
        for j, (backend, colour) in enumerate([("Vulkan", VULKAN), ("ROCm", ROCM)]):
            value = by.get((backend, depth))
            if value is None:
                continue
            x = cx + (j - 1) * bar_w + (bar_w * 0.08)
            y = ymap(value)
            parts.append(rect(x, y, bar_w * 0.84, PAD_T + PLOT_H - y, colour))
            parts.append(
                text(x + bar_w * 0.42, y - 6, f"{value:.2f}", size=10,
                     anchor="middle", weight="600")
            )
        parts.append(text(cx, PAD_T + PLOT_H + 20, labels[i], size=11, anchor="middle"))
        parts.append(
            text(cx, PAD_T + PLOT_H + 36, f"{by[('Vulkan', depth)] / by[('ROCm', depth)]:.2f}x",
                 size=10, anchor="middle", fill=ACCENT, weight="600")
        )

    parts.append(line(PAD_L, PAD_T + PLOT_H, PAD_L + PLOT_W, PAD_T + PLOT_H, stroke=INK, width=1.5))
    # legend
    lx = PAD_L
    ly = H - 14
    parts.append(rect(lx, ly - 9, 10, 10, VULKAN))
    parts.append(text(lx + 16, ly, "Vulkan f872b5911 (11310)", size=11))
    parts.append(rect(lx + 200, ly - 9, 10, 10, ROCM))
    parts.append(text(lx + 216, ly, "ROCm build unknown (0)", size=11))
    parts.append(text(PAD_L + PLOT_W, ly, "label under each group = Vulkan / ROCm ratio",
                      size=10, anchor="end", fill=MUTED))
    parts.append("</svg>")
    return "\n".join(parts)


def fig_roofline() -> str:
    with (ROOT / "data/processed/roofline.csv").open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    depths = sorted({int(r["depth"]) for r in rows})
    labels = {0: "0", 16384: "16K", 65536: "64K"}

    parts = svg_open(
        "Effective bandwidth against the assumed memory roofline",
        "First-order model: active weights + F16 attention KV per token, 3 B active of 34.66 B, peak assumed 120 GB/s.",
    )
    grid, ymap = y_axis(140, ticks=7, unit=" GB/s")
    parts += grid

    peak_y = ymap(120)
    parts.append(line(PAD_L, peak_y, PAD_L + PLOT_W, peak_y, stroke=MUTED, width=1.5, dash="6 4"))
    parts.append(text(PAD_L + PLOT_W, peak_y - 8, "assumed peak 120 GB/s",
                      size=10, anchor="end", fill=MUTED))

    for backend, colour, dash in [("Vulkan", VULKAN, None), ("ROCm", ROCM, "5 4")]:
        series = sorted(
            [(int(r["depth"]), float(r["effective_gbps"])) for r in rows if r["backend"] == backend]
        )
        points = []
        for i, (_, value) in enumerate(series):
            x = PAD_L + (PLOT_W / (len(depths) - 1)) * i
            points.append((x, ymap(value), value))
        path = " ".join(f"{'M' if i == 0 else 'L'} {x:.1f} {y:.1f}" for i, (x, y, _) in enumerate(points))
        d = f' stroke-dasharray="{dash}"' if dash else ""
        parts.append(f'<path d="{path}" fill="none" stroke="{colour}" stroke-width="2.5"{d}/>')
        for x, y, value in points:
            parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4.5" fill="{colour}"/>')
            parts.append(text(x, y - 12, f"{value:.1f}", size=10, anchor="middle", weight="600"))

    for i, depth in enumerate(depths):
        x = PAD_L + (PLOT_W / (len(depths) - 1)) * i
        parts.append(text(x, PAD_T + PLOT_H + 20, labels[depth], size=11, anchor="middle"))
    parts.append(text(PAD_L + PLOT_W / 2, H - 14, "context depth (tokens)", size=10, anchor="middle", fill=MUTED))

    parts.append(line(PAD_L, PAD_T + PLOT_H, PAD_L + PLOT_W, PAD_T + PLOT_H, stroke=INK, width=1.5))
    parts.append("</svg>")
    return "\n".join(parts)


def fig_speculative() -> str:
    data = json.loads((ROOT / "data/processed/speculative-stats.json").read_text())
    modes = ["baseline", "mtp_off", "dflash2", "mtp"]
    nice = {
        "baseline": "baseline",
        "mtp_off": "MTP-off",
        "dflash2": "DFlash2 (6)",
        "mtp": "MTP (2)",
    }

    parts = svg_open(
        "Speculative decoding: median generation throughput",
        "Vulkan, 32K capacity, 256-token outputs, 3 prompts x 3 rounds = 9 paired cells per mode. Whiskers are a 95% bootstrap CI of the median.",
    )
    grid, ymap = y_axis(45, ticks=5, unit=" t/s")
    parts += grid

    group_w = PLOT_W / len(modes)
    bar_w = group_w * 0.46
    for i, mode in enumerate(modes):
        s = data["modes"][mode]
        med = s["median_generation_tps"]
        lo, hi = s["median_ci95"]
        cx = PAD_L + group_w * (i + 0.5)
        x = cx - bar_w / 2
        colour = ACCENT if mode in ("dflash2", "mtp") else "#8a8a8a"
        y = ymap(med)
        parts.append(rect(x, y, bar_w, PAD_T + PLOT_H - y, colour))
        parts.append(text(cx, y - 8, f"{med:.2f}", size=11, anchor="middle", weight="600"))
        # CI whisker
        y_hi, y_lo = ymap(hi), ymap(lo)
        parts.append(line(cx, y_hi, cx, y_lo, stroke=INK, width=1.2))
        for yy in (y_hi, y_lo):
            parts.append(line(cx - 7, yy, cx + 7, yy, stroke=INK, width=1.2))
        parts.append(text(cx, PAD_T + PLOT_H + 20, nice[mode], size=11, anchor="middle"))
        if mode != "baseline":
            ratio = data["modes"][mode]["paired_vs"]["baseline"]["median_ratio"]
            parts.append(text(cx, PAD_T + PLOT_H + 36, f"{ratio:.2f}x vs base",
                              size=10, anchor="middle", fill=ACCENT, weight="600"))

    parts.append(line(PAD_L, PAD_T + PLOT_H, PAD_L + PLOT_W, PAD_T + PLOT_H, stroke=INK, width=1.5))
    parts.append(text(PAD_L, H - 14, "n = 9 paired cells per mode; CI is a 20,000-sample percentile bootstrap",
                      size=10, fill=MUTED))
    parts.append("</svg>")
    return "\n".join(parts)


def fig_backends_depth() -> str:
    """Three backends through depth, medians with observed ranges."""
    import csv as _csv
    import statistics as _st

    rows = list(_csv.DictReader(
        (ROOT / "data/processed/ab-b-20261110.csv").open(newline="")
    ))
    rows += list(_csv.DictReader(
        (ROOT / "data/processed/ab-a-20261110.csv").open(newline="")
    ))
    grouped: dict[tuple[str, int], list[float]] = {}
    for row in rows:
        if row.get("status") != "ok" or row.get("test") != "tg128":
            continue
        grouped.setdefault((row["backend"], int(row["depth"])), []).append(float(row["tps"]))

    series = {}
    for (backend, depth), values in grouped.items():
        series.setdefault(backend, []).append(
            (depth, _st.median(values), min(values), max(values))
        )

    parts = svg_open(
        "Three backends through context depth",
        "LFM2.5-8B-A1B UD-Q8_K_XL, 8.69 GiB, tg128, 512 MiB carve-out. Shuffled rounds; medians with observed range.",
    )
    grid, ymap = y_axis(40, ticks=5, unit=" t/s")
    parts += grid
    depths = [0, 4096, 8192, 12288, 16384]
    labels = {0: "0", 4096: "4K", 8192: "8K", 12288: "12K", 16384: "16K"}

    styles = {
        "vulkan": (VULKAN, None, "Vulkan"),
        "rocm": (ROCM, "6 4", "ROCm"),
        "cpu": ("#4a4a4a", "2 3", "CPU"),
    }
    for name, (colour, dash, label) in styles.items():
        pts = sorted(series.get(name, []))
        if not pts:
            continue
        coords = []
        for depth, med, lo, hi in pts:
            if depth not in depths:
                continue
            x = PAD_L + (PLOT_W / (len(depths) - 1)) * depths.index(depth)
            coords.append((x, ymap(med), ymap(hi), ymap(lo), med))
        path = " ".join(f"{'M' if i == 0 else 'L'} {x:.1f} {y:.1f}" for i, (x, y, _, _, _) in enumerate(coords))
        d = f' stroke-dasharray="{dash}"' if dash else ""
        parts.append(f'<path d="{path}" fill="none" stroke="{colour}" stroke-width="2.5"{d}/>')
        for x, y, yh, yl, med in coords:
            parts.append(line(x, yh, x, yl, stroke=colour, width=1.2))
            parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="{colour}"/>')
        # label the last point
        lx, ly, _, _, med = coords[-1]
        parts.append(text(lx + 8, ly + 4, f"{label} {med:.1f}", size=10, fill=colour, weight="600"))

    for i, depth in enumerate(depths):
        x = PAD_L + (PLOT_W / (len(depths) - 1)) * i
        parts.append(text(x, PAD_T + PLOT_H + 20, labels[depth], size=11, anchor="middle"))
    parts.append(text(PAD_L + PLOT_W / 2, H - 14, "context depth (tokens); whiskers are observed min–max",
                      size=10, anchor="middle", fill=MUTED))
    parts.append(line(PAD_L, PAD_T + PLOT_H, PAD_L + PLOT_W, PAD_T + PLOT_H, stroke=INK, width=1.5))
    parts.append("</svg>")
    return "\n".join(parts)


def fig_quant() -> str:
    """Effective bandwidth by backend and quantization, same session."""
    import csv as _csv
    import statistics as _st

    rows = [
        r for r in _csv.DictReader(
            (ROOT / "data/processed/ab-quant-20261110.csv").open(newline="")
        )
        if r.get("status") == "ok" and r.get("test") == "tg128"
    ]
    active = {"UD-IQ4_NL": 0.513, "UD-Q8_K_XL": 1.102}
    grouped: dict[tuple[str, str], list[float]] = {}
    for row in rows:
        grouped.setdefault((row["backend"], row["quant"]), []).append(float(row["tps"]))
    values = {
        key: _st.median(vals) * active[key[1]] for key, vals in grouped.items()
    }

    parts = svg_open(
        "Effective bandwidth by backend and quantization",
        "Depth 0, LFM2.5-8B-A1B, same interleaved session. Active-weight bytes x median t/s against an assumed 120 GB/s peak.",
    )
    grid, ymap = y_axis(45, ticks=5, unit=" GB/s")
    parts += grid
    backends = ["vulkan", "rocm", "cpu"]
    labels = {"vulkan": "Vulkan", "rocm": "ROCm", "cpu": "CPU"}
    group_w = PLOT_W / len(backends)
    bar_w = group_w * 0.28
    for i, backend in enumerate(backends):
        cx = PAD_L + group_w * (i + 0.5)
        for j, (quant, colour) in enumerate(
            [("UD-IQ4_NL", "#7a5ea8"), ("UD-Q8_K_XL", "#2f6f8f")]
        ):
            value = values.get((backend, quant))
            if value is None:
                continue
            x = cx + (j - 1) * bar_w + bar_w * 0.08
            y = ymap(value)
            parts.append(rect(x, y, bar_w * 0.84, PAD_T + PLOT_H - y, colour))
            parts.append(text(x + bar_w * 0.42, y - 6, f"{value:.1f}", size=10,
                              anchor="middle", weight="600"))
        parts.append(text(cx, PAD_T + PLOT_H + 20, labels[backend], size=11, anchor="middle"))

    peak_y = ymap(120)
    parts.append(line(PAD_L, peak_y, PAD_L + PLOT_W, peak_y, stroke=MUTED, width=1.2, dash="6 4"))
    parts.append(text(PAD_L + PLOT_W, peak_y - 8, "assumed peak 120 GB/s",
                      size=10, anchor="end", fill=MUTED))
    parts.append(line(PAD_L, PAD_T + PLOT_H, PAD_L + PLOT_W, PAD_T + PLOT_H, stroke=INK, width=1.5))
    lx, ly = PAD_L, H - 14
    parts.append(rect(lx, ly - 9, 10, 10, "#7a5ea8"))
    parts.append(text(lx + 16, ly, "IQ4_NL", size=11))
    parts.append(rect(lx + 100, ly - 9, 10, 10, "#2f6f8f"))
    parts.append(text(lx + 116, ly, "Q8_K_XL", size=11))
    parts.append("</svg>")
    return "\n".join(parts)


def main() -> int:
    FIGDIR.mkdir(parents=True, exist_ok=True)
    figures = {
        "backend-depth.svg": fig_backend_depth(),
        "roofline.svg": fig_roofline(),
        "speculative.svg": fig_speculative(),
        "backends-depth.svg": fig_backends_depth(),
        "quant.svg": fig_quant(),
    }
    for name, content in figures.items():
        (FIGDIR / name).write_text(content + "\n")
        print(f"wrote {FIGDIR / name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
