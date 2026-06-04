emulate -L zsh
setopt null_glob

owner() {
  case "$1" in
    "$HOME"/.local/share/mise/shims/*|"$HOME"/.local/share/mise/installs/*) print mise ;;
    /etc/profiles/per-user/*/bin/*|/run/current-system/sw/bin/*|/nix/var/nix/profiles/default/bin/*|"$HOME"/.nix-profile/bin/*) print nix ;;
    /opt/homebrew/bin/*|/opt/homebrew/sbin/*|/usr/local/bin/*|/usr/local/sbin/*|/home/linuxbrew/.linuxbrew/bin/*|/home/linuxbrew/.linuxbrew/sbin/*) print brew ;;
    /usr/bin/*|/bin/*|/usr/sbin/*|/sbin/*) print system ;;
    *) print unmanaged ;;
  esac
}

needs_attention() {
  [[ "$1" = brew || "$1" = unmanaged ]]
}

typeset -A command_paths
for dir in $path; do
  [[ -d "$dir" ]] || continue
  for file in "$dir"/*; do
    [[ -f "$file" && -x "$file" ]] || continue
    cmd="${file:t}"
    if [[ -z "${command_paths[$cmd]}" ]]; then
      command_paths[$cmd]="$file"
    else
      command_paths[$cmd]+=$'\n'"$file"
    fi
  done
done

for cmd in "${(@k)command_paths}"; do
  paths=("${(@f)command_paths[$cmd]}")
  [[ ${#paths[@]} -gt 0 ]] || continue
  first="${paths[1]}"
  first_owner=$(owner "$first")
  needs_attention "$first_owner" && printf "%s\tfirst=%s\t%s\n" "$cmd" "$first_owner" "$first"
  for p in "${paths[@]}"; do
    [[ "$p" = "$first" ]] && continue
    p_owner=$(owner "$p")
    [[ "$p_owner" = "$first_owner" ]] && continue
    needs_attention "$p_owner" && printf "%s\tshadow=%s\t%s\n" "$cmd" "$p_owner" "$p"
  done
done | sort
