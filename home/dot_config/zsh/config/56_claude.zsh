claude-fable() {
  local prompt_file="${HOME}/.claude/prompts/fable-orchestrator.md"

  if ! has claude; then
    print -u2 "claude-fable: claude is not available"
    return 127
  fi

  if [[ ! -r "${prompt_file}" ]]; then
    print -u2 "claude-fable: prompt not found: ${prompt_file}"
    return 1
  fi

  command claude \
    --model fable \
    --effort high \
    --append-system-prompt-file "${prompt_file}" \
    "$@"
}

claude-sonnet-advisor() {
  local prompt_file="${HOME}/.claude/prompts/sonnet-executor-with-fable-advisor.md"

  if ! has claude; then
    print -u2 "claude-sonnet-advisor: claude is not available"
    return 127
  fi

  if [[ ! -r "${prompt_file}" ]]; then
    print -u2 "claude-sonnet-advisor: prompt not found: ${prompt_file}"
    return 1
  fi

  command claude \
    --model sonnet \
    --effort medium \
    --append-system-prompt-file "${prompt_file}" \
    "$@"
}
