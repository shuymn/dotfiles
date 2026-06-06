if has "direnv"; then
  export DIRENV_WARN_TIMEOUT=30s
  eval "$(direnv hook zsh)"
fi
