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
  eval "$(atuin init zsh)"
  bindkey '^r' _atuin_search_widget
fi

# 1password-cli
load "${HOME}/.config/op/plugins.sh"

# bat / delta
export BAT_THEME="ansi"

# pi-coding-agent
export PI_SKIP_VERSION_CHECK=1
