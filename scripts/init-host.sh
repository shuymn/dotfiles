#!/bin/sh
# Write the git-ignored host.toml that Nix and chezmoi read for host values.
set -eu

if [ "$#" -ne 3 ]; then
  echo "usage: $0 <host.toml> <roles.toml> <role>" >&2
  exit 2
fi

host_file=$1
roles_file=$2
role=$3

if [ -e "$host_file" ]; then
  echo "$host_file already exists; edit it to change host values" >&2
  exit 1
fi

case $role in
  '' | *[!a-z0-9-]*) role_known=false ;;
  *) grep -qx "\[$role\]" "$roles_file" && role_known=true || role_known=false ;;
esac
if [ "$role_known" != true ]; then
  echo "unknown role '$role'; choose a table name from $roles_file" >&2
  exit 2
fi

if [ "$(uname -s)" != Darwin ]; then
  echo "host.toml generation supports macOS only" >&2
  exit 2
fi
case $(uname -m) in
  arm64) system=aarch64-darwin ;;
  x86_64) system=x86_64-darwin ;;
  *)
    echo "unsupported architecture: $(uname -m)" >&2
    exit 2
    ;;
esac

toml_string() {
  printf '"%s"' "$(printf '%s' "$1" | sed -e 's/\\/\\\\/g' -e 's/"/\\"/g')"
}

tmp_file="$host_file.tmp.$$"
trap 'rm -f "$tmp_file"' EXIT INT TERM
{
  echo "# Local host values for nix-darwin, Home Manager, and chezmoi. Never commit this file."
  echo "system = $(toml_string "$system")"
  echo "username = $(toml_string "$(id -un)")"
  echo "homeDirectory = $(toml_string "$HOME")"
  echo "hostName = $(toml_string "$(hostname -s)")"
  echo "computerName = $(toml_string "$(scutil --get ComputerName)")"
  echo "role = $(toml_string "$role")"
} > "$tmp_file"
mv "$tmp_file" "$host_file"
echo "wrote $host_file (role: $role)"
