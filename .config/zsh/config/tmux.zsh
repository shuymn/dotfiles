if has "fzf" && has "tmux"; then
  if [ -z $TMUX ] && [[ $- == *l* ]] && [[ $TERM_PROGRAM != "vscode" ]] && [[ -z $SSH_CLIENT || -z $SSH_TTY ]]; then
    local sess_id
    sess_id="$(tmux ls 2>/dev/null)"
    if [[ -z "$sess_id" ]]; then
      tmux new-session
    fi

    readonly local msg="Create new session"
    readonly local sess_msg="${sess_id}\n${msg}"
    sess_id="$(echo $sess_msg | fzf | cut -d: -f1)"
    if [[ "$sess_id" = "$msg" ]]; then
      tmux new-session
    elif [[ -n "$sess_id" ]]; then
      tmux attach-session -t "$sess_id"
    else
      # start terminal normally
      :
    fi
  fi
fi

# tmux package manager
if has "tmux" && [[ ! -d "${HOME}/.tmux/plugins/tpm" ]]; then
  git clone https://github.com/tmux-plugins/tpm ~/.tmux/plugins/tpm
fi
