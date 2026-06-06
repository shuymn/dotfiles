has() {
  type "$1" >/dev/null 2>&1
}

load() {
  if [[ -f "$1" ]]; then
    builtin source "$1"
  fi
}

add_path() {
  if [[ -d "$1" ]]; then
    path=("$1" "$path[@]")
  fi
}

add_pkg_config_path() {
  if [[ -d "$1" ]]; then
    export PKG_CONFIG_PATH="$1:${PKG_CONFIG_PATH:-}"
  fi
}
