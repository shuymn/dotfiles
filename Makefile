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

SKILLS_PROJECT := $(abspath skills)

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
	@$(MAKE) -C "$(SKILLS_PROJECT)" build

.PHONY: skills-test
skills-test: ## Run pytest against skills source and build validations
	@$(MAKE) -C "$(SKILLS_PROJECT)" test

.PHONY: skills-fmt
skills-fmt: ## Format Python files in the standalone skills project
	@$(MAKE) -C "$(SKILLS_PROJECT)" fmt

.PHONY: skills-lint
skills-lint: ## Lint Python files in the standalone skills project
	@$(MAKE) -C "$(SKILLS_PROJECT)" lint

.PHONY: skills-install
skills-install: ## Install built managed skills via skills CLI
	@$(MAKE) -C "$(SKILLS_PROJECT)" install

.PHONY: skills-reconcile
skills-reconcile: ## Remove stale managed skills while preserving external skills
	@$(MAKE) -C "$(SKILLS_PROJECT)" reconcile

.PHONY: skills-list-managed
skills-list-managed: ## Print the generated skills manifest
	@$(MAKE) -C "$(SKILLS_PROJECT)" list-managed

.PHONY: skills-audit-codex
skills-audit-codex: ## Audit ~/.codex/skills and prune duplicates found in ~/.agents/skills
	@$(MAKE) -C "$(SKILLS_PROJECT)" audit-codex

.PHONY: skills-sync
skills-sync: ## Build, sync, prune codex duplicates, and sync Codex AGENTS.md
	@$(MAKE) -C "$(SKILLS_PROJECT)" sync

.PHONY: clean-claude
clean-claude: ## Remove symlinks from the claude directory (excluding skills)
	@echo 'Start to remove claude symlinks (excluding skills)'
	@echo ''
	@$(foreach target,$(CLAUDE_TARGETS),rm -iv $(target);)
	@echo 'Finish removing claude symlinks'
