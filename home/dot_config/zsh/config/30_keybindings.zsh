# Key bindings
bindkey -e
bindkey '^p' up-line-or-history
bindkey '^n' down-line-or-history
bindkey '^k' up-line-or-history
bindkey '^j' down-line-or-history

# edit-command-line
autoload -Uz edit-command-line
zle -N edit-command-line
bindkey '^g' edit-command-line

# Temporarily stash/restore the current command line, matching Claude Code's ctrl+s.
# When a line is already stashed, ctrl+s is a no-op instead of stacking lines.
typeset -gi _push_line_stashed=0
_toggle-push-line() {
  if (( _push_line_stashed )); then
    if [[ -z "${BUFFER}" ]]; then
      _push_line_stashed=0
      zle get-line
    fi
    return 0
  fi

  [[ -n "${BUFFER}" ]] || return 0
  _push_line_stashed=1
  zle push-line
}
zle -N _toggle-push-line
[[ -t 0 ]] && stty -ixon
bindkey '^s' _toggle-push-line
