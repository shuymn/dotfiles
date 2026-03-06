PROJECT_ROOT := $(realpath $(dir $(lastword $(MAKEFILE_LIST))))
SOURCE_ROOT := $(abspath $(PROJECT_ROOT)/src)
ARTIFACT_ROOT := $(abspath $(PROJECT_ROOT)/../etc/claude/skills)
MANIFEST_PATH := $(ARTIFACT_ROOT)/.dotfiles-managed-skills.json
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
	@printf '\n[skills-sync] step=build start\n'
	@uv run python scripts/build_skills.py \
		--source "$(SOURCE_ROOT)" \
		--artifact "$(ARTIFACT_ROOT)"
	@printf '[skills-sync] step=build done\n'

.PHONY: test
test: ## Run pytest against src/ and tests/
	@printf '\n[skills-sync] step=test start\n'
	@uv run --group dev pytest
	@printf '[skills-sync] step=test done\n'

.PHONY: fmt
fmt: ## Format Python files under src/, tests/, and scripts/
	@printf '\n[skills-sync] step=fmt start\n'
	@uv run --group dev ruff check --select I --fix src tests scripts
	@uv run --group dev ruff format src tests scripts
	@printf '[skills-sync] step=fmt done\n'

.PHONY: lint
lint: ## Lint Python files under src/, tests/, and scripts/
	@printf '\n[skills-sync] step=lint start\n'
	@uv run --group dev ruff check src tests scripts
	@printf '[skills-sync] step=lint done\n'

.PHONY: install
install: ## Install built managed skills via skills CLI
	@printf '\n[skills-sync] step=install start\n'
	@printf '[skills-sync] note=bunx-skills-output-uncontrolled\n'
	@$(SKILLS_CMD) add "$(ARTIFACT_ROOT)" -g -y $(foreach agent,$(SKILLS_AGENTS),-a $(agent)) --skill '*'
	@uv run python scripts/skills_mark_managed.py \
		--manifest "$(MANIFEST_PATH)" \
		--agents-skills "$(AGENTS_SKILLS_HOME)" \
		--marker "$(SKILLS_MARKER)"
	@printf '[skills-sync] step=install done\n'

.PHONY: reconcile
reconcile: ## Remove stale managed skills while preserving external skills
	@printf '\n[skills-sync] step=reconcile start\n'
	@uv run python scripts/skills_reconcile.py \
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
	@uv run python scripts/audit_codex_skills.py \
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

.PHONY: build-skit
build-skit: ## Build skit Go binary into tools/skit/
	@printf '\n[skills-sync] step=build-skit start\n'
	@cd $(PROJECT_ROOT)/tools/skit && go build -o skit .
	@printf '[skills-sync] step=build-skit done\n'

.PHONY: sync
sync: build install reconcile audit-codex codex-agents-md ## Build and install skills plus Codex sync
	@printf '\n[skills-sync] result=success\n'
