typeset -gx -U path
path=( \
  /usr/local/bin(N-/) \
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

# XDG Base Directory Specification
export XDG_CONFIG_HOME=~/.config
export XDG_CACHE_HOME=~/.cache

if [[ ! -d "${XDG_CONFIG_HOME}/zsh" ]]; then
	mkdir -p "${XDG_CONFIG_HOME}/zsh"
fi

if [[ ! -d "${XDG_CACHE_HOME}/zsh" ]]; then
	mkdir -p "${XDG_CACHE_HOME}/zsh"
fi

export ZDOTDIR="${XDG_CONFIG_HOME}/zsh"

# autoload
autoload -Uz run-help
autoload -Uz add-zsh-hook
autoload -Uz colors && colors
autoload -Uz compinit && compinit -d "${XDG_CACHE_HOME}/zsh/.zcompdump"

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
export LSCOLORS=exfxcxdxbxegedabagacad
export LS_COLORS='di=34:ln=35:so=32:pi=33:ex=31:bd=46;34:cd=43;34:su=41;30:sg=46;30:tw=42;30:ow=43;30'

# History
export HISTFILE="${XDG_CACHE_HOME}/zsh/.zsh_history"
export HISTSIZE=10000
export SAVEHIST=1000000

# Terminal
export TERM=xterm-256color

# Key binding
bindkey -v

setopt no_global_rcs

# golang
export GOPATH="$HOME/go"
export GOBIN="$GOPATH/bin"
export PATH="$GOBIN:$PATH"

# mysql5.6
export PATH="/usr/local/opt/mysql@5.6/bin:$PATH"

export DOTPATH=${0:A:h}
