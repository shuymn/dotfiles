config() {
  hx "$XDG_CONFIG_HOME/$@"
}

update() {
  if has claude; then
    echo "[update] claude"
    claude update
    echo ""
  fi

  if has opencode; then
    echo "[update] opencode"
    opencode upgrade
    echo ""
  fi

  if has copilot; then
    echo "[update] copilot"
    copilot update
    echo ""
  fi

  if has topgrade; then
    topgrade
    echo ""
  else
    if has apt && uname -a | grep -v Darwin 1> /dev/null 2>&1; then
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

  # go
#   if has "gup"; then
    # echo "[update] Go"
    # gup -e golangci-lint,gostaticanalyzer update
#   fi
}

gomi() {
  local root && root=$(ghq root)
  go mod init $(pwd | sed -e "s#$root/##g")
}
