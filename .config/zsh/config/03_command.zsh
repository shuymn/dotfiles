config() {
  vim "$XDG_CONFIG_HOME/$@"
}

ssh() {
  if [[ -n $TMUX ]]; then
    local pane_id="$(tmux display -p '#{pane_id}')"
    local style="default"
    case "$1" in
    *.local) ;;

    *)
      style="bg=colour52,fg=white"
      ;;
    esac
    tmux select-pane -P "$style"
    command ssh $@
    tmux select-pane -t "$pane_id" -P 'default'
  else
    command ssh $@
  fi
}

update() {
  if has brew; then
    echo "[update] brew"
    brew upgrade --fetch-HEAD

    if uname | grep Darwin 1>/dev/null 2>&1; then
      echo "[update] brew cask"
      brew upgrade --cask
    fi
  fi

  if has topgrade; then
    topgrade
    echo ""
  else
    if has apt && uname -a | grep -v Darwin 1>/dev/null 2>&1; then
      echo "[update] apt"
      sudo apt update && sudo apt upgrade -y
    fi

    # Rust
    if has rustup; then
      echo "[update] rustup"
      rustup self update
      rustup update
    fi

    if has cargo; then
      echo "[update] cargo"
      cargo install-update --all

      echo "[update] rust stable"
      rustup update stable
    fi
  fi

  # anyenv
  if has anyenv; then
    echo "[update] anyenv"
    anyenv update
  fi

  if has rbenv; then
    echo "[update] ruby"
    rbenv latest install --skip-existing
    rbenv latest global
  fi

  if has pyenv; then
    echo "[update] pyenv"
    pyenv install --skip-existing 2
    pyenv install --skip-existing 3
    pyenv global $(pyenv latest 3) $(pyenv latest 2)
  fi

  if has nodenv; then
    echo "[update] nodenv"
    nodenv latest install --skip-existing
    nodenv latest global
  fi

  # volta
  if has volta; then
    echo "[update] volta"
    curl https://get.volta.sh | bash

    echo "[update] node"
    volta install node

    echo "[update] npm"
    volta install npm
  fi

  # go
  if has "gup"; then
    echo "[update] Go"
    gup -e golangci-lint,gostaticanalyzer update
  fi
}

gomi() {
  local root && root=$(ghq root)
  go mod init $(pwd | sed -e "s#$root/##g")
}

godl() {
  local version
  local update_goroot=true

  while [[ $# -gt 0 ]]; do
    case $1 in
    latest)
      version=$(https 'go.dev/dl/?mode=json' | jq -r '.[] | select(.stable == true) | .version' | head -n 1)
      shift
      ;;
    --no-update)
      update_goroot=false
      shift
      ;;
    -h | --help)
      echo "Usage: godl [latest|<version>] [--no-update]"
      echo "  latest        Install the latest stable version of Go"
      echo "  <version>     Install a specific version of Go"
      echo "  --no-update   Install without setting GOROOT"
      return 0
      ;;
    *)
      if [[ $1 =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
        version="go$1"
        shift
      else
        echo "\"$version\" is invalid version format. Abort."
        return 1
      fi
      ;;
    esac
  done

  if [ -z "$version" ]; then
    version=$(https 'go.dev/dl/?mode=json' | jq -r '.[] | select(.stable == true) | .version' | fzf)
    if [ -z "$version" ]; then
      echo "No version selected. Abort."
      return 1
    fi
  fi

  go install "golang.org/dl/$version@latest" && $version download

  if $update_goroot; then
    local config_file && config_file="$XDG_CONFIG_HOME/zsh/config/99_local.zsh"
    if grep -q "export GOROOT=" "$config_file"; then
      local temp_file && temp_file=$(mktemp)
      local new_goroot_line='export GOROOT=$('$version' env GOROOT)'
      awk -v new_line="$new_goroot_line" '/export GOROOT=/ {print new_line; next} {print}' $config_file >"$temp_file" &&
        mv "$temp_file" "$config_file" &&
        echo "Updated GOROOT"
    else
      echo "GOROOT is not set in ${config_file}. Skip updating GOROOT."
    fi
  fi
}
