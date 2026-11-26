current_dir_title() {
  if [[ "$PWD" == "$HOME" ]]; then
    print -r -- "~"
    return
  fi

  local current_dir=${PWD##*/}
  if [[ "${current_dir}" == "" ]]; then
    print -r -- "/"
  else
    print -r -- "${current_dir}"
  fi
}

set_terminal_title() {
  local current_dir
  current_dir=$(current_dir_title)

  printf '\033]0;%s - %s\007' "${ZSH_NAME:-zsh}" "$current_dir"
}

add-zsh-hook precmd set_terminal_title
