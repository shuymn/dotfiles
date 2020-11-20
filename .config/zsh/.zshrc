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

# disable
disable r

# alias
alias reload="exec $SHELL -l"
alias status="git status --short --branch"

if type bundle >/dev/null 2>&1; then
  alias rails='asdf exec bundle exec rails'
  alias rspec='asdf exec bundle exec rspec'
fi

if type exa >/dev/null 2>&1; then
  alias ls='exa --classify --group-directories-first --icons'
  alias lls='exa --classify --group-directories-first --icons --long --header --git'
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
  export EDITOR=nvim
  alias vi='nvim'
  alias vim='nvim'
  alias zshrc="nvim ${XDG_CONFIG_HOME}/zsh/.zshrc"
fi

if type asdf >/dev/null 2>&1; then
  . $(brew --prefix asdf)/asdf.sh

  if type direnv >/dev/null 2>&1; then
    eval "$(asdf exec direnv hook zsh)"
  fi
fi

if type pyenv >/dev/null 2>&1; then
  eval "$(pyenv init -)"
  eval "$(pyenv virtualenv-init -)"
fi

# starship
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

  # tmux
  if type tmux >/dev/null 2>&1; then
    if [[ ! -n $TMUX && $- == *l* ]]; then
      local sess_id
      sess_id="$(tmux list-sessions)"
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

  git-switch-fzf() {
    local branches branch
    branches=$(git branch) &&
      branch=$(echo "$branches" | fzf +m) &&
      git switch $(echo "$branch" | awk '{print $1}' | sed "s/.* //")
  }
  alias switch='git-switch-fzf'

  # gh
  if type gh >/dev/null 2>&1; then
    gh-pr-checkout-fzf() {
      gh pr checkout "$(gh pr list | fzf | cut -f1)"
    }
    alias review='gh-pr-checkout-fzf'
  fi
fi

# nix
if type nix >/dev/null 2>&1; then
  . ~/.nix-profile/etc/profile.d/nix.sh
fi

# functions
update() {
  if type brew >/dev/null 2>&1; then
    echo "[update] brew"
    brew upgrade
    echo ""

    echo "[update] brew cask"
    brew upgrade --cask
    echo ""
  fi

  # Haskell
  if type stack >/dev/null 2>&1; then
    echo "[update] stack"
    stack upgrade
    echo ""
  fi

  # Rust
  if type rustup >/dev/null 2>&1; then
    echo "[update] rustup"
    rustup self update
    echo ""
  fi

  # asdf
  if type asdf >/dev/null 2>&1; then
    echo "[update] asdf"
    asdf plugin update --all
  fi
}

config() { vim "$XDG_CONFIG_HOME/$@" }

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

# openssl
export LDFLAGS="-L/usr/local/opt/openssl@1.1/lib"
export CPPFLAGS="-I/usr/local/opt/openssl@1.1/include"

