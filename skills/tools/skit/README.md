# skit / skitkit

Go-based CLIs for skill authoring checks and managed skill sync operations.

## Binaries

- `skit`
  - Authoring and review helper CLI used directly from skills such as `design-doc`, `decompose-plan`, and `execute-plan`.
  - Exposes check/report commands like `gate-check`, `split-check`, `review-finalize`, and related validation utilities.
- `skitkit`
  - Admin CLI for building artifacts and reconciling installed managed skills.
  - Exposes `build-skills`, `manifest-refresh`, `mark-managed`, `reconcile`, and `audit-codex`.

## Commands

- `make build`
  - Build both `skit` and `skitkit` from the same `main` package using build-time `-ldflags`.
- `make test`
  - Run Go tests for the shared module and both build-time variants.

## Notes

- `skills/Makefile` uses `skitkit` for the build/install/reconcile/audit pipeline.
- `skit` intentionally does not provide the sync/admin commands.
- `cmd/` is kept thin on purpose; workflow logic lives in `internal/workflow/`, managed skill sync logic in `internal/managedskills/`, and artifact build logic in `internal/skillbuild/`.
