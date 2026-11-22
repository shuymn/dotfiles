#!/bin/sh
# Claude Code PreToolUse(AskUserQuestion) hook: an orchestrator reads the hiden decision checklist
# before the owner sees its question. The first call of a question is denied with the checklist as
# the reason (the reason reaches the model before any dialog; context added on an allowed call
# would only arrive after the owner answered). The next call in the same owner turn (prompt_id)
# within 10 minutes goes through.
# Only main sessions with a stack kit open (`stack kit open`) are orchestrators; workers, including
# in-process subagents that share the parent's session id, ask their orchestrator by design.
# Any input or tool failure lets the question through.

# Process starts are slow on some hosts (Git Bash on Windows), so this sticks to shell builtins and
# a single jq call.

PATH="/etc/profiles/per-user/${USER:-$(id -un)}/bin:/run/current-system/sw/bin:$PATH"
export PATH

sessions="$HOME/.local/state/stack/sessions"
set -- "$sessions"/*.kits
[ -e "$1" ] || exit 0

# One jq call: subagents and malformed session ids print nothing; otherwise "session|now|turn".
# -j prints no newline, so Windows jq adds no CR.
out=$(jq -j '
  (.agent_id // "" | strings) as $agent
  | (.session_id // "" | strings) as $session
  | select($agent == "" and ($session | length) <= 128 and ($session | gsub("[A-Za-z0-9_-]"; "") == "" and . != ""))
  | "\($session | ascii_downcase)|\(now | floor)|\(.prompt_id // "" | strings)"' 2>/dev/null) || exit 0
[ -n "$out" ] || exit 0
session=${out%%|*}
rest=${out#*|}
now=${rest%%|*}
turn=${rest#*|}
[ -s "$sessions/$session.kits" ] || exit 0

# The mark holds "<epoch>|<prompt_id>" from the denied call.
dir="$HOME/.cache/ask-owner-checklist"
mark="$dir/$session"
if [ -f "$mark" ] && IFS= read -r line <"$mark"; then
  since=${line%%|*}
  case $since in
    '' | *[!0-9]*) ;;
    *)
      if [ $((now - since)) -lt 600 ] && [ "${line#*|}" = "$turn" ]; then
        rm -f "$mark" 2>/dev/null
        exit 0
      fi
      ;;
  esac
fi
{ [ -d "$dir" ] || mkdir -p "$dir" 2>/dev/null; } && printf '%s|%s\n' "$now" "$turn" >"$mark" 2>/dev/null || exit 0

printf '%s\n' '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"Not shown to the owner yet. Before asking, check the question against the hiden skill (SKILL.md steps 3-5, references/judgment.md). 1) Is it the owner'"'"'s to decide (money, accounts and billing, posting in the owner'"'"'s name, approval gates, the owner'"'"'s data, public behaviour, irreversible steps)? A method choice, or a difference that does not matter and can be undone, is yours: choose, report and do not ask. 2) If a recommendation changed, did at least two other models review it without seeing your conclusion? 3) For a method choice, did you consult Codex with the options and reasons? 4) Does the question first show, for a reader without context: the decision in one sentence, plain background, each option'"'"'s gains, losses, reversibility and cost, the default if nobody decides, your recommendation and what would change it, and the facts versus assumptions? 5) Is every limit or side effect you accept backed by alternatives you tested on real inputs, and shown not to harm what users can use or see? Fix what fails; if the question still stands, send it again once with everything else batched (the next call in this turn within 10 minutes goes through)."}}'
