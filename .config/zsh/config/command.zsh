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

  # Haskell
  if has ghcup; then
    echo "[update] ghcup"
    ghcup upgrade
    ghcup install ghc recommended
    ghcup install cabal recommended
    ghcup install stack recommended
    ghcup install hls recommended
    echo ""
  fi

  if has cabal; then
    echo "[update] cabal"
    cabal update
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

  # asdf
  if has asdf; then
    echo "[update] asdf"
    asdf plugin update --all
    echo ""

    echo "[update] asdf direnv"
    asdf install direnv latest
    asdf global direnv $(asdf latest direnv)
    echo ""

    echo "[update] asdf nodejs(LTS)"
    asdf install nodejs latest:14
    asdf global nodejs $(asdf latest nodejs 14)
    echo ""

    echo "[update] asdf ruby"
    asdf install ruby latest
    asdf global ruby $(asdf latest ruby)
    echo ""

    # echo "[update] asdf php(7.4)"
    # asdf install php latest:7.4
    # asdf global php $(asdf latest php)
    # echo ""

    asdf reshim
  fi

  # anyenv
  if has anyenv; then
    echo "[update] anyenv"
    anyenv update
    echo ""
  fi

  # volta
  if has volta; then
    echo "[update] volta"
    curl https://get.volta.sh | bash
    echo ""

    echo "[update] node"
    volta install node
    echo ""
  fi
}