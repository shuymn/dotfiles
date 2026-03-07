.DEFAULT_GOAL := help

GO ?= $(if $(GOROOT),$(GOROOT)/bin/go,$(shell command -v go))
APP_CONFIG_PKG := github.com/shuymn/dotfiles/skills/tools/skit/internal/apps
SKIT_LDFLAGS := -X $(APP_CONFIG_PKG).BinaryName=skit -X $(APP_CONFIG_PKG).CommandSet=authoring
SKITKIT_LDFLAGS := -X $(APP_CONFIG_PKG).BinaryName=skitkit -X $(APP_CONFIG_PKG).CommandSet=admin

.PHONY: help
help: ## Self-documented Makefile
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| sort \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

.PHONY: build
build: ## Build skit and skitkit Go binaries
	"$(GO)" build -ldflags "$(SKIT_LDFLAGS)" -o skit .
	"$(GO)" build -ldflags "$(SKITKIT_LDFLAGS)" -o skitkit .

.PHONY: test
test: ## Run Go tests
	"$(GO)" test -race -count=10 -shuffle=on ./...
