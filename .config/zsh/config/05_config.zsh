bindkey '^p' up-line-or-history
bindkey '^n' down-line-or-history
bindkey '^k' up-line-or-history
bindkey '^j' down-line-or-history

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

# phpenv
if has "phpenv"; then
  eval "$(phpenv init -)"

  # xxenv-latest
  if [[ ! -d "$(phpenv root)/plugins/xxenv-latest" ]]; then
    git clone https://github.com/momo-lab/xxenv-latest.git "$(phpenv root)/plugins/xxenv-latest"
  fi
fi

# fnm
if has "fnm"; then
  export PATH="$HOME/Library/Application Support/fnm:$PATH"
  eval "$(fnm env --use-on-cd)"
fi

# bun
if [[ -d "$HOME/.bun" ]]; then
  export BUN_INSTALL="$HOME/.bun"
  export PATH="$BUN_INSTALL/bin:$PATH"
  [ -s "$BUN_INSTALL/_bun" ] && source "$BUN_INSTALL/_bun"
fi

# terminal title
function set_terminal_title() {
  # get directory name
  local current_dir=""
  if [[ "$PWD" == "$HOME" ]]; then
    current_dir="~"
  else
    # get last part of current directory
    current_dir=${PWD##*/}
    # if current directory is /, display /
    if [[ "${current_dir}" == "" ]]; then
      current_dir="/"
    fi
  fi

  # get process name and remove leading dash if present
  local process_name=$(ps -p $$ -o comm=)
  process_name=${process_name##*/} # Remove path
  process_name=${process_name#-}   # Remove leading dash if present

  # example: "zsh - dotfiles"
  print -Pn "\033]0;${process_name} - ${current_dir}\007"
}
precmd_functions+=(set_terminal_title)

# starship
if has "starship"; then
  export STARSHIP_CONFIG="${HOME}/.config/starship/starship.toml"
  eval "$(starship init zsh)"
  starship_precmd_user_func="set_terminal_title"
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
  export FZF_ALT_C_OPTS="--select-1 --exit-0 --preview 'eza -aT --level=2 --ignore-glob=\".git\" {} | head -200'"

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

  # zle -N history-fzf
  # bindkey '^r' history-fzf

  # enhancd
  if [[ -f "$HOME/.enhancd/init.sh" ]]; then
    export ENHANCD_FILTER="fzf:non-existing-filter"
    export ENHANCD_HOOK_AFTER_CD="ls"

    load "$HOME/.enhancd/init.sh"
  fi

  # zoxide
  if has "zoxide"; then
    eval "$(zoxide init --cmd j zsh)"
  fi
fi

if has "brew" && uname | grep Darwin 1>/dev/null 2>&1; then
  export HOMEBREW_NO_ENV_HINTS="true"

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

  # zlib
  add_pkg_config_path "/usr/local/opt/zlib/lib/pkgconfig"
fi

# nix
if has "nix"; then
  load "${HOME}/.nix-profile/etc/profile.d/nix.sh"
fi

# aws-vault
if has "aws-vault"; then
  eval "$(aws-vault --completion-script-zsh)"
  # export AWS_SESSION_TOKEN_TTL=12h
fi

# granted
if has "granted"; then
  export GRANTED_ENABLE_AUTO_REASSUME=true
fi

# terraform
if has "terraform"; then
  complete -o nospace -C /usr/local/bin/terraform terraform
fi

# volta
if [[ -d "$HOME/.volta" ]]; then
  export VOLTA_HOME="$HOME/.volta"
fi

# ghg
add_path "$HOME/.ghg/bin"

# Haskell
load "${HOME}/.ghcup/env"

# atuin
if has "atuin"; then
  export ATUIN_NOBIND="true"
  eval "$(atuin init zsh)"
  bindkey '^r' _atuin_search_widget
fi

# 1password-cli
load "${HOME}/.config/op/plugins.sh"

# JetBrains
add_path "$HOME/Library/Application Support/JetBrains/Toolbox/scripts"

# bat / delta
# export BAT_THEME="Catppuccin-macchiato"

# bun completions
[ -s "$HOME/.bun/_bun" ] && source "$HOME/.bun/_bun"

# rye
load "${HOME}/.rye/env"

# edit-command-line
autoload -Uz edit-command-line
zle -N edit-command-line

function kitty_scrollback_edit_command_line() {
  local VISUAL="$HOME/.local/share/nvim/lazy/kitty-scrollback.nvim/scripts/edit_command_line.sh"
  zle edit-command-line
  zle kill-whole-line
}
zle -N kitty_scrollback_edit_command_line

bindkey -M viins '^e' kitty_scrollback_edit_command_line
bindkey -M vicmd '^e' kitty_scrollback_edit_command_line
