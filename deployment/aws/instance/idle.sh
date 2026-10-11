#!/bin/bash
# idle.sh — check ember request count and shut down if idle for >= IDLE_MINUTES.
#
# Runs as ember-idle.service, triggered by ember-idle.timer (every 1 minute).
# Reads ember_advise_requests_total from http://127.0.0.1:8765/metrics,
# sums over all status labels, and calls shutdown -h now once the count has
# not changed for IDLE_MINUTES consecutive minutes.
#
# State files (dir defaults to /var/lib/ember; EMBER_IDLE_STATE_DIR overrides):
#   idle-count   — last observed request count
#   idle-since   — epoch seconds when the count last changed (or first check)
#
# Do NOT enable xtrace (set -x): no secrets here, but keep the convention.

set -euo pipefail

IDLE_MINUTES="{{IDLE_MINUTES}}"
METRICS_URL="http://127.0.0.1:8765/metrics"
STATE_DIR="${EMBER_IDLE_STATE_DIR:-/var/lib/ember}"
COUNT_FILE="${STATE_DIR}/idle-count"
SINCE_FILE="${STATE_DIR}/idle-since"
SHUTDOWN_CMD="${IDLE_SHUTDOWN_CMD:-shutdown -h now}"

# Guard: do nothing when idle auto-stop is disabled.
if [[ "${IDLE_MINUTES}" -eq 0 ]]; then
    exit 0
fi

mkdir -p "${STATE_DIR}"

# Fetch metrics and sum ember_advise_requests_total over all status labels.
CURRENT_COUNT="$(
    curl -sf "${METRICS_URL}" 2>/dev/null \
    | awk '/^ember_advise_requests_total\{/ { sum += $2 } END { print int(sum) }'
)" || CURRENT_COUNT="0"

# Read the last observed count (default 0 on first run).
LAST_COUNT="0"
if [[ -f "${COUNT_FILE}" ]]; then
    LAST_COUNT="$(cat "${COUNT_FILE}")"
fi

NOW="$(date +%s)"

if [[ "${CURRENT_COUNT}" != "${LAST_COUNT}" ]]; then
    # Count changed — reset the idle-since timestamp and record the new count.
    echo "${CURRENT_COUNT}" > "${COUNT_FILE}"
    echo "${NOW}" > "${SINCE_FILE}"
    exit 0
fi

# Count unchanged — check how long we have been idle.
if [[ ! -f "${SINCE_FILE}" ]]; then
    echo "${NOW}" > "${SINCE_FILE}"
    exit 0
fi
IDLE_SINCE="$(cat "${SINCE_FILE}")"

IDLE_SECONDS=$(( NOW - IDLE_SINCE ))
THRESHOLD_SECONDS=$(( IDLE_MINUTES * 60 ))

if [[ "${IDLE_SECONDS}" -ge "${THRESHOLD_SECONDS}" ]]; then
    echo "idle.sh: idle for ${IDLE_SECONDS}s (>= ${THRESHOLD_SECONDS}s), shutting down"
    ${SHUTDOWN_CMD}
fi
