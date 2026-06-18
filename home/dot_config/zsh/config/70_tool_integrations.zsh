# capsule
if has "capsule"; then
  eval "$(capsule init zsh)"
fi

# Homebrew
if has "brew" && uname | grep Darwin >/dev/null 2>&1; then
  export HOMEBREW_NO_ENV_HINTS="true"
fi

# terraform
if has "terraform"; then
  autoload -U +X bashcompinit
  bashcompinit
  complete -o nospace -C "$(command -v terraform)" terraform
fi

# atuin
if has "atuin"; then
  export ATUIN_NOBIND="true"
  unset ATUIN_TMUX_POPUP
  eval "$(atuin init zsh)"
  bindkey '^r' _atuin_search_widget
fi

# 1password-cli
load "${HOME}/.config/op/plugins.sh"

# bat
export BAT_THEME="ansi"

# yazi
if has "yazi"; then
  yy() {
    local tmp cwd yazi_status
    tmp="$(mktemp -t "yazi-cwd.XXXXXX")" || return

    {
      command yazi --cwd-file="$tmp" "$@"
      yazi_status=$?

      cwd="$(command cat -- "$tmp" 2>/dev/null)"
      if [[ "$cwd" != "$PWD" && -d "$cwd" ]]; then
        builtin cd -- "$cwd"
      fi
    } always {
      command rm -f -- "$tmp"
    }

    return "$yazi_status"
  }
fi

# pi-coding-agent
export PI_SKIP_VERSION_CHECK=1

# git-gtr
_gtr_init="${XDG_CACHE_HOME:-$HOME/.cache}/gtr/init-gtr.zsh"
[[ -f "$_gtr_init" ]] || eval "$(git gtr init zsh --as cw)" || true
source "$_gtr_init" 2>/dev/null || true; unset _gtr_init
