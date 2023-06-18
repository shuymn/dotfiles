# Fig pre block. Keep at the top of this file.
[[ -f "$HOME/.fig/shell/zshrc.pre.zsh" ]] && builtin source "$HOME/.fig/shell/zshrc.pre.zsh"

# utilility functions
has() {
  type "$1" >/dev/null 2>&1
  return $?
}

load() {
  if [[ -f "$@" ]]; then
    builtin source "$@"
  fi
}

add_path() {
  if [[ -d "$@" ]]; then
    export PATH="$@:$PATH"
  fi
}

add_pkg_config_path() {
  if [[ -d "$@" ]]; then
    export PKG_CONFIG_PATH="$@:$PKG_CONFIG_PATH"
  fi
}

# load primitive config
load "${XDG_CONFIG_HOME:?}/zsh/config/init.zsh"

# load aliases
load "${XDG_CONFIG_HOME:?}/zsh/config/alias.zsh"

# load commands
load "${XDG_CONFIG_HOME:?}/zsh/config/command.zsh"

# load tmux config
load "${XDG_CONFIG_HOME:?}/zsh/config/tmux.zsh"

# load general config
load "${XDG_CONFIG_HOME:?}/zsh/config/config.zsh"

# load plugins
load "${XDG_CONFIG_HOME:?}/zsh/config/plugin.zsh"

# load local config
load "${XDG_CONFIG_HOME:?}/zsh/config/local.zsh"

# Fig post block. Keep at the bottom of this file.
[[ -f "$HOME/.fig/shell/zshrc.post.zsh" ]] && builtin source "$HOME/.fig/shell/zshrc.post.zsh"
