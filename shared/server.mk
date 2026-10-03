# shared/server.mk — model server and MCP lifecycle targets
# Assumes EMBER is defined in the root Makefile (venv-installed ember entrypoint).

.PHONY: serve start stop restart status logs mcp mcp-list doctor

serve: ## Run model server in foreground (Ctrl-C to stop)
	$(EMBER) serve

start: ## Start model server in background
	$(EMBER) start

stop: ## Stop the background model server
	$(EMBER) stop

restart: ## Restart background model server
	$(EMBER) restart

status: ## Show server health (exit 1 when stopped)
	$(EMBER) status

logs: ## Follow the model server log
	$(EMBER) logs

mcp: ## Run MCP stdio server in foreground (debug)
	$(EMBER) mcp

mcp-list: ## List opencode-configured MCP servers
	opencode mcp list

doctor: ## Check platform, deps, model, server readiness
	$(EMBER) doctor
