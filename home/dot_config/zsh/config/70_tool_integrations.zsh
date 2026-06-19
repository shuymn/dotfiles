# capsule
if has "capsule"; then
  eval "$(capsule init zsh)"
fi

# Homebrew
if has "brew" && uname | grep Darwin >/dev/null 2>&1; then
  export HOMEBREW_NO_ENV_HINTS="true"
fi

# terraform
if has "terraform"; then
  autoload -U +X bashcompinit
  bashcompinit
  complete -o nospace -C "$(command -v terraform)" terraform
fi

# atuin
if has "atuin"; then
  export ATUIN_NOBIND="true"
  unset ATUIN_TMUX_POPUP
  eval "$(atuin init zsh)"
  bindkey '^r' _atuin_search_widget
fi

# 1password-cli
load "${HOME}/.config/op/plugins.sh"

# bat
export BAT_THEME="ansi"

# yazi
if has "yazi"; then
  yy() {
    local tmp cwd yazi_status
    tmp="$(mktemp -t "yazi-cwd.XXXXXX")" || return

    {
      command yazi --cwd-file="$tmp" "$@"
      yazi_status=$?

      cwd="$(command cat -- "$tmp" 2>/dev/null)"
      if [[ "$cwd" != "$PWD" && -d "$cwd" ]]; then
        builtin cd -- "$cwd"
      fi
    } always {
      command rm -f -- "$tmp"
    }

    return "$yazi_status"
  }
fi

# pi-coding-agent
export PI_SKIP_VERSION_CHECK=1

# git-wt
if has "git-wt"; then
  _git_wt_visible_list() {
    emulate -L zsh
    setopt pipefail no_aliases

    local tmp_root tmp_real
    tmp_root="${TMPDIR:-/tmp}"
    tmp_root="${tmp_root%/}"
    tmp_real="$(cd "$tmp_root" 2>/dev/null && pwd -P)"

    git-wt | awk -v tmp_root="$tmp_root" -v tmp_real="$tmp_real" '
      NR == 1 { print; next }
      {
        path = ($1 == "*") ? $2 : $1
        if (tmp_root != "" && index(path, tmp_root "/tmp.") == 1) next
        if (tmp_real != "" && index(path, tmp_real "/tmp.") == 1) next
        print
      }
    '
  }

  cw() {
    emulate -L zsh
    setopt pipefail no_aliases

    if ! has "fzf"; then
      print -u2 "cw: fzf is required"
      return 1
    fi

    local selection target_path
    selection="$(_git_wt_visible_list | fzf --header-lines=1)" || return
    target_path="$(awk '{ if ($1 == "*") print $2; else print $1 }' <<< "$selection")"

    [[ -n "$target_path" ]] && cd "$target_path"
  }
fi

# Start work quickly with a disposable branch name, then rename with
# `git wt -m <old> <new>` once the task name is clear.
wt-wip() {
  local branch="wip/$(date +%Y%m%d-%H%M%S)"
  local target_path

  target_path="$(git-wt "$branch" "$@")" || return
  cd "$target_path"
}
alias gwip="wt-wip"
