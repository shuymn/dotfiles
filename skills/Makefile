PROJECT_ROOT := $(realpath $(dir $(lastword $(MAKEFILE_LIST))))
ARTIFACT_ROOT := $(abspath $(PROJECT_ROOT)/../etc/claude/skills)
SKILLS_CMD := bunx --bun skills
SKILLS_AGENTS := codex claude-code
CODEX_AGENTS_SOURCE := $(abspath $(PROJECT_ROOT)/../etc/claude/CLAUDE.md)
CODEX_AGENTS_TARGET := $(HOME)/.codex/AGENTS.md

.DEFAULT_GOAL := help

.PHONY: help
help: ## Self-documented Makefile
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| sort \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

.PHONY: install
install: ## Install skills from ../etc/claude/skills via skills CLI
	@printf '\n[skills-sync] step=install start\n'
	@$(SKILLS_CMD) add "$(ARTIFACT_ROOT)" -g -y $(foreach agent,$(SKILLS_AGENTS),-a $(agent)) --skill '*'
	@printf '[skills-sync] step=install done\n'

.PHONY: codex-agents-md
codex-agents-md: ## Sync ../etc/claude/CLAUDE.md to ~/.codex/AGENTS.md
	@printf '\n[skills-sync] step=codex-agents-md start\n'
	@mkdir -p $(dir $(CODEX_AGENTS_TARGET))
	@cp -fv "$(CODEX_AGENTS_SOURCE)" "$(CODEX_AGENTS_TARGET)"
	@printf '[skills-sync] step=codex-agents-md done\n'

.PHONY: sync
sync: install codex-agents-md ## Install skills and sync AGENTS.md
	@printf '\n[skills-sync] result=success\n'
