# shared/vault.mk — project vault (Obsidian notes under vault/)
# Assumes PY and EMBER are defined in the root Makefile.

.PHONY: vault-audit

vault-audit: $(EMBER) ## Audit vault/: frontmatter, tags, wikilinks, code-refs, orphans
	$(PY) scripts/vault_audit.py vault
