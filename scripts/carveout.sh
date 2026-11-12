#!/usr/bin/env bash
# Inspect and change the UMA carve-out and GTT size on an AMD APU.
#
# Two interfaces exist on kernel 7.0.0-43:
#   * raw sysfs: /sys/class/drm/card*/device/uma/carveout        (index, writable)
#                /sys/class/drm/card*/device/uma/carveout_options (read-only)
#   * amd-smi:   amd-smi set -g 0 -m <index>   and   -G <GB> for GTT
#
# The card number is not stable. This script discovers the card that actually
# exposes the node instead of assuming card0.
#
# Writes require root. Run with sudo, or use --show (read-only).
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: carveout.sh [options]

  --show                 Print current carve-out, options, GTT and host RAM
  --set-index N          Write carve-out index N (0-7 on this model)
  --set-gb N             Write the index whose label is N GB
  --gtt-gb N             Set GTT to N GB via amd-smi (requires sudo)
  --yes                  Required for any write
  -h, --help             This help

Examples:
  ./scripts/carveout.sh --show
  sudo ./scripts/carveout.sh --set-gb 16 --yes
  sudo ./scripts/carveout.sh --gtt-gb 24 --yes
EOF
}

find_node() {
  local matches
  matches=$(compgen -G '/sys/class/drm/card*/device/uma/carveout' || true)
  if [[ -z "$matches" ]]; then
    echo "error: no /sys/class/drm/card*/device/uma/carveout node" >&2
    return 1
  fi
  local count
  count=$(printf '%s\n' "$matches" | wc -l)
  if ((count > 1)); then
    echo "warning: $count carveout nodes found; using the first" >&2
  fi
  printf '%s\n' "$matches" | head -1
}

show() {
  local node
  node=$(find_node)
  local card=${node%/device/uma/carveout}
  echo "card:        ${card##*/}"
  echo "node:        $node"
  echo "index:       $(cat "$node")"
  echo "options:"
  sed 's/^/  /' "${node%carveout}carveout_options"
  echo "vram_total:  $(( $(cat "$card/device/mem_info_vram_total") / 1048576 )) MiB"
  echo "gtt_total:   $(( $(cat "$card/device/mem_info_gtt_total") / 1048576 )) MiB"
  awk '/MemTotal/ {printf "host_total:  %d MiB\n", $2/1024}' /proc/meminfo
  if command -v amd-smi >/dev/null; then
    echo "amd-smi:     $(amd-smi version 2>/dev/null | head -1)"
  fi
}

index_for_gb() {
  local gb="$1"
  local node
  node=$(find_node)
  local options="${node%carveout}carveout_options"
  # Labels look like "7: High (16 GB)" or "1:  (1 GB)".
  awk -v want="$gb" '
    match($0, /\(([0-9]+) GB\)/, m) {
      if (m[1] == want) { print $1; found=1; exit }
    }
    END { if (!found) exit 1 }
  ' "$options"
}

require_yes() {
  if [[ "${YES:-0}" != "1" ]]; then
    echo "refusing to write without --yes" >&2
    exit 2
  fi
  if [[ $EUID -ne 0 ]]; then
    echo "error: writes require root; run with sudo" >&2
    exit 2
  fi
}

MODE=show
INDEX=""
GB=""
GTT=""
YES=0

while (($# > 0)); do
  case "$1" in
    --show) MODE=show; shift ;;
    --set-index) MODE=set-index; INDEX="$2"; shift 2 ;;
    --set-gb) MODE=set-gb; GB="$2"; shift 2 ;;
    --gtt-gb) MODE=gtt; GTT="$2"; shift 2 ;;
    --yes) YES=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

case "$MODE" in
  show)
    show
    ;;
  set-index)
    require_yes
    node=$(find_node)
    if ! grep -q "^${INDEX}:" "${node%carveout}carveout_options"; then
      echo "error: index $INDEX is not in the option table" >&2
      exit 2
    fi
    echo "before: $(cat "$node")"
    printf '%s\n' "$INDEX" > "$node"
    echo "after:  $(cat "$node")"
    echo "verify after reboot:"
    echo "  cat $node"
    echo "  echo \$(( \$(cat ${node%/uma/carveout}/mem_info_vram_total) / 1048576 )) MiB"
    ;;
  set-gb)
    require_yes
    if ! INDEX=$(index_for_gb "$GB"); then
      echo "error: no carve-out option labelled ${GB} GB" >&2
      echo "run --show to see the table" >&2
      exit 2
    fi
    node=$(find_node)
    echo "mapping ${GB} GB -> index ${INDEX}"
    printf '%s\n' "$INDEX" > "$node"
    echo "after: $(cat "$node")"
    echo "note: the carve-out may take effect only after a reboot"
    ;;
  gtt)
    require_yes
    if ! command -v amd-smi >/dev/null; then
      echo "error: amd-smi not installed" >&2
      exit 2
    fi
    echo "before: $(awk '/MemTotal/ {print "host " $2/1024 " MiB"}' /proc/meminfo)"
    amd-smi set -g 0 -G "$GTT"
    echo "after:"
    show
    ;;
esac
