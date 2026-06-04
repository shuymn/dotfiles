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
local: ## Generate local Nix host config from chezmoi data
	@mkdir -p "$(dir $(NIX_LOCAL_CONFIG))"
	@$(CHEZMOI_TEMPLATE_ENV) $(CHEZMOI_CMD) execute-template < "$(NIX_LOCAL_TEMPLATE)" > "$(NIX_LOCAL_CONFIG)"

.PHONY: check
check: local ## Check the Nix flake
	@$(NIX_LOCAL_ENV) $(NIX_CMD) flake check --impure "$(NIX_LOCAL_FLAKE)"

.PHONY: check-brew
check-brew: local ## Check Homebrew against the nix-darwin generated Brewfile
	@tmpfile="$$(mktemp "$${TMPDIR:-/tmp}/dotfiles-brewfile.XXXXXX")"; \
	trap 'rm -f "$$tmpfile"' EXIT; \
	$(NIX_LOCAL_ENV) $(NIX_CMD) eval --impure --raw "$(NIX_LOCAL_FLAKE)#darwinConfigurations.$(DARWIN_CONFIG).config.homebrew.brewfile" > "$$tmpfile"; \
	$(BREW) bundle check --file="$$tmpfile"

.PHONY: audit-cli-path
audit-cli-path: ## Classify non-Nix/non-mise PATH owners and shadows
	@zsh -lc 'emulate -L zsh; setopt null_glob; \
		owner() { \
			case "$$1" in \
				$$HOME/.local/share/mise/shims/*|$$HOME/.local/share/mise/installs/*) print mise ;; \
				/etc/profiles/per-user/*/bin/*|/run/current-system/sw/bin/*|/nix/var/nix/profiles/default/bin/*|$$HOME/.nix-profile/bin/*) print nix ;; \
				/opt/homebrew/bin/*|/opt/homebrew/sbin/*|/usr/local/bin/*|/usr/local/sbin/*|/home/linuxbrew/.linuxbrew/bin/*|/home/linuxbrew/.linuxbrew/sbin/*) print brew ;; \
				/usr/bin/*|/bin/*|/usr/sbin/*|/sbin/*) print system ;; \
				*) print unmanaged ;; \
			esac; \
		}; \
		needs_attention() { [[ "$$1" = brew || "$$1" = unmanaged ]]; }; \
		typeset -A seen; \
		for dir in $$path; do \
			[[ -d "$$dir" ]] || continue; \
			for file in "$$dir"/*; do \
				[[ -f "$$file" && -x "$$file" ]] || continue; \
				cmd="$${file:t}"; \
				[[ -n "$${seen[$$cmd]}" ]] && continue; \
				seen[$$cmd]=1; \
				paths=($$(whence -a -p "$$cmd" 2>/dev/null)); \
				[[ $${#paths[@]} -gt 0 ]] || continue; \
				first="$${paths[1]}"; \
				first_owner=$$(owner "$$first"); \
				needs_attention "$$first_owner" && printf "%s\tfirst=%s\t%s\n" "$$cmd" "$$first_owner" "$$first"; \
				for p in "$${paths[@]}"; do \
					[[ "$$p" = "$$first" ]] && continue; \
					p_owner=$$(owner "$$p"); \
					[[ "$$p_owner" = "$$first_owner" ]] && continue; \
					needs_attention "$$p_owner" && printf "%s\tshadow=%s\t%s\n" "$$cmd" "$$p_owner" "$$p"; \
				done; \
			done; \
		done | sort'

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
