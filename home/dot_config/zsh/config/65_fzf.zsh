if ! has "fzf"; then
  return
fi

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

if has "zoxide"; then
  eval "$(zoxide init --cmd j zsh)"
fi
