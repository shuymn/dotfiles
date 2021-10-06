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
  if type brew >/dev/null 2>&1; then
    echo "[update] brew"
    brew upgrade
    echo ""

    echo "[update] brew cask"
    brew upgrade --cask
    echo ""

    if type ncu >/dev/null 2>&1; then
      echo "[update] node"
      ncu -g -u
    fi
  fi

  # Haskell
  if type ghcup >/dev/null 2>&1; then
    echo "[update] ghcup"
    ghcup upgrade
    ghcup install ghc recommended
    ghcup install cabal recommended
    ghcup install stack recommended
    ghcup install hls recommended
    echo ""
  fi

  if type cabal >/dev/null 2>&1; then
    echo "[update] cabal"
    cabal update
    echo ""
  fi

  # Rust
  if type rustup >/dev/null 2>&1; then
    echo "[update] rustup"
    rustup self update
    rustup update
    echo ""
  fi

  if type cargo >/dev/null 2>&1; then
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
  if type asdf >/dev/null 2>&1; then
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
  if type anyenv >/dev/null 2>&1; then
    echo "[update] anyenv"
    anyenv update
  fi
}
