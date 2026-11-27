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
	commit create-pr extensible-by-design simplify triage-review
install_skills mattpocock/skills writing-for-agents
install_skills cloudflare/security-audit-skill security-audit

# Rex's skill and session hook for Claude Code and Codex; rerunning is a no-op.
# The Claude Code hook is also in modify_private_settings.json, which owns
# settings.json hooks. Outside a Rex terminal, use the server's bundled CLI.
rex=$(command -v rex ||
	ls "$HOME/Library/Application Support/com.superlogical.rex/RexServer/Versions/Current/Rex Server.app/Contents/MacOS/rex" 2>/dev/null ||
	true)
if [ -n "$rex" ]; then
	"$rex" skill setup >/dev/null
	# Rex's xterm-rex terminfo entry, plus the ssh guard that sends a plain TERM
	# to hosts without it (one Include line at the top of ~/.ssh/config).
	"$rex" terminfo setup >/dev/null
else
	echo "install-agents: skip Rex setup; rex is not installed" >&2
fi

marketplaces=$(claude plugin marketplace list --json)
add_marketplace() {
	printf '%s' "$marketplaces" | jq -e --arg n "$1" 'any(.[]; .name == $n)' >/dev/null ||
		claude plugin marketplace add "$2"
}
add_marketplace claude-plugins-official anthropics/claude-plugins-official
add_marketplace shuymn-codex shuymn/codex-plugin-cc
add_marketplace googlechrome GoogleChrome/modern-web-guidance

installed=$(claude plugin list --json)
is_installed() {
	printf '%s' "$installed" | jq -e --arg id "$1" 'any(.[]; .id == $id and .scope == "user")' >/dev/null
}
is_installed codex@shuymn-codex || claude plugin install codex@shuymn-codex
is_installed modern-web-guidance@googlechrome || claude plugin install modern-web-guidance@googlechrome
# security-guidance reviews every stop with Opus; enable it per repository in
# .claude/settings.local.json where security review is worth that cost.
is_installed security-guidance@claude-plugins-official || claude plugin install security-guidance@claude-plugins-official
if [ "$(claude plugin list --json | jq '[.[] | select(.id == "security-guidance@claude-plugins-official" and .scope == "user")][0].enabled')" = true ]; then
	claude plugin disable --scope user security-guidance@claude-plugins-official
fi
