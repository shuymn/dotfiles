DOTPATH := $(realpath $(dir $(lastword $(MAKEFILE_LIST))))

CHEZMOI ?= chezmoi
CHEZMOI_STATE_DIR ?= $(HOME)/.local/state/chezmoi
CHEZMOI_STATE ?= $(CHEZMOI_STATE_DIR)/chezmoistate.boltdb
CHEZMOI_CONFIG ?= $(HOME)/.config/chezmoi/chezmoi.toml
CHEZMOI_CONFIG_TEMPLATE ?= $(DOTPATH)/.chezmoi.toml.tmpl
AGE_KEY ?= $(HOME)/.config/age/key.txt
# path: includes the git-ignored host.toml, which a git+file flake would not see.
NIX_LOCAL_FLAKE := path:$(DOTPATH)
HOST_CONFIG := $(DOTPATH)/host.toml
ROLE ?= minimal
NIX ?= nix
MISE ?= $(NIX_CMD) run "$(NIX_LOCAL_FLAKE)\#mise" --
NIX_FLAGS ?= --extra-experimental-features nix-command --extra-experimental-features flakes
NIX_CMD := $(NIX) $(NIX_FLAGS)
CHEZMOI_BOOTSTRAP ?= $(NIX_CMD) shell nixpkgs\#chezmoi -c chezmoi
CHEZMOI_RUN := $(shell command -v $(CHEZMOI) >/dev/null 2>&1 && printf '%s' '$(CHEZMOI)' || printf '%s' '$(CHEZMOI_BOOTSTRAP)')
CHEZMOI_CMD := $(CHEZMOI_RUN) --source=$(DOTPATH) --persistent-state=$(CHEZMOI_STATE)

DARWIN_CONFIG ?= default
SUDO ?= sudo
BREW ?= $(shell if command -v brew >/dev/null 2>&1; then command -v brew; elif [ -x /opt/homebrew/bin/brew ]; then printf '%s' /opt/homebrew/bin/brew; elif [ -x /usr/local/bin/brew ]; then printf '%s' /usr/local/bin/brew; else printf '%s' brew; fi)

PI_EXTENSIONS_PROJECT ?= $(HOME)/ghq/github.com/shuymn/pi-extensions

.DEFAULT_GOAL := help

.PHONY: help
help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| sort \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

.PHONY: install-nix
install-nix: ## Install Nix if missing
	@if command -v $(NIX) >/dev/null 2>&1; then \
		$(NIX) --version; \
	else \
		curl -sSfL https://artifacts.nixos.org/nix-installer | sh -s -- install --enable-flakes; \
	fi

.PHONY: host
host: ## Create the git-ignored host.toml from this machine (ROLE=minimal|personal-lite|personal|work)
	@/bin/sh "$(DOTPATH)/scripts/init-host.sh" "$(HOST_CONFIG)" "$(DOTPATH)/nix/roles.toml" "$(ROLE)"

.PHONY: require-host
require-host:
	@if [ ! -f "$(HOST_CONFIG)" ]; then \
		echo "$(HOST_CONFIG) not found; run 'make host ROLE=<role>' first" >&2; \
		exit 1; \
	fi

.PHONY: check-ownership
check-ownership: ## Check Home Manager does not claim dotfile targets
	@matches="$$(find nix -name '*.nix' -print0 \
		| xargs -0 grep -nE 'home[.]file|home[.]activation|xdg[.](configFile|dataFile|stateFile|cacheFile)' 2>/dev/null || true)"; \
	if [ -n "$$matches" ]; then \
		printf '%s\n' "$$matches" >&2; \
		echo "Home Manager must not manage dotfile targets. Keep target files under home/** or migrate ownership fully." >&2; \
		exit 1; \
	fi

.PHONY: check-source-state
check-source-state: ## Check chezmoi source state does not include local-only targets
	@/bin/sh "$(DOTPATH)/scripts/check-source-state.sh"

.PHONY: check
check: check-ownership check-source-state ## Check source state, dotfile ownership, and the Nix flake
	@$(NIX_CMD) flake check "$(NIX_LOCAL_FLAKE)"

.PHONY: check-fpr
FPR_SHELL_SOURCES := home/dot_local/private_bin/executable_fpr \
	home/dot_local/share/forgejo-review/scripts/executable_bootstrap.sh
check-fpr: ## Check the fpr shell scripts and focused tests
	@shfmt -d -i 2 -ci -sr $(FPR_SHELL_SOURCES)
	@shellcheck -s sh $(FPR_SHELL_SOURCES)
	@python3 -m unittest -v tests.test_fpr

.PHONY: check-brew
check-brew: require-host ## Check Homebrew against the nix-darwin generated Brewfile
	@tmpfile="$$(mktemp "$${TMPDIR:-/tmp}/dotfiles-brewfile.XXXXXX")"; \
	trap 'rm -f "$$tmpfile"' EXIT; \
	$(NIX_CMD) eval --raw "$(NIX_LOCAL_FLAKE)#darwinConfigurations.$(DARWIN_CONFIG).config.homebrew.brewfile" > "$$tmpfile"; \
	$(BREW) bundle check --file="$$tmpfile"; \
	BREW="$(BREW)" /bin/sh "$(DOTPATH)/scripts/check-homebrew-state.sh" "$$tmpfile"

.PHONY: check-mise-updates
check-mise-updates: ## List pending mise tool updates and check every tool has release timestamps
	@$(NIX_CMD) shell "$(NIX_LOCAL_FLAKE)#mise" -c python3 "$(DOTPATH)/scripts/update-mise-tools.py" --dry-run --config "$(DOTPATH)/home/dot_config/mise/config.toml"

.PHONY: audit-cli-path
audit-cli-path: ## Classify non-Nix/non-mise PATH owners and shadows
	@zsh -lc 'source "$(DOTPATH)/scripts/audit-cli-path.zsh"'

.PHONY: build
build: require-host ## Build the nix-darwin profile without switching
	@$(NIX_CMD) build --no-link "$(NIX_LOCAL_FLAKE)#darwinConfigurations.$(DARWIN_CONFIG).system"

.PHONY: switch
switch: require-host ## Apply nix-darwin and Home Manager
	@$(SUDO) env HOME=/var/root PATH="$$PATH" $(NIX_CMD) run "$(NIX_LOCAL_FLAKE)#darwin-rebuild" -- switch --flake "$(NIX_LOCAL_FLAKE)#$(DARWIN_CONFIG)"

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
	@$(MAKE) chezmoi-config

.PHONY: chezmoi-config
chezmoi-config: ## Generate chezmoi config for plain chezmoi commands
	@mkdir -p "$(CHEZMOI_STATE_DIR)" "$(dir $(CHEZMOI_CONFIG))"
	@$(CHEZMOI_CMD) execute-template < "$(CHEZMOI_CONFIG_TEMPLATE)" > "$(CHEZMOI_CONFIG)"

.PHONY: apply
apply: chezmoi-config ## Apply chezmoi-managed dotfiles
	@$(CHEZMOI_CMD) apply

.PHONY: mise
mise: ## Install mise-managed global tools
	@MISE_LOCKED=1 $(MISE) install -C "$(HOME)"

.PHONY: install-pi
install-pi: ## Install the local pi extensions package when present
	@if [ -d "$(PI_EXTENSIONS_PROJECT)" ]; then \
		pi install "$(PI_EXTENSIONS_PROJECT)" >/dev/null; \
	else \
		echo "Skip pi-extensions package install: $(PI_EXTENSIONS_PROJECT) not found"; \
	fi
