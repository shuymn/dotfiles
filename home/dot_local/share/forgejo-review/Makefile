SHELL := /bin/sh
ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
COMPOSE := docker compose --project-directory $(ROOT) -f $(ROOT)/compose.yaml
FORGEJO_URL ?= http://127.0.0.1:3000
OPEN ?= $(shell if command -v open >/dev/null 2>&1; then printf open; else printf xdg-open; fi)

.DEFAULT_GOAL := help

.PHONY: help
help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| sort \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-12s\033[0m %s\n", $$1, $$2}'

.PHONY: config
config: ## Render and validate the Compose configuration
	@$(COMPOSE) config --quiet

.PHONY: up
up: config ## Start Forgejo on localhost only
	@$(COMPOSE) up -d
	@$(MAKE) wait

.PHONY: wait
wait: ## Wait until the Forgejo HTTP server responds
	@printf 'Waiting for %s ...\n' "$(FORGEJO_URL)"; \
	attempt=0; \
	until curl --disable --noproxy '*' --silent --show-error --fail --max-time 2 "$(FORGEJO_URL)/" >/dev/null 2>&1; do \
		attempt=$$((attempt + 1)); \
		if [ $$attempt -ge 60 ]; then echo 'Forgejo did not become ready.' >&2; exit 1; fi; \
		sleep 1; \
	done; \
	if $(COMPOSE) exec -T --user git forgejo forgejo admin user list >/dev/null 2>&1; then \
		echo 'Forgejo is installed and ready.'; \
	else \
		echo 'Forgejo is ready for first-run setup.'; \
	fi

.PHONY: open
open: ## Open the Forgejo web interface
	@$(OPEN) "$(FORGEJO_URL)"

.PHONY: bootstrap
bootstrap: ## Create fpr-agent credentials (REVIEWER=<human-login>)
	@test -n "$(REVIEWER)" || { echo 'Usage: make bootstrap REVIEWER=<human-login>' >&2; exit 2; }
	@"$(ROOT)/scripts/bootstrap.sh" "$(REVIEWER)"

.PHONY: status
status: ## Show container and Forgejo API status
	@$(COMPOSE) ps
	@if $(COMPOSE) exec -T --user git forgejo forgejo admin user list >/dev/null 2>&1; then \
		echo 'Forgejo is installed and ready (API access requires authentication).'; \
	elif curl --disable --noproxy '*' --silent --show-error --fail "$(FORGEJO_URL)/" >/dev/null 2>&1; then \
		echo 'Forgejo HTTP is ready; first-run setup is pending.'; \
	else \
		echo 'Forgejo HTTP is unavailable.' >&2; exit 1; \
	fi

.PHONY: logs
logs: ## Follow Forgejo logs
	@$(COMPOSE) logs --follow --tail=100

.PHONY: down
down: ## Stop Forgejo without deleting persistent data
	@$(COMPOSE) down
