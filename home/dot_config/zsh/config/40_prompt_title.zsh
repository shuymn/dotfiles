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

# Shell integration: report the working directory (OSC 7) and prompt/command
# boundaries (OSC 133) so the terminal tracks each pane's directory, can jump
# between prompts, and clears program status records at each new prompt.
typeset -gi _shell_integration_command_running=0

_shell_integration_report_pwd() {
  emulate -L zsh
  setopt extended_glob
  local LC_ALL=C
  # Percent-encode every byte outside the unreserved set and "/".
  local encoded=${PWD//(#m)[^A-Za-z0-9\/._~-]/%${(l:2::0:)$(( [##16] #MATCH ))}}
  printf '\033]7;file://%s%s\033\\' "${HOST}" "${encoded}"
}

_shell_integration_precmd() {
  local exit_status=$?
  if (( _shell_integration_command_running )); then
    printf '\033]133;D;%d\033\\' "${exit_status}"
    _shell_integration_command_running=0
  fi
  _shell_integration_report_pwd
  printf '\033]133;A\033\\'
}

_shell_integration_preexec() {
  _shell_integration_command_running=1
  printf '\033]133;C\033\\'
}

add-zsh-hook precmd set_terminal_title
add-zsh-hook precmd _shell_integration_precmd
add-zsh-hook preexec _shell_integration_preexec
