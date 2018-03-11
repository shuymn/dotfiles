# -------------------------------------------------- 
# history
# -------------------------------------------------- 

# share history betweet all sessions
setopt share_history

# delete old recorded entry if new entry is a duplicate
setopt hist_ignore_all_dups

# remove superfluous blanks before recording entry
setopt hist_reduce_blanks

# don't record an entry starting with a space
setopt hist_ignore_space

# -------------------------------------------------- 
# completion
# -------------------------------------------------- 

setopt auto_list
setopt auto_menu
setopt list_packed
setopt list_types

zstyle ':completion:*' matcher-list 'm:{a-z}={A-Z}'
zstyle ':completion:*' completer _complete

## cache
zstyle ':completion:*' use-cache yes
zstyle ':completion:*' cache-path "${XDG_CACHE_HOME}/.zsh"

## sudo
zstyle ':completion:*:sudo:*' command-path /usr/local/sbin /usr/local/bin /usr/sbin /usr/bin /sbin /bin

# -------------------------------------------------- 
# prompt
# -------------------------------------------------- 

setopt correct

PROMPT="%F{blue}%*%f %~
%B%(?,%F{white},%F{red})%#%f%b "

SPROMPT="%r is correct? [n,y,a,e]: "

# -------------------------------------------------- 
# aliases
# -------------------------------------------------- 

alias sudo='sudo '
alias cdu='cd-gitroot'
alias reload="exec $SHELL -l"
alias fzf='fzf --ansi --reverse --height 50%'
alias flew='fillin brew {{command}}'

# ls related
alias ls='ls -wG'
alias la='ls -wG -a'
alias lal='ls -wG -al'
alias ll='ls -wG -l'
alias lla='ls -wG -la'

# vim related
alias vi='nvim'
alias vim='nvim'
alias vimrc='nvim ~/.vimrc'
alias nvimrc="nvim ${XDG_CONFIG_HOME}/nvim/init.vim"
alias gvimrc='nvim ~/.gvimrc'

# zsh related
alias zshenv='nvim ~/.zshenv'
alias zshrc="nvim ${XDG_CONFIG_HOME}/zsh/init.zsh"
alias zplugrc="nvim ${XDG_CONFIG_HOME}/zsh/zplug.zsh"

# docker related
alias d='docker'
alias dc='docker-compose'
alias dp='docker ps'
alias dcb='docker-compose build'
alias dcd='docker-compose down'
alias dce='docker-compose exec'
alias dcp='docker-compose ps'
alias dcu='docker-compose up'
alias dcud='docker-compose up -d'

# git related
alias g='git'
alias ga='git add'
alias gb='git branch'
alias gc='git commit'
alias gs='git status'

# -------------------------------------------------- 
# others
# -------------------------------------------------- 

setopt no_beep

## anyenv
if [[ -f ~/.anyenv/bin/anyenv ]]; then
  eval "$(anyenv init -)"
fi

## title
case "${TERM}" in
  xterm*)
    precmd() {
      print -Pn "\e]0;%n@%m: %~\a"
    };;
esac

## composer running with HHVM
hh-composer () {
  tty=
  tty -s && tty=--tty
  docker run \
    $tty \
    --interactive \
    --rm \
    --volume $(pwd):/app \
    hh-composer "$@"
}
