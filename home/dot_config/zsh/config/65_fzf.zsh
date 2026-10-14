if ! has "fzf"; then
  return
fi

export FZF_DEFAULT_COMMAND='fd --type f --hidden --exclude .git'
export FZF_DEFAULT_OPTS='--height 40% --layout=reverse --border --cycle --info=inline --pointer="➜ " --marker="✓ "'

# cd + find: pick a directory below the current one and change into it.
cdf() {
  emulate -L zsh
  # No pipefail: fd exits 1 when fzf closes the pipe before the walk ends.
  setopt no_aliases

  local selection
  selection="$(
    command fd --type d --hidden --exclude .git --print0 |
      command fzf --read0 --no-multi --query="$*" --prompt='directory> ' \
        --preview 'eza -aT --level=2 --ignore-glob=.git --color=always -- {} | head -200'
  )" || return

  [[ -n "$selection" ]] && builtin cd -- "$selection"
}

# find file: print the selected path for use in other commands, e.g. cat "$(ff)".
ff() {
  emulate -L zsh
  # No pipefail: fd exits 1 when fzf closes the pipe before the walk ends.
  setopt no_aliases

  local selection
  selection="$(
    command fd --type f --hidden --exclude .git --print0 |
      command fzf --read0 --no-multi --query="$*" --prompt='file> ' \
        --preview 'bat --style=numbers,header,grid --color=always --line-range=:500 -- {}'
  )" || return

  [[ -n "$selection" ]] && print -r -- "$selection"
}

if has "zoxide"; then
  eval "$(zoxide init --cmd j zsh)"
fi
