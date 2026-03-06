DOTPATH    := $(realpath $(dir $(lastword $(MAKEFILE_LIST))))
CANDIDATES := $(wildcard .??*)
EXCLUSIONS := .DS_Store .git .gitmodules .gitignore .Brewfile .prettierrc.json .claude .vscode .editorconfig .tmux.conf .claude-plugin
DOTFILES := $(filter-out $(EXCLUSIONS), $(CANDIDATES))

CLAUDE_BASE := etc/claude
CLAUDE_HOME := $(HOME)/.claude
CLAUDE_EXCLUSIONS := $(CLAUDE_BASE)/hooks/hooks.json $(CLAUDE_BASE)/skills/%
CLAUDE_CANDIDATES := $(shell find $(CLAUDE_BASE) -type f 2>/dev/null)
CLAUDE_FILES := $(filter-out $(CLAUDE_EXCLUSIONS), $(CLAUDE_CANDIDATES))
CLAUDE_TARGETS := $(patsubst $(CLAUDE_BASE)/%,$(CLAUDE_HOME)/%,$(CLAUDE_FILES))

SKILLS_SOURCE := $(abspath skills)
SKILLS_ARTIFACT := $(abspath $(CLAUDE_BASE)/skills)
SKILLS_MANIFEST := $(SKILLS_ARTIFACT)/.dotfiles-managed-skills.json
SKILLS_MARKER := .dotfiles-managed
SKILLS_CMD := bunx --bun skills
SKILLS_AGENTS := codex claude-code
AGENTS_SKILLS_HOME := $(HOME)/.agents/skills
CODEX_SKILLS_HOME := $(HOME)/.codex/skills

CODEX_AGENTS_SOURCE := $(CLAUDE_BASE)/CLAUDE.md
CODEX_AGENTS_TARGET := $(HOME)/.codex/AGENTS.md

.DEFAULT_GOAL := help

.PHONY: list
list: ## Show dotfiles in this repository
	@echo 'List dotfiles'
	@echo ''
	@$(foreach val, $(DOTFILES), /bin/ls -dF $(val);)

.PHONY: link
link: ## Create symlinks to the directory
	@echo 'Start to link dotfiles'
	@echo ''
	@$(foreach val, $(DOTFILES), ln -sfnv $(abspath $(val)) $(HOME)/$(val);)

.PHONY: clean
clean: ## Remove the dotfiles and this repository
	@echo 'Remove the dotfiles'
	@-$(foreach val, $(DOTFILES), rm -vrf $(HOME)/$(val);)
	-rm -rf $(DOTPATH)

.PHONY: start-bash-lsp
start-bash-lsp: ## for VSCode
	@docker container run --name explainshell --rm -p 5000:5000 spaceinvaderone/explainshell

.PHONY: help
help: ## Self-documented Makefile
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| sort \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'

.PHONY: link-claude
link-claude: ## Create symlinks to the claude directory (excluding skills)
	@echo 'Start to link claude files'
	@echo ''
	@$(foreach file,$(CLAUDE_FILES), \
		mkdir -p $(dir $(patsubst etc/claude/%,$(CLAUDE_HOME)/%,$(file))) && \
		ln -sfnv $(abspath $(file)) $(patsubst etc/claude/%,$(CLAUDE_HOME)/%,$(file));)
	@echo 'Finish linking claude files'

.PHONY: skills-build
skills-build: ## Build standalone skills artifacts into etc/claude/skills
	@printf '\n[skills-sync] step=build start\n'
	@uv run python scripts/skills/build_skills.py \
		--source "$(SKILLS_SOURCE)" \
		--artifact "$(SKILLS_ARTIFACT)"
	@printf '[skills-sync] step=build done\n'

.PHONY: skills-test
skills-test: ## Run pytest against skills source and build validations
	@printf '\n[skills-sync] step=test start\n'
	@uv run --group dev pytest skills
	@printf '[skills-sync] step=test done\n'

.PHONY: skills-install
skills-install: ## Install built managed skills via skills CLI
	@printf '\n[skills-sync] step=install start\n'
	@printf '[skills-sync] note=bunx-skills-output-uncontrolled\n'
	@$(SKILLS_CMD) add "$(SKILLS_ARTIFACT)" -g -y $(foreach agent,$(SKILLS_AGENTS),-a $(agent)) --skill '*'
	@uv run python scripts/skills/skills_mark_managed.py \
		--manifest "$(SKILLS_MANIFEST)" \
		--agents-skills "$(AGENTS_SKILLS_HOME)" \
		--marker "$(SKILLS_MARKER)"
	@printf '[skills-sync] step=install done\n'

.PHONY: skills-reconcile
skills-reconcile: ## Remove stale managed skills while preserving external skills
	@printf '\n[skills-sync] step=reconcile start\n'
	@uv run python scripts/skills/skills_reconcile.py \
		--manifest "$(SKILLS_MANIFEST)" \
		--agents-skills "$(AGENTS_SKILLS_HOME)" \
		--marker "$(SKILLS_MARKER)" \
		--skills-cmd "$(SKILLS_CMD)"
	@printf '[skills-sync] step=reconcile done\n'

.PHONY: skills-list-managed
skills-list-managed: ## Print the generated skills manifest
	@cat "$(SKILLS_MANIFEST)"

.PHONY: skills-audit-codex
skills-audit-codex: ## Audit ~/.codex/skills and prune duplicates found in ~/.agents/skills
	@printf '\n[skills-sync] step=codex-audit start\n'
	@uv run python scripts/skills/audit_codex_skills.py \
		--manifest "$(SKILLS_MANIFEST)" \
		--agents-skills "$(AGENTS_SKILLS_HOME)" \
		--codex-skills "$(CODEX_SKILLS_HOME)" \
		--marker "$(SKILLS_MARKER)" \
		--prune-duplicates
	@printf '[skills-sync] step=codex-audit done\n'

.PHONY: skills-sync
skills-sync: skills-build skills-install skills-reconcile skills-audit-codex ## Build, sync, prune codex duplicates, and sync Codex AGENTS.md
	@printf '\n[skills-sync] step=codex-agents-md start\n'
	@mkdir -p $(dir $(CODEX_AGENTS_TARGET))
	@cp -fv $(abspath $(CODEX_AGENTS_SOURCE)) $(CODEX_AGENTS_TARGET)
	@printf '[skills-sync] step=codex-agents-md done\n'
	@printf '\n[skills-sync] result=success\n'

.PHONY: clean-claude
clean-claude: ## Remove symlinks from the claude directory (excluding skills)
	@echo 'Start to remove claude symlinks (excluding skills)'
	@echo ''
	@$(foreach target,$(CLAUDE_TARGETS),rm -iv $(target);)
	@echo 'Finish removing claude symlinks'
