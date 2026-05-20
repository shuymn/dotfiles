# pi agent extensions handoff

This directory is the dotfiles-managed source of truth for pi agent resources.

## Purpose

Keep global pi extensions reproducible from this repository instead of leaving one-off files under `~/.pi/agent/extensions`. A fresh machine or later agent session should be able to restore the same extension setup with:

```bash
make link-pi
```

`make link-pi` symlinks managed pi runtime files under `etc/pi/**` into `~/.pi/**` with matching paths. Documentation files in this directory are for handoff only and should not be linked into `~/.pi`.

## Extension ownership rule

When adding or changing global pi extensions:

1. Edit files under `etc/pi/agent/extensions/**`.
2. Install or refresh extension tooling when dependencies changed:
   ```bash
   bun install --cwd etc/pi/agent/extensions
   ```
3. Run the shared checks. `check` runs Biome formatting and lint diagnostics:
   ```bash
   bun run --cwd etc/pi/agent/extensions check
   bun run --cwd etc/pi/agent/extensions typecheck
   bun test --cwd etc/pi/agent/extensions
   ```
4. Link managed files:
   ```bash
   make link-pi
   ```
5. In a running pi session, use `/reload` to pick up changes.

Do not make long-lived manual edits directly under `~/.pi/agent/extensions/**`. If you find an unmanaged global extension there, copy it into `etc/pi/agent/extensions/`, then run `make link-pi` so the global file becomes a symlink back to this repo.

## Migrating an unmanaged global extension

Example:

```bash
mkdir -p etc/pi/agent/extensions/example
cp ~/.pi/agent/extensions/example.ts etc/pi/agent/extensions/example/index.ts
make link-pi
ls -l ~/.pi/agent/extensions/example/index.ts
bun run --cwd etc/pi/agent/extensions check
```

Expected result:

```text
~/.pi/agent/extensions/example/index.ts -> ~/.dotfiles/etc/pi/agent/extensions/example/index.ts
```

## Design notes

- Prefer interactive TUI selection over free-form flags when options are mutually exclusive or should be chosen from live project state, such as language, create/update mode, and branch/base selection.
- Keep long agent-facing workflow instructions in adjacent Markdown files when that makes TypeScript entrypoints easier to maintain.
- Branch selection should filter remote HEAD refs carefully. `refs/remotes/origin/HEAD` may render as `origin` with `%(refname:short)`, so code should inspect full `%(refname)` and exclude refs ending in `/HEAD`.
- Do not add static file inventories to this README. They drift quickly; use `find etc/pi -type f` when you need the current list.
