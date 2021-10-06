# aliases
alias reload="exec $SHELL -l"
alias status="git status --short --branch"

if has "terraform"; then
  alias tf="terraform"
fi

if has "bundle"; then
  alias rails='asdf exec bundle exec rails'
  alias rspec='asdf exec bundle exec rspec'
fi

if has "exa"; then
  alias ls='exa --classify --group-directories-first --icons'
  alias ll='exa --classify --group-directories-first --icons --long --header --git'
else
  alias ls='ls -G'
fi

if has "bat"; then
  alias cat='bat --paging=never'
fi

if has "rg"; then
  alias grep='rg'
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

if has "pyenv"; then
  alias python='pyenv exec python'
fi

if has "fzf"; then
  git-switch-fzf() {
    local branches branch
    branches=$(git branch) &&
      branch=$(echo "$branches" | fzf +m) &&
      git switch $(echo "$branch" | sd '\*' '' | awk '{print $1}')
  }
  alias switch='git-switch-fzf'

  if has "ghq"; then
    ghq-cd() {
      if [ -n "$1" ]; then
        dir="$(ghq list --full-path --exact "$1")"

        if [ -z "$dir" ]; then
          echo "no directories found for '$1'"
          return 1
        fi

        cd "$dir"
        return
      fi

      cd "$(ghq list --full-path | fzf --preview 'exa -aT --level=2 --ignore-glob='.git' {} | head -200')"
    }
    alias repos='ghq-cd'
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
fi

if type vscode-launcher-go >/dev/null 2>&1; then
  alias code="vscode-launcher-go"
fi

# PhpStorm
if [[ -d "${HOME}/Applications/JetBrains Toolbox/PhpStorm.app" ]]; then
  alias phpstorm="open -a ${HOME}/Applications/JetBrains\ Toolbox/PhpStorm.app"
fi

# RubyMine
if [[ -d "${HOME}/Applications/JetBrains Toolbox/RubyMine.app" ]]; then
  alias rubymine="open -a ${HOME}/Applications/JetBrains\ Toolbox/RubyMine.app"
fi

# DataGrip
if [[ -d "${HOME}/Applications/JetBrains Toolbox/DataGrip.app" ]]; then
  alias datagrip="open -a ${HOME}/Applications/JetBrains\ Toolbox/DataGrip.app"
fi
