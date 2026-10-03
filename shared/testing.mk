# shared/testing.mk — test suite and protocol check targets
# Assumes PY, GF, and GUT_FEELING_* vars are defined in the root Makefile.

.PHONY: test test-fast test-strict test-cov mcp-check smoke

test: $(GF) ## Full test suite (loads model once, ~30s)
	$(PY) -m pytest

test-fast: $(GF) ## Unit tests only, no model load
	$(PY) -m pytest -m "not model"

test-strict: $(GF) ## Full suite; FAILS if weights missing (CI use)
	GUT_FEELING_REQUIRE_MODEL=1 $(PY) -m pytest

test-cov: $(GF) ## Unit tests with coverage report
	$(PY) -m pytest --cov=gut_feeling --cov-report=term-missing -m "not model"

mcp-check: $(GF) ## MCP protocol end-to-end check
	$(PY) -u scripts/test_mcp_client.py

smoke: $(GF) ## Direct MPS inference smoke test
	$(PY) -u scripts/smoke_mps.py
