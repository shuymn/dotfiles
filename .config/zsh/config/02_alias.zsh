# aliases
alias reload="exec $SHELL -l"

alias status="git status --short --branch"

if has "terraform"; then
  alias tf="terraform"
fi

if has "eza"; then
  alias ls='eza --classify --group-directories-first --icons'
  alias ll='eza --classify --group-directories-first --icons --long --header --git'
else
  alias ls='ls -G'
fi

if has "bat"; then
  alias cat='bat --paging=never'
fi

if has "btm"; then
  alias top='btm'
fi

if has "procs"; then
  alias ps='procs'
fi

if has "nvim"; then
  alias vi='nvim'
  alias vim='nvim'
  alias zshrc="nvim ${XDG_CONFIG_HOME}/zsh/.zshrc"
fi

if has "$(brew --prefix)/bin/gomi"; then
  alias rm="$(brew --prefix)/bin/gomi"
fi

if has "fzf"; then
  change-branch() {
    local all && all=false

    while [ $# -ge 0 ]; do
      case "$1" in
        -a | --all)
          all=true
          shift 1
          ;;
        *)
          local target && target="$1"
          local branches && branches=$(git branch | sed -e 's/[ +*]//g')

          if [ "$all" = false ]; then
            branches=$(echo "$branches" | grep -x -f- --color=never <(git reflog | awk '$3 ~ /checkout/ {print $8}' | awk '!c[$1]++ {print $1}'))
          fi

          if [ -n "$target" ]; then
            if [[ $target =~ ^-?[0-9]+([.][0-9]+)?$ ]]; then
              local ba && IFS=$'\n' ba=($(echo $branches))
              local branch && branch=${ba[$((target + 1))]}

              if [ -z "$branch" ]; then
                echo "branch #$target does not exist"
                return
              fi

              git switch "$branch"
              return
            fi

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

            echo "branch '$target' does not exist"
            return
          fi

          local branch && branch=$(echo "$branches" | fzf +m) && git switch "$branch"
          return
          ;;
      esac
    done
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
          author="${2:-}"
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
    change-repository() {
      if [ -n "$1" ]; then
        local repo_path=""
        repo_path="$(ghq list --full-path --exact "$1")"

        if [ -z "$repo_path" ]; then
          echo "no directories found for '$1'"
          return 1
        fi

        cd "$repo_path"
        return
      fi

      cd "$(ghq list --full-path | fzf --preview 'eza -aT --level=2 --ignore-glob='.git' {} | head -200')"
    }
    alias cr='change-repository'
  fi

  if has "tmux" && has "tig"; then
    alias tig='TERM=xterm-256color tig'
  fi

  if has "gh"; then
    gh-pr-checkout-fzf() {
      gh pr checkout "$(gh pr list | fzf | cut -f1)"
    }
    alias review='gh-pr-checkout-fzf'
  fi

  if has "aws-vault"; then
    eva() {
      local profile
      profile=$(aws-vault list --profiles | fzf) &&
        unset AWS_VAULT &&
        export $(aws-vault exec "$profile" --prompt=osascript -- env | grep AWS_)
    }

    uva() {
      unset $(env | grep AWS_ | sed 's/=.*//g')
    }
  fi
fi

if has "pbcopy"; then
  alias teee='tee >(pbcopy)'
fi

if has "kitty"; then
  alias kish="kitty +kitten ssh"
fi
