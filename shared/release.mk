# shared/release.mk — setup, bootstrap, release, and cleanup targets
# Assumes UV, PY, EMBER, MODEL_DIR, and EMBER_* vars are defined in the root Makefile.

.PHONY: download init opencode setup bootstrap check ci clean clean-model

download: $(EMBER) ## Download pinned Clef-Flash weights (~18 GB) to .models/
	$(PY) -c "from huggingface_hub import snapshot_download; from ember.models import get; spec = get('flash'); snapshot_download(spec.repo, revision=spec.revision, local_dir='$(MODEL_DIR)')"

init: $(EMBER) ## Regenerate opencode.json with this clone's absolute paths (idempotent)
	$(EMBER) init

opencode: $(EMBER) ## Install local opencode plugin and ember-advise skill
	$(EMBER) init --opencode

setup: sync download ## First-time setup: deps + model weights

bootstrap: setup init doctor ## Full first-run: deps + weights + MCP config + readiness

check: compile test-fast ## Fast pre-commit gate (compile + unit tests, no model)

ci: bootstrap check test-strict ## Full non-interactive gate (bootstrap + check + strict tests)

clean: ## Remove caches and build output (keeps .venv and .models)
	find . -type d -name __pycache__ -not -path './.venv/*' -exec rm -rf {} +
	rm -rf .pytest_cache dist

clean-model: ## Delete downloaded model weights
	@if [ "$(EMBER_FORCE)" != "1" ]; then \
		printf "This will delete $(MODEL_DIR). Set EMBER_FORCE=1 to skip this prompt.\n"; \
		printf "Continue? [y/N] "; \
		read ans; \
		[ "$$ans" = "y" ] || [ "$$ans" = "Y" ] || { printf "Aborted.\n"; exit 1; }; \
	fi
	rm -rf $(MODEL_DIR)
