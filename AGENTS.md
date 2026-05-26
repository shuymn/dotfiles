<!-- Do not restructure or delete sections. Update inline when behavior changes. -->

# AGENTS.md

## Repo-Specific Rules

- Edit skill sources under `skills/src/**`; do not edit generated artifacts under `etc/claude/skills/**`.
- There is no `make -C skills build` target; after changing skill sources, validate with `git diff --check -- skills/src` and use `make -C skills sync` only when installing the current artifact tree.
- Use `make link-claude` when you need to refresh `~/.claude/**` symlinks from this repo.
- Treat `README.md` as user-facing setup docs; keep this file limited to agent-only repository rules.

<!-- Maintenance: Update this file when skill source/build ownership or Claude sync workflow changes. -->
