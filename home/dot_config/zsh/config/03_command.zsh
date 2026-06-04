config() {
  hx "$XDG_CONFIG_HOME/$@"
}

gomi() {
  local root && root=$(ghq root)
  go mod init $(pwd | sed -e "s#$root/##g")
}
