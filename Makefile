# ember — development lifecycle
#
# Run `make` or `make help` to list targets.
# Server lifecycle targets wrap the `ember` CLI so contributors and
# users share one implementation.
#
# Makefile layout:
#   This file defines variables and the venv sentinel only.
#   All targets live in shared/*.mk domain modules:
#     shared/helper.mk   — help target, ANSI colors, .DEFAULT_GOAL
#     shared/python.mk   — sync, compile, lint, format, typecheck, security, pr-ready
#     shared/testing.mk  — test, test-fast, test-strict, test-cov, mcp-check, smoke
#     shared/server.mk   — serve, start, stop, restart, status, logs, mcp, mcp-list, doctor
#     shared/release.mk  — download, init, opencode, setup, bootstrap, check, ci, clean, clean-model, deployment-requirements, deploy, undeploy
#     shared/vault.mk    — vault-audit
#     shared/site.mk     — site, site-serve (Jekyll GitHub Pages)
SHELL := /bin/bash

REPO_ROOT := $(CURDIR)
VENV      := $(REPO_ROOT)/.venv
PY        := $(VENV)/bin/python
EMBER     := $(VENV)/bin/ember
UV        ?= uv

EMBER_HOST   ?= 127.0.0.1
EMBER_PORT   ?= 8765
EMBER_DEVICE ?= auto
export EMBER_HOST EMBER_PORT EMBER_DEVICE

MODEL_DIR ?= $(REPO_ROOT)/.models/clef-flash

# Venv sentinel — rebuilt whenever pyproject.toml or uv.lock change
$(EMBER): pyproject.toml uv.lock
	$(UV) sync
	@touch $(EMBER)

include shared/helper.mk
include shared/python.mk
include shared/testing.mk
include shared/server.mk
include shared/release.mk
include shared/vault.mk
include shared/site.mk

.PHONY: setup-hooks
setup-hooks: ## Install git hooks from .githooks/ (sets core.hooksPath)
	git config core.hooksPath .githooks
	@echo "git hooks installed from .githooks/"
