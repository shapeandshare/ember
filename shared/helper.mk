# shared/helper.mk — help target and ANSI color definitions
# Included by the root Makefile; defines .DEFAULT_GOAL and color vars only.

# ---------------------------------------------------------------------------
# ANSI colors
# ---------------------------------------------------------------------------
RESET  := \033[0m
CYAN   := \033[36m
GREEN  := \033[32m
YELLOW := \033[33m

# ---------------------------------------------------------------------------
# Default goal
# ---------------------------------------------------------------------------
.DEFAULT_GOAL := help

# ---------------------------------------------------------------------------
# Targets
# ---------------------------------------------------------------------------
.PHONY: help

help: ## Show this help
	@printf "$(CYAN)gut-feeling — make targets$(RESET)\n\n"
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@printf "\n$(YELLOW)env:$(RESET)  host=$(GUT_FEELING_HOST)  port=$(GUT_FEELING_PORT)  device=$(GUT_FEELING_DEVICE)\n"
