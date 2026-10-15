# shared/testing.mk — test suite and protocol check targets
# Assumes PY, EMBER, and EMBER_* vars are defined in the root Makefile.

.PHONY: test test-fast test-strict test-cov test-evals eval-run eval-report eval-export eval-snapshot eval-context eval-context-smoke eval-agent eval-agent-smoke dataset-lint dataset-card audit-sources mcp-check smoke conda-smoke

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

eval-context: $(EMBER) ## Long-context probe: measure each model's cap on MPS (hours; opt-in)
	$(PY) evals/context/run_context.py

eval-context-smoke: $(EMBER) ## Long-context probe smoke: flash, 2K and 4K, 3 items (minutes)
	$(PY) evals/context/run_context.py --smoke

eval-agent: $(EMBER) ## Agent-in-the-loop eval through opencode (opt-in; uses API credit)
	$(PY) evals/eval/run_agent_evals.py

eval-agent-smoke: $(EMBER) ## Agent eval smoke: 6 scenarios, 1 trial
	$(PY) evals/eval/run_agent_evals.py --smoke

dataset-lint: $(EMBER) ## Lint the benchmark dataset (report mode; enforced rules exit 1)
	$(PY) -m evals.dataset.lint

dataset-card: $(EMBER) ## Regenerate the dataset card (evals/dataset/card.json + CARD.md)
	$(PY) -m evals.dataset.card

audit-sources: ## Re-check every data-source register row online (before a dataset publication)
	python3 scripts/audit_data_sources.py

mcp-check: $(EMBER) ## MCP protocol end-to-end check
	$(PY) -u scripts/test_mcp_client.py

smoke: $(EMBER) ## Direct MPS inference smoke test
	$(PY) -u scripts/smoke_mps.py

MAMBA ?= micromamba
CONDA_ENV ?= ember-smoke

UNAME_S := $(shell uname -s)
UNAME_M := $(shell uname -m)
ifeq ($(UNAME_S)-$(UNAME_M),Darwin-arm64)
CONDA_PLATFORM ?= osx-arm64
else ifeq ($(UNAME_S)-$(UNAME_M),Linux-x86_64)
CONDA_PLATFORM ?= linux-64
else
CONDA_PLATFORM ?= unsupported
endif

# The install prefers conda-forge (canonical) and falls back to the interim joshburt channel
# until the feedstock publishes ember-advise; conda-forge then wins on channel priority with no
# change here. Drop `-c joshburt` at conda-forge onboarding.
conda-smoke: ## No-model conda smoke for VERSION=<v>: explicit lock env via micromamba + ember-advise + CLI/doctor/torch-free import
	@test "$(CONDA_PLATFORM)" != "unsupported" || { printf "error: set CONDA_PLATFORM to osx-arm64 or linux-64\n"; exit 1; }
	$(MAMBA) create -y -n $(CONDA_ENV) -f conda-$(CONDA_PLATFORM).lock
	$(MAMBA) install -y -n $(CONDA_ENV) -c conda-forge -c joshburt "ember-advise==$(VERSION)"
	$(MAMBA) run -n $(CONDA_ENV) ember --help
	$(MAMBA) run -n $(CONDA_ENV) gut --help
	$(MAMBA) run -n $(CONDA_ENV) ember-advise --help
	$(MAMBA) run -n $(CONDA_ENV) python -c "import shutil, sys; missing = [c for c in ('ember', 'gut', 'ember-advise', 'ember-mcp') if not shutil.which(c)]; sys.exit(f'missing entry points: {missing}') if missing else None"
	$(MAMBA) run -n $(CONDA_ENV) ember doctor
	$(MAMBA) run -n $(CONDA_ENV) python -c "import sys, ember.mcp.mcp_server; assert 'torch' not in sys.modules"
