# shared/testing.mk — test suite and protocol check targets
# Assumes PY, EMBER, and EMBER_* vars are defined in the root Makefile.

.PHONY: test test-fast test-strict test-cov test-evals eval-run eval-report eval-export eval-snapshot eval-agent eval-agent-smoke mcp-check smoke

test: $(EMBER) ## Full test suite (loads model once, ~30s)
	$(PY) -m pytest

test-fast: $(EMBER) ## Unit tests only, no model load
	$(PY) -m pytest -m "not model"

test-strict: $(EMBER) ## Full suite; FAILS if weights missing (CI use)
	EMBER_REQUIRE_MODEL=1 $(PY) -m pytest

test-cov: $(EMBER) ## Unit tests with coverage report
	$(PY) -m pytest --cov=ember --cov-report=term-missing -m "not model"

test-evals: $(EMBER) ## Calibration eval suite: positive + negative recipe cases (loads model)
	$(PY) -m pytest -m "evals" -v tests/test_advise_evals.py

eval-run: $(EMBER) ## Run the calibration eval dataset against the live server
	$(PY) evals/eval/run_evals.py

eval-report: ## Render the most recent eval results as a Markdown table
	$(PY) evals/eval/report_evals.py

eval-export: ## Write the reviewer bundle (HTML + Markdown report) for the latest run
	$(PY) evals/eval/report_evals.py --export

eval-snapshot: ## Copy the latest run into the tracked benchmark/ bundle the site renders
	$(PY) evals/eval/snapshot_evals.py

eval-agent: $(EMBER) ## Agent-in-the-loop eval through opencode (opt-in; uses API credit)
	$(PY) evals/eval/run_agent_evals.py

eval-agent-smoke: $(EMBER) ## Agent eval smoke: 6 scenarios, 1 trial
	$(PY) evals/eval/run_agent_evals.py --smoke

mcp-check: $(EMBER) ## MCP protocol end-to-end check
	$(PY) -u scripts/test_mcp_client.py

smoke: $(EMBER) ## Direct MPS inference smoke test
	$(PY) -u scripts/smoke_mps.py
