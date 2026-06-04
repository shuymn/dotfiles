bindkey '^p' up-line-or-history
bindkey '^n' down-line-or-history
bindkey '^k' up-line-or-history
bindkey '^j' down-line-or-history

# direnv
if has "direnv"; then
  export DIRENV_WARN_TIMEOUT=30s

  eval "$(direnv hook zsh)"
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
add-zsh-hook precmd set_terminal_title

# capsule
if has "capsule"; then
    eval "$(capsule init zsh)"
fi

# fzf
if has "fzf"; then
  load "${HOME}/.fzf.sh"

  export FZF_DEFAULT_COMMAND='fd --type f --hidden --exclude .git'
  export FZF_DEFAULT_OPTS='--height 40% --reverse --border'

  export FZF_CTRL_T_COMMAND=$FZF_DEFAULT_COMMAND
  export FZF_CTRL_T_OPTS='--preview \
    "[[ $(file --mime {}) =~ binary ]] && \
    echo {} is a binary file || \
    (bat --style=number,header,grid --color=always {} || \
    highlight -O ansi -l {} || \
    coderay {} || \
    rougify {} || \
    cat {}) 2> /dev/null | head -500"'

  export FZF_ALT_C_COMMAND='fd --type d --hidden --exclude .git'
  export FZF_ALT_C_OPTS="--select-1 --exit-0 --preview 'eza -aT --level=2 --ignore-glob=\".git\" {} | head -200'"

  history-fzf() {
    local tac

    if type tac > /dev/null 2>&1; then
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

if has "brew" && uname | grep Darwin 1> /dev/null 2>&1; then
  export HOMEBREW_NO_ENV_HINTS="true"
fi

# terraform
if has "terraform"; then
  autoload -U +X bashcompinit && bashcompinit
  complete -o nospace -C "$(command -v terraform)" terraform
fi

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
export BAT_THEME="ansi"

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
