# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with this repository.

<!-- Do not restructure or delete sections. Update inline when behavior changes. -->

## Commands

```bash
make build          # go build -ldflags "...BinaryName=skit ...CommandSet=authoring" -o skit . && go build -ldflags "...BinaryName=skitkit ...CommandSet=admin" -o skitkit .
make test           # go test -race -count=10 -shuffle=on ./...

go test -race -count=1 ./cmd/...   # single package
```

## Architecture

`skit` and `skitkit` are minimal Go CLIs with no external deps. `internal/cli/` is a custom framework.
`cmd/` stays as thin exported wrappers; workflow checks live in `internal/workflow/`, managed skill sync lives in `internal/managedskills/`, and build pipeline logic lives in `internal/skillbuild/`, all grouped by `internal/apps/` into authoring (`skit`) and admin (`skitkit`) command sets selected at build time via `-ldflags`.

**Template system:** `.md.tmpl` + sibling `.fragments.json` → rendered `.md`.
Three supported types in `internal/template/spec.go` (`design-templates`, `plan-templates`, `trace-templates`),
each mapping to a model in `internal/model/`.

## Conventions

- `cmd/` functions: `flag.NewFlagSet(name, flag.ContinueOnError)`; `Run` returns `int` exit code
- Validation errors: typed sentinel errors via private constructors (`buildErr()`, `renderError()`)
- `model` fields: `strings.TrimSpace` before emptiness check

<!-- Maintenance: Review when adding subcommands or changing the template system. -->
