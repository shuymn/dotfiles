#!/usr/bin/env bash

set -eu -o pipefail

errorf() {
  printf "%s\n" "$*" >&2
  exit 1
}

script_dir() {
  local script_source
  local resolved_dir
  script_source="${BASH_SOURCE[0]}"
  if [[ ! -f "${script_source}" ]]; then
    errorf "remote execution is disabled; clone the repository locally and run ./install.sh"
  fi
  resolved_dir="$(cd -- "$(dirname -- "${script_source}")" && pwd -P)"
  if [[ ! -f "${resolved_dir}/Makefile" ]] || [[ ! -f "${resolved_dir}/install.sh" ]]; then
    errorf "remote execution is disabled; clone the repository locally and run ./install.sh"
  fi
  printf "%s\n" "${resolved_dir}"
}

require_local_checkout() {
  if [[ ! -f "${DOTPATH}/Makefile" ]]; then
    errorf "${DOTPATH}: Makefile not found"
  fi

  if [[ ! -f "${DOTPATH}/install.sh" ]]; then
    errorf "${DOTPATH}: install.sh not found"
  fi

  if [[ ! -d "${DOTPATH}/.git" ]]; then
    errorf "${DOTPATH}: not a git checkout; clone the repository locally before running install.sh"
  fi
}

link() {
  echo "Linking dotfiles..."
  make -C "${DOTPATH}" link
  echo "Finish linking"
}

install() {
  require_local_checkout
  link
}

DOTPATH="$(script_dir)"
export DOTPATH

trap "echo 'terminated' 1>&2; exit 1" INT ERR
install
