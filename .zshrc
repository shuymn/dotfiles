if [[ -f ~/.zplug/init.zsh ]]; then
  export ZPLUG_LOADFILE="${XDG_CONFIG_HOME}/zsh/zplug.zsh"
  source ~/.zplug/init.zsh

  if ! zplug check --verbose; then
    printf "Install? [y/N]: "
    if read -q; then
      echo; zplug install
    fi
  fi

  zplug load
fi

if [[ -f ~/.zshrc_local ]]; then
  source ~/.zshrc_local
fi

