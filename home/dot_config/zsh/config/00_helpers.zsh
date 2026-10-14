has() {
  type "$1" >/dev/null 2>&1
}

load() {
  if [[ -f "$1" ]]; then
    builtin source "$1"
  fi
}
