# shared/aws.mk — AWS GPU deployment targets
# Assumes UV, REPO_ROOT, and EMBER are defined in the root Makefile.
# Run with: PYTHONPATH=deployment/aws uv run python -m ember_aws <cmd>

NAME          ?= default
REGION        ?= us-west-2
MODEL         ?= flash
INSTANCE_TYPE ?=
CAPACITY      ?= on-demand
IDLE_MINUTES  ?= 0
EMBER_VERSION ?=
AWS_CLI        = PYTHONPATH=deployment/aws $(UV) run python -m ember_aws

.PHONY: aws-preflight aws-cache aws-cache-list aws-cache-rm aws-cache-destroy \
        aws-up aws-status aws-stop aws-start aws-replace aws-logs aws-ssh \
        aws-token aws-rotate-token aws-down aws-verify aws-tools aws-tools-rm

aws-preflight: $(EMBER) ## Check AWS identity, quota, Tailscale, and model cache readiness
	$(AWS_CLI) preflight \
	  --name $(NAME) --region $(REGION) --model $(MODEL) \
	  $(if $(INSTANCE_TYPE),--instance-type $(INSTANCE_TYPE),)

aws-cache: $(EMBER) ## Create the S3 model cache stack (if absent) and upload the pinned model
	$(AWS_CLI) cache add \
	  --model $(MODEL) --region $(REGION)

aws-cache-list: $(EMBER) ## List cached models, revisions, sizes, and which deployments use each
	$(AWS_CLI) cache list --region $(REGION)

aws-cache-rm: $(EMBER) ## Remove one cached model (exit 3 while a deployment uses it)
	$(AWS_CLI) cache rm \
	  --model $(MODEL) --region $(REGION)

aws-cache-destroy: $(EMBER) ## Delete the cache bucket — requires --confirm <bucket-name> and no deployments
	$(AWS_CLI) cache destroy \
	  --confirm $(CONFIRM) --region $(REGION)

aws-up: $(EMBER) ## Deploy (or update) the ember GPU instance and wait for health
	$(AWS_CLI) deploy \
	  --name $(NAME) --region $(REGION) --model $(MODEL) \
	  $(if $(INSTANCE_TYPE),--instance-type $(INSTANCE_TYPE),) \
	  --capacity $(CAPACITY) \
	  --idle-minutes $(IDLE_MINUTES) \
	  $(if $(EMBER_VERSION),--ember-version $(EMBER_VERSION),)

aws-status: $(EMBER) ## Show deployment state, instance, URL, health, and cost estimate
	$(AWS_CLI) status \
	  --name $(NAME) --region $(REGION)

aws-stop: $(EMBER) ## Stop the EC2 instance and wait for stopped state
	$(AWS_CLI) stop \
	  --name $(NAME) --region $(REGION)

aws-start: $(EMBER) ## Start the instance and wait for health
	$(AWS_CLI) start \
	  --name $(NAME) --region $(REGION)

aws-replace: $(EMBER) ## Replace the instance with the latest DLAMI and wait for health
	$(AWS_CLI) replace \
	  --name $(NAME) --region $(REGION)

aws-logs: $(EMBER) ## Stream instance logs via Tailscale SSH (--unit ember|converge|idle|tailscale)
	$(AWS_CLI) logs \
	  --name $(NAME) \
	  $(if $(UNIT),--unit $(UNIT),) \
	  $(if $(FOLLOW),--follow,)

aws-ssh: $(EMBER) ## Open a Tailscale SSH shell on the instance
	$(AWS_CLI) ssh \
	  --name $(NAME)

aws-token: $(EMBER) ## Print the server auth token (for export EMBER_AUTH_TOKEN="$(make -s aws-token)")
	$(AWS_CLI) token \
	  --name $(NAME) --region $(REGION)

aws-rotate-token: $(EMBER) ## Generate a new server token and reboot the instance
	$(AWS_CLI) rotate-token \
	  --name $(NAME) --region $(REGION)

aws-down: $(EMBER) ## Destroy the deployment — pass CONFIRM=<name> (keeps the cache)
	@test -n "$(CONFIRM)" || (echo "Usage: make aws-down CONFIRM=<deployment-name>"; exit 3)
	$(AWS_CLI) destroy \
	  --name $(NAME) --region $(REGION) --confirm $(CONFIRM)

aws-verify: $(EMBER) ## Run the CUDA verification gate over Tailscale SSH and benchmark from here
	$(AWS_CLI) verify \
	  --name $(NAME) --region $(REGION)

aws-tools: ## Install the tailscale CLI if not already present (idempotent; records installs in .aws-tools.installed)
	@if command -v tailscale >/dev/null 2>&1; then \
	  echo "tailscale: already installed"; \
	else \
	  if uname -s | grep -q Darwin; then \
	    brew install --cask tailscale && \
	    grep -qxF tailscale .aws-tools.installed 2>/dev/null || echo "tailscale" >> .aws-tools.installed && \
	    echo "tailscale: installed via brew"; \
	  else \
	    echo "tailscale: install from https://tailscale.com/download/linux"; \
	  fi; \
	fi

aws-tools-rm: ## Remove only the tools listed in .aws-tools.installed
	@if [ ! -f .aws-tools.installed ]; then echo "nothing to remove (.aws-tools.installed absent)"; exit 0; fi
	@while IFS= read -r tool; do \
	  if [ -z "$$tool" ]; then continue; fi; \
	  echo "removing $$tool"; \
	  if uname -s | grep -q Darwin; then \
	    brew uninstall --cask "$$tool" 2>/dev/null || echo "$$tool: not installed via brew, skipping"; \
	  else \
	    echo "$$tool: manual removal required on Linux"; \
	  fi; \
	done < .aws-tools.installed
	@rm -f .aws-tools.installed
	@echo "aws-tools-rm: done"
