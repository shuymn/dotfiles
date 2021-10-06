# neovim
if has "nvim"; then
  export EDITOR=nvim
fi

# version manager
if has "anyenv"; then
  eval "$(anyenv init -)"

  # direnv
  if has "direnv"; then
    eval "$(direnv hook zsh)"
  fi
fi

if has "asdf"; then
  export ASDF_NPM_DEFAULT_PACKAGES_FILE="$HOME/.config/asdf/.default-npm-packages"
  source "$(brew --prefix asdf)/asdf.sh"

  if has "direnv"; then
    eval "$(asdf exec direnv hook zsh)"
    export DIRENV_WARN_TIMEOUT=30s
  fi
fi

# pyenv
if has "pyenv"; then
  eval "$(pyenv init -)"
  export PYENV_ROOT="$(pyenv root)"

  # xxenv-latest
  if [[ ! -d "$(pyenv root)/plugins/xxenv-latest" ]]; then
    git clone https://github.com/momo-lab/xxenv-latest.git "$(pyenv root)/plugins/xxenv-latest"
  fi

  # pyenv-virtualenv
  if [[ -d "$(pyenv root)/plugins/pyenv-virtualenv" ]]; then
    eval "$(pyenv virtualenv-init - zsh)"
  fi
fi

# nodenv
if has "nodenv"; then
  eval "$(nodenv init -)"

  # xxenv-latest
  if [[ ! -d "$(nodenv root)/plugins/xxenv-latest" ]]; then
    git clone https://github.com/momo-lab/xxenv-latest.git "$(nodenv root)/plugins/xxenv-latest"
  fi
fi

# rbenv
if has "rbenv"; then
  eval "$(rbenv init -)"

  # xxenv-latest
  if [[ ! -d "$(rbenv root)/plugins/xxenv-latest" ]]; then
    git clone https://github.com/momo-lab/xxenv-latest.git "$(rbenv root)/plugins/xxenv-latest"
  fi
fi

# starship
if has "starship"; then
  export STARSHIP_CONFIG="${HOME}/.config/starship/starship.toml"
  eval "$(starship init zsh)"
fi

# fzf
if has "fzf"; then
  load "${HOME}/.fzf.sh"

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

  # enhancd
  if [[ -f "$HOME/.enhancd/init.sh" ]]; then
    export ENHANCD_FILTER="fzf:non-existing-filter"
    export ENHANCD_HOOK_AFTER_CD="ls"

    source "$HOME/.enhancd/init.sh"
  fi
fi

# nix
if has "nix"; then
  load "${HOME}/.nix-profile/etc/profile.d/nix.sh"
fi

# aws-vault
if has "aws-vault"; then
  eval "$(aws-vault --completion-script-zsh)"
  export AWS_SESSION_TOKEN_TTL=12h
fi

# terraform
if has "terraform"; then
  complete -o nospace -C /usr/local/bin/terraform terraform
fi

# Haskell
load "${HOME}/.ghcup/env"
