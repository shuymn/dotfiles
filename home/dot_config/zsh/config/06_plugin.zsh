# zsh fast syntax highlighting
for profile in "${DOTFILES_NIX_PROFILE_DIRS[@]}"
do
  plugin="${profile}/share/zsh/plugins/fast-syntax-highlighting/fast-syntax-highlighting.plugin.zsh"
  if [[ -f "${plugin}" ]]; then
    load "${plugin}"
    break
  fi
done
unset profile plugin

# ni.zsh
load "$HOME/.config/zsh/plugins/ni.zsh"
