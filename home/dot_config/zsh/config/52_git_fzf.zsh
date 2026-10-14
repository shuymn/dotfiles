if ! has "fzf"; then
  return
fi

change-branch() {
  emulate -L zsh
  setopt pipefail no_aliases

  local all=false

  while [[ "$1" = "-a" || "$1" = "--all" ]]; do
    all=true
    shift 1
  done

  local target="$1"

  if [ -n "$target" ]; then
    if ! [[ $target =~ ^-?[0-9]+$ ]]; then
      # 明示的にブランチを指定された場合は reflogで絞った一覧ではなく、参照の存在で判断する
      # master/mainは相互にフォールバックする
      local -a candidates
      if [ "$target" = "master" ]; then
        candidates=("master" "main")
      elif [ "$target" = "main" ]; then
        candidates=("main" "master")
      else
        candidates=("$target")
      fi

      local name
      for name in "${candidates[@]}"; do
        # 1: ローカルブランチがあればそれに切り替え
        if git show-ref --verify --quiet "refs/heads/$name"; then
          if [ "$name" != "$target" ]; then
            echo "branch '$target' does not exist; switched to '$name'" >&2
          fi
          git switch "$name"
          return
        fi
        # 2: originにだけあるならtrackingで作って切り替え
        if git show-ref --verify --quiet "refs/remotes/origin/$name"; then
          if [ "$name" != "$target" ]; then
            echo "branch '$target' does not exist; switched to '$name'" >&2
          fi
          git switch --track "origin/$name"
          return
        fi
      done

      print -u2 -- "branch '$target' does not exist"
      return 1
    fi
  fi

  local branches
  branches=$(git branch --format='%(refname:short)') || return

  if [ "$all" = false ]; then
    branches=$(
      git reflog --format='%gs' |
        awk '$1 == "checkout:" && !seen[$NF]++ { print $NF }' |
        grep -Fx -f <(print -r -- "$branches")
    ) || {
      print -u2 -- "no recently visited local branches; use cb --all"
      return 1
    }
  fi

  if [[ -z "$branches" ]]; then
    print -u2 -- "no local branches"
    return 1
  fi

  if [ -n "$target" ]; then
    local -a branch_names=("${(@f)branches}")
    local branch=${branch_names[$((target + 1))]}

    if [ -z "$branch" ]; then
      print -u2 -- "branch #$target does not exist"
      return 1
    fi

    git switch "$branch"
    return
  fi

  local branch
  branch=$(print -r -- "$branches" | fzf --no-multi) || return
  [[ -n "$branch" ]] || return 1
  git switch "$branch"
}
alias cb='change-branch'

# Local/Remote branch selector (zsh)
# Usage:
#   lsb              # local branches
#   lsb --remote     # remote branches (origin/*), outputs without "origin/"
# Examples:
#   git switch "$(lsb)"
#   git switch -c "$(lsb --remote)" --track "origin/$(lsb --remote)"
lsb() {
  emulate -L zsh
  setopt pipefail no_aliases

  local remote=0
  local author=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
    --remote | -r)
      remote=1
      shift
      ;;
    --author)
      if (( $# < 2 )); then
        print -u2 -- "usage: lsb [--remote|-r] [--author <pattern>]"
        return 2
      fi
      author="$2"
      shift 2
      ;;
    --author=*)
      author="${1#*=}"
      shift
      ;;
    *)
      print -u2 "usage: lsb [--remote|-r] [--author <pattern>]"
      return 2
      ;;
    esac
  done

  local preview_cmd
  local selection

  if ((remote)); then
    # List origin/*, strip "origin/", sort by latest commit epoch, show branch in fzf
    preview_cmd='git log -n 30 --date=short --pretty=format:"%C(auto)%h %ad %d %s" origin/{}'
    selection="$(
      git for-each-ref --sort=-committerdate refs/remotes/origin --format='%(refname:short)' |
        grep -vE '^(origin/HEAD|origin)$' |
        sed 's#^origin/##' |
        while IFS= read -r br; do
          if [[ -n "$author" ]]; then
            # local と代入を分けると local の終了ステータス(常に0)が標準出力されるため1行で書く
            local tip="$(git log -1 --format='%an <%ae>' "origin/$br" 2>/dev/null)" || continue
            [[ "$tip" =~ "$author" ]] || continue
          fi
          print -r -- "$br"
        done |
        fzf --prompt='remote> ' --preview "$preview_cmd"
    )" || return
  else
    # Local refs/heads, sort by latest commit epoch, show branch in fzf
    preview_cmd='git log -n 30 --date=short --pretty=format:"%C(auto)%h %ad %d %s" {}'
    selection="$(
      git for-each-ref --sort=-committerdate refs/heads --format='%(refname:short)' |
        fzf --prompt='branch> ' --preview "$preview_cmd"
    )" || return
  fi

  [[ -n "$selection" ]] && print -r -- "$selection"
}
alias lsbr='lsb --remote'

if has "ghq"; then
  # ghq は git worktree (.git がファイル) もリポジトリとして列挙するので除外する
  _ghq_list_without_worktrees() {
    local dir
    ghq list --full-path "$@" | while IFS= read -r dir; do
      [[ -f "$dir/.git" ]] || print -r -- "$dir"
    done
  }

  change-repository() {
    emulate -L zsh
    setopt pipefail no_aliases

    local repo_path
    if [ -n "$1" ]; then
      repo_path="$(_ghq_list_without_worktrees --exact "$1")" || return

      if [ -z "$repo_path" ]; then
        print -u2 -- "no directories found for '$1'"
        return 1
      fi
    else
      repo_path=$(
        _ghq_list_without_worktrees | roots |
          fzf --no-multi --preview 'eza -aT --level=2 --ignore-glob=.git -- {} | head -200' \
            --preview-window='right:60%:wrap'
      ) || return
    fi

    [[ -n "$repo_path" ]] || return 1
    builtin cd -- "$repo_path"
  }
  alias cr='change-repository'
fi

if has "gh"; then
  gh-pr-checkout-fzf() {
    emulate -L zsh
    setopt pipefail no_aliases

    local selection
    selection=$(gh pr list | fzf --no-multi) || return
    [[ -n "$selection" ]] || return 1
    gh pr checkout "${selection%%$'\t'*}"
  }
  alias cbpr='gh-pr-checkout-fzf'
fi
