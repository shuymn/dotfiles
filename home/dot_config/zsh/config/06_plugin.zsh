# zsh fast syntax highlighting
for plugin in \
  "/etc/profiles/per-user/${DOTFILES_USER}/share/zsh/plugins/fast-syntax-highlighting/fast-syntax-highlighting.plugin.zsh" \
  "${HOME}/.nix-profile/share/zsh/plugins/fast-syntax-highlighting/fast-syntax-highlighting.plugin.zsh" \
  "/run/current-system/sw/share/zsh/plugins/fast-syntax-highlighting/fast-syntax-highlighting.plugin.zsh" \
  "/nix/var/nix/profiles/default/share/zsh/plugins/fast-syntax-highlighting/fast-syntax-highlighting.plugin.zsh"
do
  if [[ -f "${plugin}" ]]; then
    load "${plugin}"
    break
  fi
done
unset plugin

# ni.zsh
load "$HOME/.config/zsh/plugins/ni.zsh"
