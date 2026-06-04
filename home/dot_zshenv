# XDG Base Directory Specification
export XDG_CONFIG_HOME=~/.config
export XDG_CACHE_HOME=~/.cache

if [[ ! -d "${XDG_CONFIG_HOME}/zsh" ]]; then
	mkdir -p "${XDG_CONFIG_HOME}/zsh"
fi

if [[ ! -d "${XDG_CACHE_HOME}/zsh" ]]; then
	mkdir -p "${XDG_CACHE_HOME}/zsh"
fi

export ZDOTDIR="${XDG_CONFIG_HOME}/zsh"

# load .zshenv
builtin source ${ZDOTDIR}/.zshenv
