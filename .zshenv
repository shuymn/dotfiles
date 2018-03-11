typeset -U path fpath cdpath manpath

bindkey -v

export XDG_CONFIG_HOME=~/.config
export XDG_CACHE_HOME=~/.cache

if [[ ! -d "${XDG_CACHE_HOME}/.zsh" ]]; then
  mkdir -p "${XDG_CACHE_HOME}/.zsh"
fi

# autoload
autoload -Uz colors && colors
autoload -Uz compinit && compinit -u -d "${XDG_CACHE_HOME}/.zsh/.zcompdump"

# export
export LANGUAGE="en_US.UTF-8"
export LANG="${LANGUAGE}"
export LC_ALL="${LANGUAGE}"
export LC_CTYPE="${LANGUAGE}"

export EDITOR=vim

export TERM=xterm-256color
export LSCOLORS=gxfxcxdxbxegedabagacad

export HISTFILE="${XDG_CACHE_HOME}/.zsh/.zsh_history"
export HISTSIZE=10000
export SAVEHIST=1000000

## disable loading global profiles
setopt no_global_rcs

## homebrew
export PATH=/usr/local/bin:$PATH
export PATH=/usr/local/sbin:$PATH
## go
export GOPATH=~/.go
export PATH=/usr/local/go/bin:$PATH
## haskell stack
export PATH=~/.local/bin:$PATH
## anyenv
export PATH=~/.anyenv/bin:$PATH
## macvim-kaoriya
export PATH=$(brew --prefix macvim-kaoriya)/bin:$PATH
## zplug
export PATH=~/.zplug/bin:$PATH

