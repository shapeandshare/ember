#!/usr/bin/env bash
# Manage the warm Clef-Flash model server (the process that holds the MPS model).
#
# Usage: scripts/clef-server.sh {start|stop|restart|status}
#
# Safety: `stop` only terminates processes that (a) are recorded in the pid file,
# or (b) are listening on CLEF_PORT *and* whose command line is clef_local.server.
# It waits for the port to be released before returning, so `restart` is reliable.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_PY="$REPO_ROOT/.venv/bin/python"
HOST="${CLEF_HOST:-127.0.0.1}"
PORT="${CLEF_PORT:-8765}"
URL="http://${HOST}:${PORT}"
LOG="${CLEF_SERVER_LOG:-$REPO_ROOT/logs/server.log}"
PID_FILE="${CLEF_PIDFILE:-$REPO_ROOT/logs/server.pid}"

mkdir -p "$REPO_ROOT/logs"

is_up() { curl -sf --max-time 2 "$URL/health" >/dev/null 2>&1; }

port_pids() { lsof -ti "tcp:${PORT}" 2>/dev/null || true; }

is_our_server() {
  local pid="$1"
  ps -o command= -p "$pid" 2>/dev/null | grep -q "clef_local.server"
}

wait_port_free() {
  for _ in $(seq 1 100); do
    [ -z "$(port_pids)" ] && return 0
    sleep 0.2
  done
  return 1
}

start() {
  if is_up; then echo "already running at $URL"; return 0; fi
  echo "starting Clef server (log: $LOG) ..."
  cd "$REPO_ROOT"
  nohup "$VENV_PY" -m clef_local.server >>"$LOG" 2>&1 &
  echo $! >"$PID_FILE"
  for _ in $(seq 1 150); do
    if is_up; then echo "ready at $URL"; return 0; fi
    sleep 2
  done
  echo "timed out waiting for $URL; check $LOG" >&2
  return 1
}

stop() {
  # 1) pid file
  if [ -f "$PID_FILE" ]; then
    local p
    p="$(cat "$PID_FILE" 2>/dev/null || true)"
    [ -n "$p" ] && kill "$p" 2>/dev/null || true
  fi
  # 2) anything on our port that is actually our server
  for pid in $(port_pids); do
    if is_our_server "$pid"; then kill "$pid" 2>/dev/null || true; fi
  done
  rm -f "$PID_FILE"

  if ! wait_port_free; then
    # force-kill remaining clef servers holding the port
    for pid in $(port_pids); do
      if is_our_server "$pid"; then kill -9 "$pid" 2>/dev/null || true; fi
    done
    wait_port_free || true
  fi
  echo "stopped"
}

case "${1:-status}" in
  start) start ;;
  stop) stop ;;
  restart) stop; start ;;
  status) if is_up; then curl -s "$URL/health"; echo; else echo "not running"; fi ;;
  *) echo "usage: $0 {start|stop|restart|status}" >&2; exit 2 ;;
esac
