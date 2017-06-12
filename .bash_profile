[ -f "$HOME/.bashrc" ] && source "$HOME/.bashrc"

defaults write com.apple.finder AppleShowAllFiles -boolean true
defaults write -g ApplePressAndHoldEnabled -bool false

alias ls='ls -G'

export LSCOLORS=gxfxcxdxbxegedabagacad
export GOPATH=$HOME/.go
export PATH="$HOME/.anyenv/bin:$PATH:$GOPATH/bin"

eval "$(anyenv init -)"
