#!/usr/bin/env bash
# Hook to verify explicit commit intent before executing git commit commands
# This prevents accidental commits and enforces the /commit skill's safety requirement

set -euo pipefail

# Read tool call information from stdin
input=$(cat)

# Extract tool name and command from the JSON input
tool_name=$(echo "$input" | jq -r '.tool_name // empty')
command=$(echo "$input" | jq -r '.tool_input.command // empty')

# Only check Bash tool calls
if [[ "$tool_name" != "Bash" ]]; then
    exit 0
fi

# Check if the command contains git commit
if [[ "$command" =~ git[[:space:]]+commit ]]; then
    # Check if this is likely from /commit skill by looking for specific patterns
    # /commit skill uses HEREDOC format for commit messages
    if [[ "$command" =~ \$\(cat[[:space:]]+\<\<\'EOF\' ]] || [[ "$command" =~ --amend ]]; then
        # This looks like it's from /commit skill or a legitimate commit operation
        exit 0
    fi

    # Block the commit and provide helpful message
    echo "⚠️  COMMIT BLOCKED: Explicit commit intent required" >&2
    echo "" >&2
    echo "Git commits should only be created when explicitly requested by the user." >&2
    echo "" >&2
    echo "Please use one of the following:" >&2
    echo "  • /commit        - Create commits using the commit skill" >&2
    echo "  • User request   - Wait for explicit user instruction to commit" >&2
    echo "" >&2
    echo "If you need to commit changes, please ask the user first." >&2
    echo "" >&2

    exit 2
fi

# Allow all other commands
exit 0
