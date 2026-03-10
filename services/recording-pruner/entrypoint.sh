#!/usr/bin/env bash
set -euo pipefail

RECORDINGS_DIR="${RECORDINGS_DIR:-/recordings}"
TOTAL_LIMIT_BYTES="${MEDIA_STORAGE_TOTAL_LIMIT_BYTES:-10737418240}"
RECORDING_SHARE_PERCENT="${MEDIA_STORAGE_RECORDING_SHARE_PERCENT:-80}"
if [[ -n "${RECORDING_STORAGE_LIMIT_BYTES:-}" ]]; then
  LIMIT_BYTES="${RECORDING_STORAGE_LIMIT_BYTES}"
else
  artifact_share_percent=$((100 - RECORDING_SHARE_PERCENT))
  artifact_bytes=$((TOTAL_LIMIT_BYTES * artifact_share_percent / 100))
  LIMIT_BYTES=$((TOTAL_LIMIT_BYTES - artifact_bytes))
fi
INTERVAL_SECONDS="${RECORDING_PRUNE_INTERVAL_SECONDS:-30}"

log() {
  printf '[recording-pruner] %s\n' "$1"
}

calculate_usage() {
  find "$RECORDINGS_DIR" -type f -exec stat -c '%s' {} \; 2>/dev/null | awk '{sum += $1} END {print sum + 0}'
}

cleanup_empty_dirs() {
  find "$RECORDINGS_DIR" -depth -type d -empty -delete 2>/dev/null || true
}

prune_if_needed() {
  local current_usage oldest

  current_usage="$(calculate_usage)"
  if [[ "$current_usage" -le "$LIMIT_BYTES" ]]; then
    return
  fi

  log "usage ${current_usage} bytes exceeds limit ${LIMIT_BYTES}; pruning oldest recordings"

  while [[ "$current_usage" -gt "$LIMIT_BYTES" ]]; do
    oldest="$(
      find "$RECORDINGS_DIR" -type f -printf '%T@ %p\n' 2>/dev/null \
        | sort -n \
        | sed -n '1p' \
        | cut -d' ' -f2-
    )"

    if [[ -z "$oldest" ]]; then
      break
    fi

    rm -f "$oldest"
    cleanup_empty_dirs
    current_usage="$(calculate_usage)"
    log "deleted ${oldest}; usage now ${current_usage} bytes"
  done
}

mkdir -p "$RECORDINGS_DIR"
log "watching ${RECORDINGS_DIR} with ${LIMIT_BYTES} byte limit every ${INTERVAL_SECONDS}s"

while true; do
  prune_if_needed
  sleep "$INTERVAL_SECONDS"
done
