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
    --effort medium \
    --append-system-prompt-file "${prompt_file}" \
    "$@"
}
