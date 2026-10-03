#!/usr/bin/env bash
# Readiness check for the Clef-Flash local setup. Read-only: starts/stops nothing.
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="$REPO_ROOT/.venv/bin/python"
HOST="${CLEF_HOST:-127.0.0.1}"
PORT="${CLEF_PORT:-8765}"
URL="http://${HOST}:${PORT}"
MODEL_DIR="$REPO_ROOT/.models/clef-flash"

ok()   { printf "  \033[32m✓\033[0m %s\n" "$1"; }
bad()  { printf "  \033[31m✗\033[0m %s\n" "$1"; }
warn() { printf "  \033[33m!\033[0m %s\n" "$1"; }

echo "Clef-Flash doctor"
echo
echo "Environment:"
if command -v uv >/dev/null 2>&1; then ok "uv: $(uv --version)"; else bad "uv not found"; fi
if [ -x "$PY" ]; then ok "venv python: $("$PY" --version 2>&1)"; else bad "venv missing ($PY) — run: make sync"; fi
if command -v opencode >/dev/null 2>&1; then ok "opencode: $(opencode --version 2>&1 | head -1)"; else warn "opencode not on PATH"; fi

if [ -x "$PY" ]; then
  "$PY" - <<'PYEOF'
import importlib
import importlib.util

required = ["torch", "transformers", "safetensors", "huggingface_hub",
            "fastapi", "uvicorn", "mcp", "httpx", "torchvision", "PIL"]
missing = [m for m in required if importlib.util.find_spec(m) is None]
if missing:
    print("  \033[31m✗\033[0m missing modules: " + ", ".join(missing) + " — run: make sync")
else:
    torch = importlib.import_module("torch")
    mps = torch.backends.mps.is_available()
    mark = "\033[32m✓\033[0m" if mps else "\033[33m!\033[0m"
    print(f"  {mark} torch {torch.__version__} | transformers {importlib.import_module('transformers').__version__} | mps={'yes' if mps else 'no (CPU fallback)'}")
PYEOF
fi

echo
echo "Model:"
if [ -f "$MODEL_DIR/model.safetensors.index.json" ]; then
  size="$(du -sh "$MODEL_DIR" 2>/dev/null | cut -f1)"
  ok "weights present (${size:-?})"
else
  bad "weights missing — run: make download"
fi

echo
echo "Server:"
if curl -sf "$URL/health" >/dev/null 2>&1; then
  ok "up at ${URL}"
  curl -s "$URL/health" 2>/dev/null | "$PY" -c 'import sys,json; print("     ", json.load(sys.stdin).get("engine"))' 2>/dev/null || true
else
  warn "not running at ${URL} — start with: make start"
fi
echo
