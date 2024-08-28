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

if has "gomi"; then
  alias rm=gomi
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

          local count && count=$(echo "$branches" | grep -x "$1" | wc -l | tr -d ' ')

          if [ $count != "1" ]; then
            echo "branch '$1' does not exist"
            return
          fi

          git switch "$1"
          return
        fi

        local branch && branch=$(echo "$branches" | fzf +m) && git switch "$branch"
        return
        ;;
      esac
    done
  }
  alias cb='change-branch'

  if has "ghq"; then
    change-repository() {
      if [ -n "$1" ]; then
        local dir
        dir="$(ghq list --full-path --exact "$1")"

        if [ -z "$dir" ]; then
          echo "no directories found for '$1'"
          return 1
        fi

        cd "$dir"
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

if has "vscode-launcher-go"; then
  alias code="vscode-launcher-go"
  alias code-insiders="vscode-launcher-go -insiders"
fi

if has "code-insiders"; then
  alias c="code-insiders"
fi

if has "pbcopy"; then
  alias teee='tee >(pbcopy)'
fi
