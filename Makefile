DOTPATH := $(realpath $(dir $(lastword $(MAKEFILE_LIST))))

CHEZMOI ?= chezmoi
CHEZMOI_STATE_DIR ?= $(HOME)/.local/state/chezmoi
CHEZMOI_STATE ?= $(CHEZMOI_STATE_DIR)/chezmoistate.boltdb
CHEZMOI_CONFIG ?= $(HOME)/.config/chezmoi/chezmoi.toml
CHEZMOI_CONFIG_TEMPLATE ?= $(DOTPATH)/.chezmoi.toml.tmpl
AGE_KEY ?= $(HOME)/.config/age/key.txt
NIX_LOCAL_FLAKE := path:$(DOTPATH)
NIX_LOCAL_CONFIG ?= $(DOTPATH)/nix/local.nix
NIX_LOCAL_TEMPLATE ?= $(DOTPATH)/nix/local.nix.tmpl
NIX_ROLE ?=
NIX_LOCAL_ENV := DOTFILES_NIX_LOCAL=$(NIX_LOCAL_CONFIG)
CHEZMOI_TEMPLATE_ENV := $(if $(NIX_ROLE),DOTFILES_NIX_ROLE=$(NIX_ROLE),)
NIX ?= nix
NIX_FLAGS ?= --extra-experimental-features nix-command --extra-experimental-features flakes
NIX_CMD := $(NIX) $(NIX_FLAGS)
CHEZMOI_BOOTSTRAP ?= $(NIX_CMD) shell nixpkgs\#chezmoi -c chezmoi
CHEZMOI_RUN := $(shell command -v $(CHEZMOI) >/dev/null 2>&1 && printf '%s' '$(CHEZMOI)' || printf '%s' '$(CHEZMOI_BOOTSTRAP)')
CHEZMOI_CMD := $(CHEZMOI_RUN) --source=$(DOTPATH) --persistent-state=$(CHEZMOI_STATE)

DARWIN_CONFIG ?= default
SUDO ?= sudo
BREW ?= $(shell if command -v brew >/dev/null 2>&1; then command -v brew; elif [ -x /opt/homebrew/bin/brew ]; then printf '%s' /opt/homebrew/bin/brew; elif [ -x /usr/local/bin/brew ]; then printf '%s' /usr/local/bin/brew; else printf '%s' brew; fi)

CLAUDE_BASE := etc/claude
MISE ?= mise
SKILLS_ROOT := $(abspath $(CLAUDE_BASE)/skills)
SKILLS_CMD := $(MISE) exec -- skills
SKILLS_AGENTS := codex claude-code

PI_EXTENSIONS_PROJECT ?= $(HOME)/ghq/github.com/shuymn/pi-extensions

AGENT_CHEZMOI_TARGETS := \
	$(HOME)/.claude/CLAUDE.md \
	$(HOME)/.claude/statusline.sh \
	$(HOME)/.codex/AGENTS.md \
	$(HOME)/.pi/agent/AGENTS.md \
	$(HOME)/.pi/agent/keybindings.json

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
local: ## Generate local Nix host config from chezmoi data
	@mkdir -p "$(dir $(NIX_LOCAL_CONFIG))"
	@$(CHEZMOI_TEMPLATE_ENV) $(CHEZMOI_CMD) execute-template < "$(NIX_LOCAL_TEMPLATE)" > "$(NIX_LOCAL_CONFIG)"

.PHONY: check-ownership
check-ownership: ## Check Home Manager does not claim dotfile targets
	@matches="$$(find nix -name '*.nix' -print0 \
		| xargs -0 grep -nE 'home[.]file|home[.]activation|xdg[.](configFile|dataFile|stateFile|cacheFile)' 2>/dev/null || true)"; \
	if [ -n "$$matches" ]; then \
		printf '%s\n' "$$matches" >&2; \
		echo "Home Manager must not manage dotfile targets. Keep target files under home/** or migrate ownership fully." >&2; \
		exit 1; \
	fi

.PHONY: check
check: check-ownership local ## Check the Nix flake
	@$(NIX_LOCAL_ENV) $(NIX_CMD) flake check --impure "$(NIX_LOCAL_FLAKE)"

.PHONY: check-brew
check-brew: local ## Check Homebrew against the nix-darwin generated Brewfile
	@tmpfile="$$(mktemp "$${TMPDIR:-/tmp}/dotfiles-brewfile.XXXXXX")"; \
	trap 'rm -f "$$tmpfile"' EXIT; \
	$(NIX_LOCAL_ENV) $(NIX_CMD) eval --impure --raw "$(NIX_LOCAL_FLAKE)#darwinConfigurations.$(DARWIN_CONFIG).config.homebrew.brewfile" > "$$tmpfile"; \
	$(BREW) bundle check --file="$$tmpfile"

.PHONY: audit-cli-path
audit-cli-path: ## Classify non-Nix/non-mise PATH owners and shadows
	@zsh -lc 'source "$(DOTPATH)/scripts/audit-cli-path.zsh"'

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

.PHONY: age-key
age-key: ## Generate local age identity for chezmoi encryption
	@if [ -e "$(AGE_KEY)" ]; then \
		echo "$(AGE_KEY) already exists"; \
	else \
		mkdir -p "$(dir $(AGE_KEY))"; \
		umask 077; \
		if command -v age-keygen >/dev/null 2>&1; then \
			age-keygen -o "$(AGE_KEY)"; \
		else \
			$(NIX_CMD) shell nixpkgs\#age -c age-keygen -o "$(AGE_KEY)"; \
		fi; \
	fi
	@$(MAKE) chezmoi-config NIX_ROLE="$(NIX_ROLE)"

.PHONY: chezmoi-config
chezmoi-config: ## Generate chezmoi config for plain chezmoi commands
	@mkdir -p "$(CHEZMOI_STATE_DIR)" "$(dir $(CHEZMOI_CONFIG))"
	@$(CHEZMOI_TEMPLATE_ENV) $(CHEZMOI_CMD) execute-template < "$(CHEZMOI_CONFIG_TEMPLATE)" > "$(CHEZMOI_CONFIG)"

.PHONY: apply
apply: chezmoi-config ## Apply chezmoi-managed dotfiles
	@$(CHEZMOI_CMD) apply

.PHONY: mise
mise: ## Install mise-managed global tools
	@$(MISE) install -C "$(HOME)"

.PHONY: agents
agents: agent-dotfiles sync-skills install-pi ## Apply agent dotfiles and runtime syncs

.PHONY: agent-dotfiles
agent-dotfiles: chezmoi-config ## Apply only static agent dotfiles
	@$(CHEZMOI_CMD) apply $(foreach target,$(AGENT_CHEZMOI_TARGETS),"$(target)")

.PHONY: sync-skills
sync-skills: ## Install repo-owned skills into configured agent runtimes
	@$(SKILLS_CMD) add "$(SKILLS_ROOT)" -g -y $(foreach agent,$(SKILLS_AGENTS),-a $(agent)) --skill '*'

.PHONY: install-pi
install-pi: ## Install the local pi extensions package when present
	@if [ -d "$(PI_EXTENSIONS_PROJECT)" ]; then \
		pi install "$(PI_EXTENSIONS_PROJECT)" >/dev/null; \
	else \
		echo "Skip pi-extensions package install: $(PI_EXTENSIONS_PROJECT) not found"; \
	fi
