# shared/python.mk — Python toolchain targets (lint, format, typecheck, security)
# Assumes UV, PY, VENV, REPO_ROOT, and EMBER are defined in the root Makefile.

.PHONY: sync compile lint format format-check typecheck security pr-ready

sync: $(EMBER) ## Install/sync Python deps
	$(UV) sync

compile: $(EMBER) ## Byte-compile all Python modules
	$(PY) -m compileall -q ember scripts tests deployment/aws

lint: $(EMBER) ## Run ruff linter
	$(UV) run ruff check ember tests scripts deployment/aws/ember_aws

format: $(EMBER) ## Run ruff formatter (in-place)
	$(UV) run ruff format ember tests scripts deployment/aws/ember_aws

format-check: $(EMBER) ## Check formatting without modifying
	$(UV) run ruff format --check ember tests scripts deployment/aws/ember_aws

typecheck: $(EMBER) ## Run mypy strict type check
	$(UV) run mypy

security: $(EMBER) ## Run bandit security scan
	$(UV) run bandit -r ember deployment/aws/ember_aws -c pyproject.toml

pr-ready: format lint typecheck security compile test-fast ## Full pre-PR gate (no model load)
