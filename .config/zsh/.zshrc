# history
setopt share_history
setopt hist_ignore_all_dups
setopt hist_reduce_blanks
setopt hist_ignore_space

# completion
setopt auto_list
setopt auto_menu
setopt list_packed
setopt list_types

zstyle ':completion:*' matcher-list 'm:{a-z}={A-Z}'
zstyle ':completion:*' completer _complete

# cache
zstyle ':completion:*' use-cache yes
zstyle ':completion:*' cache-path "${XDG_CACHE_HOME}/.zsh"

# sudo
zstyle ':completion:*:sudo:*' command-path /usr/local/sbin /usr/local/bin /usr/sbin /usr/bin /sbin /bin

# alias
alias reload="exec $SHELL -l"

if type exa >/dev/null 2>&1; then
  alias ls='exa'
else
  alias ls='ls -G'
fi

if type bat >/dev/null 2>&1; then
  alias cat='bat --paging=never'
fi

if type ripgrep >/dev/null 2>&1; then
  alias grep='ripgrep'
fi

if type nvim >/dev/null 2>&1; then
  alias vi='nvim'
  alias vim='nvim'
fi

# anyenv
if type anyenv >/dev/null 2>&1; then
  eval "$(anyenv init -)"

  if type pyenv >/dev/null 2>&1 && [[ -d $(pyenv root)/plugins/pyenv-virtualenv ]]; then
    eval "$(pyenv virtualenv-init - zsh)"
  fi
fi

if type starship >/dev/null 2>&1; then
  export STARSHIP_CONFIG="$HOME/.config/starship/starship.toml"
  eval "$(starship init zsh)"
fi

# fzf
if type fzf >/dev/null 2>&1; then
  [ -f ~/.fzf.zsh ] && source ~/.fzf.zsh

  export FZF_DEFAULT_COMMAND='fd --type f --hidden'
  export FZF_DEFAULT_OPTS='--height 40% --reverse --border'

  export FZF_CTRL_T_COMMAND=$FZF_DEFAULT_COMMAND
  export FZF_CTRL_T_OPTS='--preview \
    "[[ $(file --mine {}) =~ binary ]] && \
    echo {} is a binary file || \
    (bat --style=number,header,grid --color=always {} || \
    highlight -O ansi -l {} || \
    coderay {} || \
    rougify {} || \
    cat {}) 2> /dev/null | head -500"'

  export FZF_ALT_C_COMMAND='fd --type d --hidden'
  export FZF_ALT_C_OPTS="--select-1 --exit-0 --preview 'exa -aT --level=2 --ignore-glob=\".git\" {} | head -200'"

  history-fzf() {
    local tac

    if type tac >/dev/null 2>&1; then
      tac="tac"
    else
      tac="tail -r"
    fi

    BUFFER=$(history -n 1 | eval $tac | fzf --query "$LBUFFER")
    CURSOR=$#BUFFER

    zle reset-prompt
  }

  zle -N history-fzf
  bindkey '^r' history-fzf

  if type ghq >/dev/null 2>&1; then
    ghq-fzf() {
      cd "$(ghq list --full-path | fzf --preview 'exa -aT --level=2 --ignore-glob='.git' {} | head -200')"
    }
    alias repos='ghq-fzf'
  fi
fi

# direnv
if type direnv >/dev/null 2>&1; then
  eval "$(direnv hook zsh)"
fi

# nix
if type nix >/dev/null 2>&1; then
  . /Users/shu.yamani/.nix-profile/etc/profile.d/nix.sh
fi

# functions
update() {
  if type brew >/dev/null 2>&1; then
    brew upgrade
    brew cask upgrade
  fi

  if type anyenv >/dev/null 2>&1; then
    anyenv git pull
    anyenv update
  fi

  # Haskell
  if type stack >/dev/null 2>&1; then
    stack upgrade
  fi

  # Rust
  if type rustup >/dev/null 2>&1; then
    rustup self update
  fi
}

# tabtab source for packages
# uninstall by removing these lines
[[ -f ~/.config/tabtab/__tabtab.zsh ]] && . ~/.config/tabtab/__tabtab.zsh || true

# plugins
if [[ -e "/usr/local/share/zsh-history-substring-search/zsh-history-substring-search.zsh" ]]; then
  source "/usr/local/share/zsh-history-substring-search/zsh-history-substring-search.zsh"
fi

if [[ -e "/usr/local/share/zsh-syntax-highlighting/zsh-syntax-highlighting.zsh" ]]; then
  source "/usr/local/share/zsh-syntax-highlighting/zsh-syntax-highlighting.zsh"
fi

# pyenv-virtualenv
if [[ -n $VIRTUAL_ENV && -e "${VIRTUAL_ENV}/bin/activate" ]]; then
  source "${VIRTUAL_ENV}/bin/activate"
fi
