typeset -gx -U path
path=( \
  /usr/local/bin(N-/) \
  /usr/local/sbin(N-/) \
  /usr/local/opt/zplug(N-/) \
  ~/.local/bin(N-/) \
  ~/.serverless/bin(N-/) \
  ~/.cargo/bin(N-/) \
  "$path[@]" \
)

typeset -gx -U fpath
fpath=( \
  /usr/local/share/zsh/site-functions(N-/) \
  /usr/local/share/zsh-completions(N-/) \
  $fpath \
)

# autoload
autoload -Uz run-help
autoload -Uz add-zsh-hook
autoload -Uz colors && colors
autoload -Uz compinit && compinit -d "${XDG_CACHE_HOME}/zsh/.zcompdump"
autoload -U +X bashcompinit && bashcompinit

# Language
export LANGUAGE="en_US.UTF-8"
export LANG="${LANGUAGE}"
export LC_ALL="${LANGUAGE}"
export LC_TYPE="${LANGUAGE}"

# Editor
export EDITOR=nvim
export CVSEDITOR="${EDITOR}"
export SVN_EDITOR="${EDITOR}"
export GIT_EDITOR="${EDITOR}"

# Pager
export PAGER=less
# Less status line
export LESS='-R -f -X -i -P ?f%f:(stdin). ?lb%lb?L/%L.. [?eEOF:?pb%pb\%..]'
export LESSCHARSET='utf-8'

# LESS man page colors (makes Man pages more readable).
export LESS_TERMCAP_mb=$'\E[01;31m'
export LESS_TERMCAP_md=$'\E[01;31m'
export LESS_TERMCAP_me=$'\E[0m'
export LESS_TERMCAP_se=$'\E[0m'
export LESS_TERMCAP_so=$'\E[00;44;37m'
export LESS_TERMCAP_ue=$'\E[0m'
export LESS_TERMCAP_us=$'\E[01;32m'

# ls command colors
export CLICOLOR=1
export LSCOLORS=ExFxBxDxCxegedabagacad

# History
export HISTFILE="${XDG_CACHE_HOME}/zsh/.zsh_history"
export HISTSIZE=10000
export SAVEHIST=1000000

# Key binding
bindkey -v

setopt no_global_rcs

# golang
export GOPATH="$HOME/go"
export GOBIN="$GOPATH/bin"
[ ! -d $GOBIN ] || export PATH="$GOBIN:$PATH"

# mysql5.6
[ ! -d "/usr/local/opt/mysql@5.6/bin" ] || export PATH="/usr/local/opt/mysql@5.6/bin:$PATH"

# dotpath
export DOTPATH=${0:A:h}
