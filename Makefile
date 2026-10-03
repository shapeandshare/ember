# Clef-Flash Local — lifecycle management
#
# Run `make` or `make help` to list targets.
SHELL := /bin/bash
.DEFAULT_GOAL := help

REPO_ROOT  := $(CURDIR)
VENV       := $(REPO_ROOT)/.venv
PY         := $(VENV)/bin/python
UV         ?= uv

CLEF_HOST   ?= 127.0.0.1
CLEF_PORT   ?= 8765
CLEF_DEVICE ?= auto
export CLEF_HOST CLEF_PORT CLEF_DEVICE

MODEL_DIR  ?= $(REPO_ROOT)/.models/clef-flash
SERVER_SH  := $(REPO_ROOT)/scripts/clef-server.sh
SERVER_LOG := $(REPO_ROOT)/logs/server.log

.PHONY: help setup sync download init bootstrap opencode serve start stop restart status logs mcp \
        mcp-list test test-fast test-strict mcp-check smoke compile check ci doctor clean clean-model

help: ## Show this help
	@printf "\nClef-Flash Local — make targets\n\n"
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@printf "\n  host=%s port=%s device=%s\n\n" "$(CLEF_HOST)" "$(CLEF_PORT)" "$(CLEF_DEVICE)"

# --------------------------------------------------------------------------- #
# environment
# --------------------------------------------------------------------------- #
$(PY):
	$(UV) sync

setup: sync download ## First-time setup: deps + model weights

sync: ## Install/sync Python dependencies (uv)
	$(UV) sync

download: $(PY) ## Download the pinned Clef-Flash weights (~18 GB) to .models/
	$(PY) -c "from huggingface_hub import snapshot_download; from clef_local.models import get; spec = get('flash'); snapshot_download(spec.repo, revision=spec.revision, local_dir='$(MODEL_DIR)')"

init: $(PY) ## Regenerate opencode.json with this clone's absolute paths (idempotent)
	$(VENV)/bin/clef init

opencode: $(PY) ## Install the local opencode plugin (project scope)
	$(VENV)/bin/clef init --opencode

bootstrap: setup init doctor ## First run: deps + weights + MCP config + readiness check

# --------------------------------------------------------------------------- #
# model server lifecycle
# --------------------------------------------------------------------------- #
serve: $(PY) ## Run the model server in the foreground (Ctrl-C to stop)
	$(PY) -m clef_local.server

start: $(PY) ## Start the warm model server in the background
	$(SERVER_SH) start

stop: ## Stop the background model server (only the one on this host:port)
	$(SERVER_SH) stop

restart: ## Restart the background model server
	$(SERVER_SH) restart

status: ## Show whether the model server is up
	$(SERVER_SH) status

logs: ## Tail the model server log
	@mkdir -p "$(REPO_ROOT)/logs"
	tail -f "$(SERVER_LOG)"

mcp: $(PY) ## Run the MCP server in the foreground (stdio; for debugging)
	$(PY) clef_local/mcp_server.py

mcp-list: ## Ask opencode to list its configured MCP servers
	opencode mcp list

# --------------------------------------------------------------------------- #
# quality
# --------------------------------------------------------------------------- #
test: $(PY) ## Run the full test suite (loads the model once)
	$(PY) -m pytest

test-fast: $(PY) ## Run unit tests only (no model load)
	$(PY) -m pytest -m "not model"

test-strict: $(PY) ## Full suite that FAILS (not skips) if weights are missing (CI)
	CLEF_REQUIRE_MODEL=1 $(PY) -m pytest

mcp-check: $(PY) ## MCP protocol end-to-end check
	$(PY) -u scripts/test_mcp_client.py

smoke: $(PY) ## Direct MPS inference smoke test
	$(PY) -u scripts/smoke_mps.py

compile: $(PY) ## Byte-compile all Python modules
	$(PY) -m py_compile clef_local/*.py scripts/*.py tests/*.py
	@echo "compile OK"

check: compile test-fast ## Fast pre-commit gate (compile + unit tests)

ci: bootstrap check test-strict ## Full non-interactive gate (bootstrap + check + strict tests)

doctor: ## Check environment, model, and server readiness
	@bash "$(REPO_ROOT)/scripts/doctor.sh"

# --------------------------------------------------------------------------- #
# maintenance
# --------------------------------------------------------------------------- #
clean: ## Remove caches and stale pid files (keeps .venv and .models)
	@find "$(REPO_ROOT)" -type d -name __pycache__ -not -path "*/.venv/*" -exec rm -rf {} + 2>/dev/null || true
	@find "$(REPO_ROOT)" -type f -name '*.pyc' -not -path "*/.venv/*" -delete 2>/dev/null || true
	@rm -rf "$(REPO_ROOT)/.pytest_cache"
	@rm -f "$(REPO_ROOT)/logs/server.pid"
	@echo "cleaned caches and pid files"

clean-model: ## Delete the downloaded model weights (CLEF_FORCE=1 to skip the prompt)
	@if [ "$$CLEF_FORCE" = "1" ]; then :; else printf "Delete %s? [y/N] " "$(MODEL_DIR)"; read ans; [ "$$ans" = "y" ] || { echo "aborted"; exit 1; }; fi
	@rm -rf "$(MODEL_DIR)"
	@echo "removed $(MODEL_DIR)"
