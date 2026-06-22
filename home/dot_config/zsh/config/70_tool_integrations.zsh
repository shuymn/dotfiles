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
    local tmp cwd yazi_status cd_status
    tmp="$(mktemp -t "yazi-cwd.XXXXXX")" || return

    {
      command yazi --cwd-file="$tmp" "$@"
      yazi_status=$?

      cwd="$(command cat -- "$tmp" 2>/dev/null)"
      if [[ "$cwd" != "$PWD" && -d "$cwd" ]]; then
        builtin cd -- "$cwd"
        cd_status=$?
        if ((cd_status != 0 && yazi_status == 0)); then
          yazi_status=$cd_status
        fi
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

    if ! has "jq"; then
      print -u2 "_git_wt_visible_list: jq is required"
      return 1
    fi

    local ghq_root root real tmp_roots_json
    local -a tmp_roots

    for root in "${TMPDIR:-/tmp}" "$(getconf DARWIN_USER_TEMP_DIR 2>/dev/null)"; do
      [[ -n "$root" ]] || continue
      root="${root%/}"
      tmp_roots+=("$root")
      real="$(cd "$root" 2>/dev/null && pwd -P)"
      [[ -n "$real" ]] && tmp_roots+=("$real")
    done

    tmp_roots_json="$(
      printf '%s\n' "${tmp_roots[@]}" | awk 'NF && !seen[$0]++' | jq -R -s 'split("\n")[:-1]'
    )" || return
    ghq_root="${HOME}/ghq/"

    printf "%s\t%-40s  %-8s  %s\n" "_" "  BRANCH" "HEAD" "PATH"
    git-wt --json |
      jq -r --argjson tmp_roots "$tmp_roots_json" --arg ghq_root "$ghq_root" '
        def temp_path($roots):
          . as $path | any($roots[]; . as $root | $path | startswith($root + "/tmp."));
        .[]
        | .path as $path
        | select(($path | temp_path($tmp_roots)) | not)
        | ($path | if startswith($ghq_root) then .[($ghq_root | length):] else . end) as $display_path
        | [
            ($path | @base64),
            ((if .current then "* " else "  " end) + (.branch // "")),
            (.head // ""),
            $display_path
          ]
        | @tsv
      ' |
      awk -F '\t' '{ printf "%s\t%-40.40s  %-8.8s  %s\n", $1, $2, $3, $4 }'
  }

  cw() {
    emulate -L zsh
    setopt pipefail no_aliases

    if ! has "fzf"; then
      print -u2 "cw: fzf is required"
      return 1
    fi
    if ! has "jq"; then
      print -u2 "cw: jq is required"
      return 1
    fi

    local selection encoded_path target_path
    selection="$(_git_wt_visible_list | fzf --header-lines=1 --delimiter=$'\t' --with-nth=2..)" || return
    encoded_path="$(awk -F '\t' 'NF >= 2 { print $1; exit }' <<< "$selection")"
    target_path="$(jq -nr --arg path "$encoded_path" '$path | @base64d')" || return

    [[ -n "$target_path" ]] && builtin cd -- "$target_path"
  }

  _git_wt_create_wip() {
    emulate -L zsh
    setopt no_aliases

    local branch_base branch target_path attempt
    branch_base="wip/$(date +%Y%m%d-%H%M%S)"

    for attempt in {0..99}; do
      branch="$branch_base"
      if ((attempt > 0)); then
        branch="${branch_base}-${attempt}"
      fi

      if git show-ref --verify --quiet "refs/heads/$branch" 2>/dev/null; then
        continue
      fi

      target_path="$(git-wt "$branch" "$@")" || return
      print -r -- "$branch"
      print -r -- "$target_path"
      return
    done

    print -u2 "wt-wip: could not find unused branch name for $branch_base"
    return 1
  }

  # Start work quickly with a disposable branch name, then rename with
  # `git wt -m <old> <new>` once the task name is clear.
  wt-wip() {
    local branch target_path
    { read -r branch; read -r target_path } < <(_git_wt_create_wip "$@") || return
    builtin cd -- "$target_path"
  }
  gwip() {
    wt-wip "$@"
  }

  if has "herdr"; then
    hwip() {
      emulate -L zsh
      setopt no_aliases

      local branch target_path herdr_status
      { read -r branch; read -r target_path } < <(_git_wt_create_wip "$@") || return
      herdr workspace create --cwd "$target_path" --label "$branch" --focus || {
        herdr_status=$?
        print -u2 "hwip: herdr failed; worktree remains at $target_path"
        print -u2 "hwip: branch remains $branch"
        return "$herdr_status"
      }
      builtin cd -- "$target_path"
    }
  fi
fi
