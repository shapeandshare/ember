# shared/testing.mk — test suite and protocol check targets
# Assumes PY, EMBER, and EMBER_* vars are defined in the root Makefile.

.PHONY: test test-fast test-strict test-cov mcp-check smoke

test: $(EMBER) ## Full test suite (loads model once, ~30s)
	$(PY) -m pytest

test-fast: $(EMBER) ## Unit tests only, no model load
	$(PY) -m pytest -m "not model"

test-strict: $(EMBER) ## Full suite; FAILS if weights missing (CI use)
	EMBER_REQUIRE_MODEL=1 $(PY) -m pytest

test-cov: $(EMBER) ## Unit tests with coverage report
	$(PY) -m pytest --cov=ember --cov-report=term-missing -m "not model"

mcp-check: $(EMBER) ## MCP protocol end-to-end check
	$(PY) -u scripts/test_mcp_client.py

smoke: $(EMBER) ## Direct MPS inference smoke test
	$(PY) -u scripts/smoke_mps.py
