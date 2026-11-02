#!/bin/sh
# Usage: chezmoi-backup.sh <backup dir> <chezmoi command...>
# Copy the home files that `chezmoi apply` would modify or delete into
# <backup dir>, replacing the previous backup, so one generation of
# overwritten content survives. Keep the previous backup when apply would
# overwrite nothing. Directories are copied only when apply deletes them;
# otherwise their changed files are listed separately.
set -eu
backup=$1
shift

status=$("$@" status)
# After status: chezmoi derives target modes from the umask.
umask 077
next="$backup.new"
rm -rf "$next"
printf '%s\n' "$status" | while IFS= read -r line; do
  target=${line#???}
  path="$HOME/$target"
  case $line in
  ?D*) [ -e "$path" ] || [ -L "$path" ] || continue ;;
  ?M*) [ -L "$path" ] || [ -f "$path" ] || continue ;;
  *) continue ;;
  esac
  # A deleted parent directory was already copied with its contents.
  [ -e "$next/$target" ] || [ -L "$next/$target" ] && continue
  mkdir -p "$next/$(dirname "$target")"
  cp -pPR "$path" "$next/$target"
done
[ -d "$next" ] || exit 0
rm -rf "$backup"
mv "$next" "$backup"
echo "Backed up home files that apply will overwrite to $backup"
