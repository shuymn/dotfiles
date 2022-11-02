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
    rbenv latest install
    rbenv latest global
  fi

  if has pyenv; then
    echo "[update] pyenv"
    pyenv install 2
    pyenv install 3
    pyenv global $(pyenv latest 3) $(pyenv latest 2)
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
}

gomi() {
  local root && root=$(ghq root)
  go mod init $(pwd | sed -e "s#$root/##g")
}
