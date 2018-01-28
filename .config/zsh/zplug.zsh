# vim:ft=zplug

ZPLUG_PROTOCOL=ssh

zplug "zplug/zplug", hook-build:"zplug --self-manage"

zplug "${XDG_CONFIG_HOME}/zsh", from:local, use:"init.zsh"

zplug "itchyny/fillin", as:command, hook-build:"go get -d && go build", use:"fillin"

zplug "peco/peco", as:command, from:gh-r
zplug "junegunn/fzf-bin", as:command, from:gh-r, rename-to:"fzf"

zplug "b4b4r07/enhancd", use:"init.sh"
if zplug check "b4b4r07/enhancd"; then
  export ENHANCD_FILTER="fzf"
  export ENHANCD_HOOK_AFTER_CD=ls
fi

zplug "mollifier/anyframe"
if zplug check "mollifier/anyframe"; then
  zstyle ":anyframe:selector:" use fzf
  zstyle ":anyframe:selector:fzf:" command 'fzf --ansi --reverse --height 50%'

  bindkey '^r' anyframe-widget-execute-history
  bindkey '^xr' anyframe-widget-put-history
  bindkey '^xi' anyframe-widget-insert-git-branch
fi

zplug "zsh-users/zsh-history-substring-search"
if zplug check "zsh-users/zsh-history-substring-search"; then
  bindkey '^[[A' history-substring-search-up
  bindkey '^[[B' history-substring-search-down
  bindkey '^p' history-substring-search-up
  bindkey '^n' history-substring-search-down
  bindkey -M vicmd 'k' history-substring-search-up
  bindkey -M vicmd 'j' history-substring-search-down
fi

zplug "zsh-users/zsh-completions"
zplug "zsh-users/zsh-autosuggestions"
zplug "zsh-users/zsh-syntax-highlighting", defer:2
