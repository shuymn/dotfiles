DOTPATH    := $(realpath $(dir $(lastword $(MAKEFILE_LIST))))
CANDIDATES := $(wildcard .??*)
EXCLUSIONS := .DS_Store .git .gitmodules .gitignore .Brewfile .prettierrc.json .claude .vscode
DOTFILES := $(filter-out $(EXCLUSIONS), $(CANDIDATES))

CLAUDE_HOME := $(HOME)/.claude
CLAUDE_FILES := $(shell find etc/claude -type f 2>/dev/null)
CLAUDE_TARGETS := $(patsubst etc/claude/%,$(CLAUDE_HOME)/%,$(CLAUDE_FILES))

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
	@$(foreach file,$(CLAUDE_FILES),ln -sfnv $(abspath $(file)) $(patsubst etc/claude/%,$(CLAUDE_HOME)/%,$(file));)
	@echo 'Finish linking claude files'

.PHONY: clean-claude
clean-claude: ## Remove symlinks from the claude directory
	@echo 'Start to remove claude symlinks'
	@echo ''
	@$(foreach target,$(CLAUDE_TARGETS),rm -iv $(target);)
	@echo 'Finish removing claude symlinks'
