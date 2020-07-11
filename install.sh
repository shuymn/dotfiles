#!/bin/bash

errorf() {
  printf "$*"
  exit 1
}

is_exists() {
  type "$1" >/dev/null 2>&1
  return $?
}

# Set DOTPATH as default variable
if [ -z "${DOTPATH:-}" ]; then
  DOTPATH=~/.dotfiles
  export DOTPATH
fi

DOTFILES_GITHUB="https://github.com/shuymn/dotfiles.git"
export DOTFILES_GITHUB

download() {
  if [ -d $DOTPATH ]; then
    errorf "$DOTPATH: already exists"
  fi

  echo "Downloading dotfiles..."

  if is_exists "git"; then
    git clone --recursive "$DOTFILES_GITHUB" "$DOTPATH"
  else
    errorf "git command not found"
  fi

  echo "Finish downloading"
}

link() {
  echo "Linking dotfiles..."

  if [ ! -d $DOTPATH ]; then
    errorf "$DOTPATH: not found"
  fi

  cd "$DOTPATH"

  make link && echo "Finish linking"
}

install() {
  # Download the repository
  download &&

    # Link dotfiles to home directory
    link
}

trap "echo 'terminated' 1>&2; exit 1" INT ERR
dotfiles_install
