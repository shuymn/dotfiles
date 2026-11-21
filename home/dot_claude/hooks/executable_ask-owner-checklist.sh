#!/bin/sh
# Claude Code PreToolUse(AskUserQuestion) hook: put the hiden decision checklist in front of the agent
# right before it asks the owner. It never denies; the question goes ahead unchanged.
set -eu

cat <<'EOF'
{"hookSpecificOutput":{"hookEventName":"PreToolUse","additionalContext":"Before this question reaches the owner, check it against the hiden skill (SKILL.md steps 3-5, references/judgment.md). 1) Is it the owner's to decide (money, accounts and billing, posting in the owner's name, approval gates, the owner's data, public behaviour, irreversible steps)? If not, choose, act and report instead of asking. 2) If a recommendation changed, did at least two other models review it without seeing your conclusion? 3) For a method choice, did you consult Codex with the options and reasons? 4) Does the question first show, for a reader without context: the decision in one sentence, plain background, each option's gains, losses, reversibility and cost, the default if nobody decides, your recommendation and what would change it, and the facts versus assumptions? 5) Is every limit you accept backed by alternatives you tested? If any answer is no, fix that first; if the question still stands, ask it once with everything else batched."}}
EOF
