#!/usr/bin/env bash
# Measure which GTT control interface actually changes the aperture.
#
# Run with sudo. It writes to the live system and must not run during a
# benchmark. Every step is logged, including the before/after value, so the
# result can be recorded in docs/hardware.md rather than assumed.
#
# It tries, in order:
#   1. amd-smi set -G <GB>   (system-wide; -g is rejected)
#   2. ttm.pages_limit
# and stops at the first interface that changes mem_info_gtt_total.
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
  echo "error: run with sudo" >&2
  exit 2
fi

OUT="${OUT:-runs/gtt-test-$(date -u +%Y%m%dT%H%M%SZ).txt}"
mkdir -p "$(dirname "$OUT")"

gtt() {
  local f
  f=$(compgen -G '/sys/class/drm/card*/device/mem_info_gtt_total' | head -1)
  [[ -n "$f" ]] && echo $(( $(cat "$f") / 1048576 )) || echo "?"
}

host() {
  awk '/MemTotal/ {printf "%d", $2/1024}' /proc/meminfo
}

log() { echo "$*" | tee -a "$OUT"; }

log "# GTT control test"
log "# $(date -u +%Y-%m-%dT%H:%M:%SZ) kernel $(uname -r)"
log "baseline: gtt=$(gtt) MiB host=$(host) MiB"
log "pages_limit baseline: $(cat /sys/module/ttm/parameters/pages_limit)"
log

log "## 1. amd-smi set -G 12 (system-wide; -G cannot be combined with -g)"
if command -v amd-smi >/dev/null; then
  amd-smi set -G 12 2>&1 | tee -a "$OUT" || true
  log "after: gtt=$(gtt) MiB host=$(host) MiB"
  if [[ "$(gtt)" != "?" && "$(gtt)" -ge 11000 ]]; then
    log "RESULT: amd-smi -G changes GTT immediately (or after this write)"
    log "wrote $OUT"
    exit 0
  fi
else
  log "amd-smi not installed"
fi
log

log "## 2. ttm.pages_limit (expected: does NOT change the GTT aperture)"
ORIG=$(cat /sys/module/ttm/parameters/pages_limit)
log "pages_limit before: $ORIG"
if [[ -w /sys/module/ttm/parameters/pages_limit ]]; then
  echo 3145728 > /sys/module/ttm/parameters/pages_limit
  log "pages_limit now: $(cat /sys/module/ttm/parameters/pages_limit)"
  log "after: gtt=$(gtt) MiB host=$(host) MiB"
  # restore, so the machine is left as found
  echo "$ORIG" > /sys/module/ttm/parameters/pages_limit
  log "restored pages_limit to $ORIG"
else
  log "pages_limit not writable"
fi

log
log "RESULT: no interface changed mem_info_gtt_total immediately."
log "ttm.pages_limit is a TTM allocation cap, not the GTT aperture size."
log "Next: reboot and re-check; if amd-smi -G persisted, it is a boot-time setting."
log "Fallback: kernel cmdline  amdgpu.gttsize=12288"
log "wrote $OUT"
