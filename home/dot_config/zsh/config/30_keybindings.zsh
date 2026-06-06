# Key bindings
bindkey -v
bindkey '^p' up-line-or-history
bindkey '^n' down-line-or-history
bindkey '^k' up-line-or-history
bindkey '^j' down-line-or-history

# edit-command-line
autoload -Uz edit-command-line
zle -N edit-command-line
