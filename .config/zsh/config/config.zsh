# neovim
if has "nvim"; then
  export EDITOR=nvim
fi

# version manager
if has "anyenv"; then
  eval "$(anyenv init -)"

  # anyenv-update
  if [[ ! -d "$(anyenv root)/plugins/anyenv-update" ]]; then
    git clone https://github.com/znz/anyenv-update.git "$(anyenv root)/plugins/anyenv-update"
  fi
fi

if has "asdf"; then
  export ASDF_NPM_DEFAULT_PACKAGES_FILE="$HOME/.config/asdf/.default-npm-packages"

  if has "brew"; then
    source "$(brew --prefix asdf)/asdf.sh"
  elif [[ -d "$HOME/.asdf" ]]; then
    source "$HOME/.asdf/asdf.sh"
  fi
fi

# direnv
if has "direnv"; then
  export DIRENV_WARN_TIMEOUT=30s

  if has "asdf"; then
    eval "$(asdf exec direnv hook zsh)"
  else
    eval "$(direnv hook zsh)"
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
  if [[ ! -d "$(pyenv root)/plugins/pyenv-virtualenv" ]]; then
    git clone https://github.com/pyenv/pyenv-virtualenv.git "$(pyenv root)/plugins/pyenv-virtualenv"
  fi
  eval "$(pyenv virtualenv-init - zsh)"
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

if has "phpenv"; then
  eval "$(phpenv init -)"

  # xxenv-latest
  if [[ ! -d "$(phpenv root)/plugins/xxenv-latest" ]]; then
    git clone https://github.com/momo-lab/xxenv-latest.git "$(phpenv root)/plugins/xxenv-latest"
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

    load "$HOME/.enhancd/init.sh"
  fi
fi

if has "brew"; then
  # bison
  add_path "/usr/local/opt/bison/bin"

  # libxml2
  add_path "/usr/local/opt/libxml2/bin"
  add_pkg_config_path "/usr/local/opt/libxml2/lib/pkgconfig"

  # bzip2
  add_path "/usr/local/opt/bzip2/bin"

  # curl
  add_path "/usr/local/opt/curl/bin"

  # libiconv
  add_path "/usr/local/opt/libiconv/bin"

  # krb5
  add_path "/usr/local/opt/krb5/bin"
  add_pkg_config_path "/usr/local/opt/krb5/lib/pkgconfig"

  # openssl@1.1
  add_path "/usr/local/opt/openssl@1.1/bin"
  add_pkg_config_path "/usr/local/opt/openssl@1.1/lib/pkgconfig"

  # icu4c
  add_path "/usr/local/opt/icu4c/bin"

  # libedit
  add_pkg_config_path "/usr/local/opt/libedit/lib/pkgconfig"

  # libjpeg
  add_pkg_config_path "/usr/local/opt/libjpeg/lib/pkgconfig"

  # libpng
  add_pkg_config_path "/usr/local/opt/libpng/lib/pkgconfig"

  # libzip
  add_pkg_config_path "/usr/local/opt/libzip/lib/pkgconfig"

  # oniguruma
  add_pkg_config_path "/usr/local/opt/oniguruma/lib/pkgconfig"

  # tidy-html5
  add_pkg_config_path "/usr/local/opt/tidy-html5/lib/pkgconfig"
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

# volta
if [[ -d "$HOME/.volta" ]]; then
  export VOLTA_HOME="$HOME/.volta"
fi

# Haskell
load "${HOME}/.ghcup/env"
