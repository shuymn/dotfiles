# utilility functions
has() {
  type "$1" >/dev/null 2>&1
  return $?
}

load() {
  if [[ -f "$@" ]]; then
    source "$@"
  fi
}

# load primitive config
load "${XDG_CONFIG_HOME}/zsh/config/init.zsh"

# load aliases
load "${XDG_CONFIG_HOME}/zsh/config/alias.zsh"

# load commands
load "${XDG_CONFIG_HOME}/zsh/config/command.zsh"

# load tmux config
load "${XDG_CONFIG_HOME}/zsh/config/tmux.zsh"

# load general config
load "${XDG_CONFIG_HOME}/zsh/config/config.zsh"

# load plugins
load "${XDG_CONFIG_HOME}/zsh/config/plugin.zsh"

# load local config
load "${XDG_CONFIG_HOME}/zsh/config/local.zsh"
