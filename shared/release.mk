# shared/release.mk — setup, bootstrap, release, and cleanup targets
# Assumes UV, PY, EMBER, MODEL_DIR, and EMBER_* vars are defined in the root Makefile.

.PHONY: download init opencode setup bootstrap check ci clean clean-model release-dry release-ember deployment-requirements deploy undeploy

download: $(EMBER) ## Download pinned Clef-Flash weights (~18 GB) to .models/
	$(PY) -c "from huggingface_hub import snapshot_download; from ember.models import get; spec = get('flash'); snapshot_download(spec.repo, revision=spec.revision, local_dir='$(MODEL_DIR)')"

init: $(EMBER) ## Regenerate opencode.json with this clone's absolute paths (idempotent)
	$(EMBER) init

opencode: $(EMBER) ## Install local opencode plugin and ember-advise skill
	$(EMBER) init --opencode

setup: sync ## First-time setup: deps only (no model weights; see `make download`)

bootstrap: setup download init doctor ## Full first-run: deps + weights + MCP config + readiness

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

release-dry: ## Preview the next ember version bump without making changes
	$(PY) -m commitizen bump --dry-run

release-ember: ## Trigger the ember release workflow on main (bump PR → GitHub Release → PyPI)
	gh workflow run release-ember.yml --ref main

deployment-requirements: $(EMBER) ## Regenerate deployment/requirements.txt from uv.lock (run before every Outerbounds deploy)
	$(UV) export --format requirements.txt --no-dev --no-editable --no-hashes --no-emit-project -o deployment/requirements.txt
	$(PY) scripts/freeze_deployment_requirements.py

deploy: deployment-requirements ## Deploy ember to Outerbounds (validates deploy.yaml is filled in first)
	@if grep -q "<CONFIRM-" deployment/deploy.yaml; then \
		printf "error: deployment/deploy.yaml still has unresolved <CONFIRM-...> placeholders:\n"; \
		grep -n "<CONFIRM-" deployment/deploy.yaml; \
		exit 1; \
	fi
	$(UV) run outerbounds app deploy \
		--config-file deployment/deploy.yaml \
		--package-src-path . \
		--readiness-condition async

undeploy: ## Delete the ember deployment from Outerbounds (set EMBER_FORCE=1 to skip the prompt)
	@if [ "$(EMBER_FORCE)" != "1" ]; then \
		printf "This will delete the 'ember' app deployment from Outerbounds. Set EMBER_FORCE=1 to skip this prompt.\n"; \
		printf "Continue? [y/N] "; \
		read ans; \
		[ "$$ans" = "y" ] || [ "$$ans" = "Y" ] || { printf "Aborted.\n"; exit 1; }; \
	fi
	$(UV) run outerbounds app delete --name ember --auto-approve
