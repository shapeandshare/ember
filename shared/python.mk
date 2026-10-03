# shared/python.mk — Python toolchain targets (lint, format, typecheck, security)
# Assumes UV, PY, VENV, REPO_ROOT, and GF are defined in the root Makefile.

.PHONY: sync compile lint format format-check typecheck security pr-ready

sync: $(GF) ## Install/sync Python deps
	$(UV) sync

compile: $(GF) ## Byte-compile all Python modules
	$(PY) -m compileall -q gut_feeling scripts tests

lint: $(GF) ## Run ruff linter
	$(UV) run ruff check gut_feeling tests scripts

format: $(GF) ## Run ruff formatter (in-place)
	$(UV) run ruff format gut_feeling tests scripts

format-check: $(GF) ## Check formatting without modifying
	$(UV) run ruff format --check gut_feeling tests scripts

typecheck: $(GF) ## Run mypy strict type check
	$(UV) run mypy gut_feeling

security: $(GF) ## Run bandit security scan
	$(UV) run bandit -r gut_feeling -c pyproject.toml

pr-ready: format lint typecheck security compile test-fast ## Full pre-PR gate (no model load)
