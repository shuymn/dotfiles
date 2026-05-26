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

SKILLS_ROOT := $(abspath $(CLAUDE_BASE)/skills)
SKILLS_CMD := bunx --bun skills
SKILLS_AGENTS := codex claude-code
CODEX_AGENTS_SOURCE := $(abspath $(CLAUDE_BASE)/CLAUDE.md)
CODEX_AGENTS_TARGET := $(HOME)/.codex/AGENTS.md
PI_BASE := etc/pi
PI_HOME := $(HOME)/.pi
PI_EXTENSIONS_PROJECT ?= $(HOME)/ghq/github.com/shuymn/pi-extensions
PI_CANDIDATES := $(shell find $(PI_BASE) -type f -print 2>/dev/null)
PI_TARGETS := $(patsubst $(PI_BASE)/%,$(PI_HOME)/%,$(PI_CANDIDATES))

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

.PHONY: link-pi
link-pi: ## Create symlinks to the pi agent directory
	@echo 'Start to link pi files'
	@echo ''
	@if [ -d "$(PI_HOME)" ]; then \
		find "$(PI_HOME)" -type l -print | while IFS= read -r link; do \
			target=$$(readlink "$$link"); \
			case "$$target" in \
				$(abspath $(PI_BASE))/*) \
					rel=$${target#$(abspath $(PI_BASE))/}; \
					source="$(PI_BASE)/$$rel"; \
					case " $(PI_CANDIDATES) " in *" $$source "*) ;; *) rm -v "$$link" ;; esac; \
					;; \
			esac; \
		done; \
	fi
	@$(foreach file,$(PI_CANDIDATES), \
		mkdir -p $(dir $(patsubst etc/pi/%,$(PI_HOME)/%,$(file))) && \
		ln -sfnv $(abspath $(file)) $(patsubst etc/pi/%,$(PI_HOME)/%,$(file));)
	@if [ -d "$(PI_EXTENSIONS_PROJECT)" ]; then \
		pi install "$(PI_EXTENSIONS_PROJECT)" >/dev/null; \
	else \
		echo "Skip pi-extensions package install: $(PI_EXTENSIONS_PROJECT) not found"; \
	fi
	@mkdir -p $(PI_HOME)/agent
	@ln -sfnv $(abspath $(CLAUDE_BASE)/CLAUDE.md) $(PI_HOME)/agent/AGENTS.md
	@echo 'Finish linking pi files'

.PHONY: sync-skills
sync-skills: ## Install skills and sync Codex AGENTS.md
	@printf '\n[skills-sync] step=install start\n'
	@$(SKILLS_CMD) add "$(SKILLS_ROOT)" -g -y $(foreach agent,$(SKILLS_AGENTS),-a $(agent)) --skill '*'
	@printf '[skills-sync] step=install done\n'
	@printf '\n[skills-sync] step=codex-agents-md start\n'
	@mkdir -p $(dir $(CODEX_AGENTS_TARGET))
	@cp -fv "$(CODEX_AGENTS_SOURCE)" "$(CODEX_AGENTS_TARGET)"
	@printf '[skills-sync] step=codex-agents-md done\n'
	@printf '\n[skills-sync] result=success\n'

.PHONY: clean-claude
clean-claude: ## Remove symlinks from the claude directory (excluding skills)
	@echo 'Start to remove claude symlinks (excluding skills)'
	@echo ''
	@$(foreach target,$(CLAUDE_TARGETS),rm -iv $(target);)
	@echo 'Finish removing claude symlinks'
