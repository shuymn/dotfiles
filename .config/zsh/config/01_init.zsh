# history
setopt extended_history
setopt share_history
setopt hist_expire_dups_first
setopt hist_find_no_dups
setopt hist_ignore_all_dups
setopt hist_ignore_space
setopt hist_no_store
setopt hist_reduce_blanks
setopt hist_save_no_dups

# key binding
bindkey -v

# completion
setopt auto_list
setopt auto_menu
setopt auto_param_slash
setopt complete_in_word
setopt list_packed
setopt list_types

zstyle ':completion:*' matcher-list 'm:{a-z}={A-Z}'
zstyle ':completion:*' completer _complete
zstyle ':completion:*' menu select
zstyle ':completion:*' group-name ''
zstyle ':completion:*' verbose yes

# cache
zstyle ':completion:*' use-cache yes
zstyle ':completion:*' cache-path "${XDG_CACHE_HOME}/zsh"

# sudo
zstyle ':completion:*:sudo:*' command-path /usr/local/sbin /usr/local/bin /usr/sbin /usr/bin /sbin /bin

# autoload
autoload -Uz add-zsh-hook
autoload -Uz run-help
autoload -Uz compinit && compinit -d "${XDG_CACHE_HOME}/zsh/.zcompdump"

# disable
disable r
