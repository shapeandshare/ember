# shared/server.mk — model server and MCP lifecycle targets
# Assumes GF is defined in the root Makefile (venv-installed gut-feeling entrypoint).

.PHONY: serve start stop restart status logs mcp mcp-list doctor

serve: ## Run model server in foreground (Ctrl-C to stop)
	$(GF) serve

start: ## Start model server in background
	$(GF) start

stop: ## Stop the background model server
	$(GF) stop

restart: ## Restart background model server
	$(GF) restart

status: ## Show server health (exit 1 when stopped)
	$(GF) status

logs: ## Follow the model server log
	$(GF) logs

mcp: ## Run MCP stdio server in foreground (debug)
	$(GF) mcp

mcp-list: ## List opencode-configured MCP servers
	opencode mcp list

doctor: ## Check platform, deps, model, server readiness
	$(GF) doctor
