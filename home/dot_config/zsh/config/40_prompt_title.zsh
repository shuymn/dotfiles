set_terminal_title() {
  local current_dir=""
  if [[ "$PWD" == "$HOME" ]]; then
    current_dir="~"
  else
    current_dir=${PWD##*/}
    if [[ "${current_dir}" == "" ]]; then
      current_dir="/"
    fi
  fi

  local process_name
  process_name=$(ps -p $$ -o comm=)
  process_name=${process_name##*/}
  process_name=${process_name#-}

  print -Pn "\033]0;${process_name} - ${current_dir}\007"
}
add-zsh-hook precmd set_terminal_title
