DOTPATH    := $(realpath $(dir $(lastword $(MAKEFILE_LIST))))
CANDIDATES := $(wildcard .??*)
EXCLUSIONS := .DS_Store .git .gitmodules .gitignore .Brewfile .prettierrc.json .claude .vscode .editorconfig .tmux.conf .claude-plugin
DOTFILES := $(filter-out $(EXCLUSIONS), $(CANDIDATES))

CLAUDE_BASE := etc/claude
CLAUDE_HOME := $(HOME)/.claude
CLAUDE_EXCLUSIONS := $(CLAUDE_BASE)/hooks/hooks.json
CLAUDE_CANDIDATES := $(shell find $(CLAUDE_BASE) -type f 2>/dev/null)
CLAUDE_FILES := $(filter-out $(CLAUDE_EXCLUSIONS), $(CLAUDE_CANDIDATES))
CLAUDE_TARGETS := $(patsubst $(CLAUDE_BASE)/%,$(CLAUDE_HOME)/%,$(CLAUDE_FILES))

CODEX_BASE := $(CLAUDE_BASE)/skills
CODEX_HOME := $(HOME)/.codex/skills
CODEX_FILES := $(shell find $(CODEX_BASE) -type f 2>/dev/null)
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
link-claude: ## Create symlinks to the claude directory
	@echo 'Start to link claude files'
	@echo ''
	@$(foreach file,$(CLAUDE_FILES), \
		mkdir -p $(dir $(patsubst etc/claude/%,$(CLAUDE_HOME)/%,$(file))) && \
		ln -sfnv $(abspath $(file)) $(patsubst etc/claude/%,$(CLAUDE_HOME)/%,$(file));)
	@echo 'Finish linking claude files'

.PHONY: link-codex
link-codex: ## Copy codex skill files and AGENTS.md to the codex directory
	@echo 'Start to link codex files'
	@echo ''
	@$(foreach file,$(CODEX_FILES), \
		mkdir -p $(dir $(patsubst $(CODEX_BASE)/%,$(CODEX_HOME)/%,$(file))) && \
		rm -f $(patsubst $(CODEX_BASE)/%,$(CODEX_HOME)/%,$(file)) && \
		cp -fv $(abspath $(file)) $(patsubst $(CODEX_BASE)/%,$(CODEX_HOME)/%,$(file));)
	@mkdir -p $(dir $(CODEX_AGENTS_TARGET))
	@cp -fv $(abspath $(CODEX_AGENTS_SOURCE)) $(CODEX_AGENTS_TARGET)
	@echo 'Finish linking codex files'

.PHONY: clean-claude
clean-claude: ## Remove symlinks from the claude directory
	@echo 'Start to remove claude symlinks'
	@echo ''
	@$(foreach target,$(CLAUDE_TARGETS),rm -iv $(target);)
	@echo 'Finish removing claude symlinks'
