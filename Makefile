DOTPATH := $(realpath $(dir $(lastword $(MAKEFILE_LIST))))

CHEZMOI ?= chezmoi
CHEZMOI_STATE_DIR ?= $(HOME)/.local/state/chezmoi
CHEZMOI_STATE ?= $(CHEZMOI_STATE_DIR)/chezmoistate.boltdb
NIX ?= nix
NIX_FLAGS ?= --extra-experimental-features nix-command --extra-experimental-features flakes
NIX_CMD := $(NIX) $(NIX_FLAGS)
CHEZMOI_BOOTSTRAP ?= $(NIX_CMD) shell nixpkgs\#chezmoi -c chezmoi
CHEZMOI_RUN := $(shell command -v $(CHEZMOI) >/dev/null 2>&1 && printf '%s' '$(CHEZMOI)' || printf '%s' '$(CHEZMOI_BOOTSTRAP)')
CHEZMOI_CMD := $(CHEZMOI_RUN) --source=$(DOTPATH) --persistent-state=$(CHEZMOI_STATE)

NIX_LOCAL_FLAKE := path:$(DOTPATH)
NIX_LOCAL_CONFIG ?= $(DOTPATH)/nix/local.nix
NIX_LOCAL_TEMPLATE ?= $(DOTPATH)/nix/local.nix.tmpl
NIX_LOCAL_ENV := DOTFILES_NIX_LOCAL=$(NIX_LOCAL_CONFIG)
DARWIN_CONFIG ?= default
SUDO ?= sudo

CLAUDE_BASE := etc/claude
CLAUDE_HOME := $(HOME)/.claude
CLAUDE_EXCLUSIONS := $(CLAUDE_BASE)/hooks/hooks.json $(CLAUDE_BASE)/skills/%
CLAUDE_CANDIDATES := $(shell find $(CLAUDE_BASE) -type f 2>/dev/null)
CLAUDE_FILES := $(filter-out $(CLAUDE_EXCLUSIONS), $(CLAUDE_CANDIDATES))

SKILLS_ROOT := $(abspath $(CLAUDE_BASE)/skills)
SKILLS_CMD := bunx --bun skills
SKILLS_AGENTS := codex claude-code
CODEX_AGENTS_SOURCE := $(abspath $(CLAUDE_BASE)/CLAUDE.md)
CODEX_AGENTS_TARGET := $(HOME)/.codex/AGENTS.md

PI_BASE := etc/pi
PI_HOME := $(HOME)/.pi
PI_EXTENSIONS_PROJECT ?= $(HOME)/ghq/github.com/shuymn/pi-extensions
PI_CANDIDATES := $(shell find $(PI_BASE) -type f -print 2>/dev/null)

MISE ?= mise

.DEFAULT_GOAL := help

.PHONY: help
help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| sort \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-16s\033[0m %s\n", $$1, $$2}'

.PHONY: install-nix
install-nix: ## Install Nix if missing
	@if command -v $(NIX) >/dev/null 2>&1; then \
		$(NIX) --version; \
	else \
		curl -sSfL https://artifacts.nixos.org/nix-installer | sh -s -- install --enable-flakes; \
	fi

.PHONY: local
local:
	@$(CHEZMOI_CMD) execute-template < "$(NIX_LOCAL_TEMPLATE)" > "$(NIX_LOCAL_CONFIG)"

.PHONY: check
check: local ## Check the Nix flake
	@$(NIX_LOCAL_ENV) $(NIX_CMD) flake check --impure "$(NIX_LOCAL_FLAKE)"

.PHONY: build
build: local ## Build the nix-darwin profile without switching
	@$(NIX_LOCAL_ENV) $(NIX_CMD) build --impure --no-link "$(NIX_LOCAL_FLAKE)#darwinConfigurations.$(DARWIN_CONFIG).system"

.PHONY: switch
switch: local ## Apply nix-darwin and Home Manager
	@$(SUDO) env HOME=/var/root PATH="$$PATH" $(NIX_LOCAL_ENV) $(NIX_CMD) run --impure "$(NIX_LOCAL_FLAKE)#darwin-rebuild" -- switch --flake "$(NIX_LOCAL_FLAKE)#$(DARWIN_CONFIG)" --impure

.PHONY: gc
gc: ## Delete old Nix generations and garbage collect the store
	@nix-collect-garbage -d
	@$(SUDO) nix-collect-garbage -d

.PHONY: apply
apply: ## Apply chezmoi dotfile links
	@mkdir -p "$(CHEZMOI_STATE_DIR)"
	@$(CHEZMOI_CMD) apply

.PHONY: mise
mise: ## Install mise-managed global tools
	@$(MISE) install -C "$(HOME)"

.PHONY: agents
agents: link-claude sync-skills link-pi ## Link and sync agent files

.PHONY: link-claude
link-claude:
	@$(foreach file,$(CLAUDE_FILES), \
		mkdir -p $(dir $(patsubst etc/claude/%,$(CLAUDE_HOME)/%,$(file))) && \
		ln -sfn $(abspath $(file)) $(patsubst etc/claude/%,$(CLAUDE_HOME)/%,$(file));)

.PHONY: sync-skills
sync-skills:
	@$(SKILLS_CMD) add "$(SKILLS_ROOT)" -g -y $(foreach agent,$(SKILLS_AGENTS),-a $(agent)) --skill '*'
	@mkdir -p $(dir $(CODEX_AGENTS_TARGET))
	@cp -f "$(CODEX_AGENTS_SOURCE)" "$(CODEX_AGENTS_TARGET)"

.PHONY: link-pi
link-pi:
	@if [ -d "$(PI_HOME)" ]; then \
		find "$(PI_HOME)" -type l -print | while IFS= read -r link; do \
			target=$$(readlink "$$link"); \
			case "$$target" in \
				$(abspath $(PI_BASE))/*) \
					rel=$${target#$(abspath $(PI_BASE))/}; \
					source="$(PI_BASE)/$$rel"; \
					case " $(PI_CANDIDATES) " in *" $$source "*) ;; *) rm -f "$$link" ;; esac; \
					;; \
			esac; \
		done; \
	fi
	@$(foreach file,$(PI_CANDIDATES), \
		mkdir -p $(dir $(patsubst etc/pi/%,$(PI_HOME)/%,$(file))) && \
		ln -sfn $(abspath $(file)) $(patsubst etc/pi/%,$(PI_HOME)/%,$(file));)
	@if [ -d "$(PI_EXTENSIONS_PROJECT)" ]; then \
		pi install "$(PI_EXTENSIONS_PROJECT)" >/dev/null; \
	else \
		echo "Skip pi-extensions package install: $(PI_EXTENSIONS_PROJECT) not found"; \
	fi
	@mkdir -p $(PI_HOME)/agent
	@ln -sfn $(abspath $(CLAUDE_BASE)/CLAUDE.md) $(PI_HOME)/agent/AGENTS.md
