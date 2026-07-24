if has "zellij"; then
  zellij-rename-repo() {
    emulate -L zsh
    setopt no_aliases

    if [[ -z "${ZELLIJ:-}" ]]; then
      print -u2 "zellij-rename-repo: not inside a Zellij session"
      return 1
    fi

    local repo_root repo_name session
    local -a sessions

    repo_root="$(command git rev-parse --show-toplevel 2>/dev/null)" || {
      print -u2 "zellij-rename-repo: not inside a Git repository"
      return 1
    }
    repo_name="${repo_root:t}"
    if [[ -z "$repo_name" ]]; then
      print -u2 "zellij-rename-repo: could not determine the repository name"
      return 1
    fi

    sessions=("${(@f)$(command zellij list-sessions --short --no-formatting)}") || {
      print -u2 "zellij-rename-repo: failed to list Zellij sessions"
      return 1
    }
    for session in "${sessions[@]}"; do
      if [[ "$session" == "$repo_name" ]]; then
        print -u2 "zellij-rename-repo: session already exists: $repo_name"
        return 1
      fi
    done

    command zellij action rename-session "$repo_name"
  }

  alias zrr="zellij-rename-repo"
fi
