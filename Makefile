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

SKILLS_SOURCE := $(abspath $(CLAUDE_BASE)/skills)
SKILLS_MANIFEST := $(SKILLS_SOURCE)/.dotfiles-managed-skills.json
SKILLS_MARKER := .dotfiles-managed
SKILLS_CMD := bunx --bun skills
SKILLS_AGENTS := codex claude-code
AGENTS_SKILLS_HOME := $(HOME)/.agents/skills
CODEX_SKILLS_HOME := $(HOME)/.codex/skills

CODEX_AGENTS_SOURCE := $(CLAUDE_BASE)/CLAUDE.md
CODEX_AGENTS_TARGET := $(HOME)/.codex/AGENTS.md
DOTFILES_MANAGED_MIRROR := $(HOME)/.agents/.dotfiles-managed-skills.json

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

.PHONY: skills-manifest-refresh
skills-manifest-refresh: ## Refresh the managed skills manifest in dotfiles
	@printf '\n[skills-sync] step=manifest-refresh start\n'
	@uv run python scripts/skills/skills_manifest_refresh.py \
		--source "$(SKILLS_SOURCE)" \
		--manifest "$(SKILLS_MANIFEST)"
	@printf '[skills-sync] step=manifest-refresh done\n'

.PHONY: skills-install
skills-install: ## Install managed skills via skills CLI
	@printf '\n[skills-sync] step=install start\n'
	@printf '[skills-sync] note=bunx-skills-output-uncontrolled\n'
	@$(SKILLS_CMD) add "$(SKILLS_SOURCE)" -g -y $(foreach agent,$(SKILLS_AGENTS),-a $(agent)) --skill '*'
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

.PHONY: skills-sync-shared
skills-sync-shared: ## Sync shared skills assets to ~/.agents
	@printf '\n[skills-sync] step=sync-shared start\n'
	@uv run python scripts/skills/sync_shared.py \
		--source "$(SKILLS_SOURCE)/_shared" \
		--destination "$(AGENTS_SKILLS_HOME)/_shared" \
		--delete
	@printf '[skills-sync] step=sync-shared done\n'

.PHONY: skills-list-managed
skills-list-managed: ## Print the managed skills manifest
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
skills-sync: skills-manifest-refresh skills-install skills-reconcile skills-sync-shared skills-audit-codex ## Sync managed skills, prune codex duplicates, and sync Codex AGENTS.md
	@printf '\n[skills-sync] step=codex-agents-md start\n'
	@mkdir -p $(dir $(CODEX_AGENTS_TARGET))
	@cp -fv $(abspath $(CODEX_AGENTS_SOURCE)) $(CODEX_AGENTS_TARGET)
	@mkdir -p $(dir $(DOTFILES_MANAGED_MIRROR))
	@cp -fv "$(SKILLS_MANIFEST)" "$(DOTFILES_MANAGED_MIRROR)"
	@printf '[skills-sync] step=codex-agents-md done\n'
	@printf '\n[skills-sync] result=success\n'

.PHONY: clean-claude
clean-claude: ## Remove symlinks from the claude directory (excluding skills)
	@echo 'Start to remove claude symlinks (excluding skills)'
	@echo ''
	@$(foreach target,$(CLAUDE_TARGETS),rm -iv $(target);)
	@echo 'Finish removing claude symlinks'
