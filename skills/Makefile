PROJECT_ROOT := $(realpath $(dir $(lastword $(MAKEFILE_LIST))))
SOURCE_ROOT := $(abspath $(PROJECT_ROOT)/src)
ARTIFACT_ROOT := $(abspath $(PROJECT_ROOT)/../etc/claude/skills)
MANIFEST_PATH := $(ARTIFACT_ROOT)/.dotfiles-managed-skills.json
SKITKIT_BIN := $(PROJECT_ROOT)/tools/skit/skitkit
SKILLS_MARKER := .dotfiles-managed
SKILLS_CMD := bunx --bun skills
SKILLS_AGENTS := codex claude-code
AGENTS_SKILLS_HOME := $(HOME)/.agents/skills
CODEX_SKILLS_HOME := $(HOME)/.codex/skills
CODEX_AGENTS_SOURCE := $(abspath $(PROJECT_ROOT)/../etc/claude/CLAUDE.md)
CODEX_AGENTS_TARGET := $(HOME)/.codex/AGENTS.md

.DEFAULT_GOAL := help

.PHONY: help
help: ## Self-documented Makefile
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| sort \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

.PHONY: build
build: ## Build standalone skills artifacts into ../etc/claude/skills
	@$(MAKE) -C $(PROJECT_ROOT)/tools/skit build
	@printf '\n[skills-sync] step=build start\n'
	@$(SKITKIT_BIN) build-skills \
		--source "$(SOURCE_ROOT)" \
		--artifact "$(ARTIFACT_ROOT)"
	@printf '[skills-sync] step=build done\n'

.PHONY: test
test: ## Run Go tests for skit
	@$(MAKE) -C $(PROJECT_ROOT)/tools/skit test

.PHONY: install
install: ## Install built managed skills via skills CLI
	@printf '\n[skills-sync] step=install start\n'
	@printf '[skills-sync] note=bunx-skills-output-uncontrolled\n'
	@$(SKILLS_CMD) add "$(ARTIFACT_ROOT)" -g -y $(foreach agent,$(SKILLS_AGENTS),-a $(agent)) --skill '*'
	@$(SKITKIT_BIN) mark-managed \
		--manifest "$(MANIFEST_PATH)" \
		--agents-skills "$(AGENTS_SKILLS_HOME)" \
		--marker "$(SKILLS_MARKER)"
	@printf '[skills-sync] step=install done\n'

.PHONY: reconcile
reconcile: ## Remove stale managed skills while preserving external skills
	@printf '\n[skills-sync] step=reconcile start\n'
	@$(SKITKIT_BIN) reconcile \
		--manifest "$(MANIFEST_PATH)" \
		--agents-skills "$(AGENTS_SKILLS_HOME)" \
		--marker "$(SKILLS_MARKER)" \
		--skills-cmd "$(SKILLS_CMD)"
	@printf '[skills-sync] step=reconcile done\n'

.PHONY: list-managed
list-managed: ## Print the generated skills manifest
	@cat "$(MANIFEST_PATH)"

.PHONY: audit-codex
audit-codex: ## Audit ~/.codex/skills and prune duplicates found in ~/.agents/skills
	@printf '\n[skills-sync] step=codex-audit start\n'
	@$(SKITKIT_BIN) audit-codex \
		--manifest "$(MANIFEST_PATH)" \
		--agents-skills "$(AGENTS_SKILLS_HOME)" \
		--codex-skills "$(CODEX_SKILLS_HOME)" \
		--marker "$(SKILLS_MARKER)" \
		--prune-duplicates
	@printf '[skills-sync] step=codex-audit done\n'

.PHONY: codex-agents-md
codex-agents-md: ## Sync ../etc/claude/CLAUDE.md to ~/.codex/AGENTS.md
	@printf '\n[skills-sync] step=codex-agents-md start\n'
	@mkdir -p $(dir $(CODEX_AGENTS_TARGET))
	@cp -fv "$(CODEX_AGENTS_SOURCE)" "$(CODEX_AGENTS_TARGET)"
	@printf '[skills-sync] step=codex-agents-md done\n'

.PHONY: sync
sync: build install reconcile audit-codex codex-agents-md ## Build and install skills plus Codex sync
	@printf '\n[skills-sync] result=success\n'
