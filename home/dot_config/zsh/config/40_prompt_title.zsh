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

report_herdr_pane_title() {
  [[ -n "${HERDR_PANE_ID:-}" ]] || return
  command -v herdr >/dev/null 2>&1 || return
  [[ "$1" != "${_herdr_pane_last_title:-}" ]] || return
  _herdr_pane_last_title="$1"

  herdr pane report-metadata "${HERDR_PANE_ID}" \
    --source zsh-title \
    --title "$1" \
    >/dev/null 2>&1 &!
}

set_terminal_title() {
  local current_dir
  current_dir=$(current_dir_title)

  local process_name
  process_name=$(ps -p $$ -o comm=)
  process_name=${process_name##*/}
  process_name=${process_name#-}

  print -Pn "\033]0;${process_name} - ${current_dir}\007"
  report_herdr_pane_title "${current_dir}"
}

set_running_title() {
  local command_name=${1[(w)1]}
  [[ -n "${command_name}" ]] || return

  local current_dir
  current_dir=$(current_dir_title)
  report_herdr_pane_title "${command_name} · ${current_dir}"
}

add-zsh-hook precmd set_terminal_title
add-zsh-hook preexec set_running_title
