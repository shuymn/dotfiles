# Autoloaded helpers
autoload -Uz add-zsh-hook
if (( ${+aliases[run-help]} )); then
  unalias run-help
fi
autoload -Uz run-help

# Disabled builtins/aliases
disable r
