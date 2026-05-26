<!-- Do not restructure or delete sections. Update inline when behavior changes. -->

# AGENTS.md

## Repo-Specific Rules

- Edit skills directly under `etc/claude/skills/**`; there is no separate `skills/` source tree.
- After changing skills, check for whitespace/conflict markers with `git diff --check -- etc/claude/skills`, then run `make sync-skills` to install them.
- Use `make link-claude` when you need to refresh `~/.claude/**` symlinks from this repo.
- Treat `README.md` as user-facing setup docs; keep this file limited to agent-only repository rules.

<!-- Maintenance: Update this file when skill source/build ownership or Claude sync workflow changes. -->
