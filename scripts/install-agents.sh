#!/bin/sh
# Install the shared agent skills and Claude Code plugins that are missing.
# Installed ones are left alone, so updates stay manual (`skills update -g`,
# `claude plugin update`). Run through `make agents`, which puts the mise tools
# (skills, claude) on PATH.
set -eu

agents_dir="$HOME/.agents/skills"
claude_dir="$HOME/.claude/skills"

# install_skills <source> <name>...: install the named skills that lack the
# shared copy or the Claude Code link, for Claude Code, Codex, and pi.
install_skills() {
	source=$1
	shift
	missing=
	for name in "$@"; do
		if [ ! -e "$agents_dir/$name" ]; then
			missing="$missing $name"
		elif [ ! -e "$claude_dir/$name" ]; then
			# Relink locally; reinstalling would replace the shared copy.
			mkdir -p "$claude_dir"
			ln -s "../../.agents/skills/$name" "$claude_dir/$name"
		fi
	done
	[ -n "$missing" ] || return 0
	# shellcheck disable=SC2086 # $missing is a word list
	skills add -g "$source" -s $missing -a claude-code codex pi -y
	for name in $missing; do
		if [ ! -e "$agents_dir/$name" ] || [ ! -e "$claude_dir/$name" ]; then
			echo "install-agents: $name from $source is still missing" >&2
			exit 1
		fi
	done
}

install_skills shuymn/skills \
	adversarial-verify commit create-pr extensible-by-design github-clone-workspace \
	goal-loop-engineering proofread prune-tests simplify triage-review
install_skills mattpocock/skills codebase-design domain-modeling grilling tdd writing-for-agents
install_skills GoogleChrome/modern-web-guidance modern-web-guidance
install_skills cloudflare/security-audit-skill security-audit

marketplaces=$(claude plugin marketplace list --json)
add_marketplace() {
	printf '%s' "$marketplaces" | jq -e --arg n "$1" 'any(.[]; .name == $n)' >/dev/null ||
		claude plugin marketplace add "$2"
}
add_marketplace claude-plugins-official anthropics/claude-plugins-official
add_marketplace shuymn-codex shuymn/codex-plugin-cc

installed=$(claude plugin list --json)
is_installed() {
	printf '%s' "$installed" | jq -e --arg id "$1" 'any(.[]; .id == $id and .scope == "user")' >/dev/null
}
is_installed codex@shuymn-codex || claude plugin install codex@shuymn-codex
# security-guidance reviews every stop with Opus; enable it per repository in
# .claude/settings.local.json where security review is worth that cost.
is_installed security-guidance@claude-plugins-official || claude plugin install security-guidance@claude-plugins-official
if [ "$(claude plugin list --json | jq '[.[] | select(.id == "security-guidance@claude-plugins-official" and .scope == "user")][0].enabled')" = true ]; then
	claude plugin disable --scope user security-guidance@claude-plugins-official
fi
