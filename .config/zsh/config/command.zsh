config() {
  vim "$XDG_CONFIG_HOME/$@"
}

ssh() {
  if [[ -n $TMUX ]]; then
    local pane_id="$(tmux display -p '#{pane_id}')"
    tmux select-pane -P 'bg=colour52,fg=white'
    command ssh $@
    tmux select-pane -t "$pane_id" -P 'default'
  else
    command ssh $@
  fi
}

update() {
  if has brew; then
    echo "[update] brew"
    brew upgrade
    echo ""

    echo "[update] brew cask"
    brew upgrade --cask
    echo ""
  fi

  if has apt && uname -a | grep -v Darwin 1>/dev/null 2>&1; then
    echo "[update] apt"
    sudo apt update && sudo apt upgrade -y
    echo ""
  fi

  # Rust
  if has rustup; then
    echo "[update] rustup"
    rustup self update
    rustup update
    echo ""
  fi

  if has cargo; then
    echo "[update] cargo"
    cargo install-update --all
    echo ""

    echo "[update] rust nightly"
    rustup update nightly
    echo ""

    echo "[update] rust stable"
    rustup update stable
    echo ""
  fi

  # anyenv
  if has anyenv; then
    echo "[update] anyenv"
    anyenv update
    echo ""
  fi

  if has rbenv; then
    echo "[update] ruby"
    rbenv latest install
    rbenv latest latest
    echo ""
  fi

  if has pyenv; then
    echo "[update] pyenv"
    pyenv latest install 2
    pyenv latest global 2
    pyenv latest install 3
    pyenv latest global 3
    echo ""
  fi

  # volta
  if has volta; then
    echo "[update] volta"
    curl https://get.volta.sh | bash
    echo ""

    echo "[update] node"
    volta install node
  fi
}
