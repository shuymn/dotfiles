alias reload="exec $SHELL -l"
alias status="git status --short --branch"

if has "terraform"; then
  alias tf="terraform"
fi

if has "eza"; then
  alias ls='eza --classify --group-directories-first --icons'
  alias ll='eza --classify --group-directories-first --icons --long --header --git'
else
  alias ls='ls -G'
fi

if has "bat"; then
  alias cat='bat --paging=never'
fi

if has "pbcopy"; then
  alias teee='tee >(pbcopy)'
fi
