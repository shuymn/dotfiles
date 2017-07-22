typeset -U path cdpath fpath manpath

[ ! -d $HOME/.zfunctions ] && mkdir -p $HOME/.zfunctions
fpath=("$HOME/.zfunctions" $fpath)

# zplug の設定
if [ -e "${HOME}/.zplug" ]; then
  source ~/.zplug/init.zsh

  zplug "zsh-users/zsh-syntax-highlighting", defer:2
  zplug "zsh-users/zsh-history-substring-search"
  zplug "zsh-users/zsh-completions"
  zplug "chriskempson/base16-shell"

  if ! zplug check --verbose; then
    printf "Install? [y/N]: "
    if read -q; then
      echo; zplug install
    fi
  fi

  zplug load
fi

# 環境変数
export EDITOR=vim        # エディタをvimに設定
export LANG=ja_JP.UTF-8  # 文字コードをUTF-8に設定
export KCODE=u           # KCODEにUTF-8を設定
bindkey -v

# 履歴の設定
HISTFILE="${HOME}/.zsh_history"  # 履歴ファイルの保存先
HISTSIZE=10000           # メモリに保存される履歴の件数
SAVEHIST=1000000         # 履歴ファイルに保存される履歴の件数

# 補完関連の設定
autoload -Uz compinit
compinit -u  # 補完を有効にする
setopt auto_list                  # 補完候補を一覧で表示する(d)
setopt auto_menu                  # 補完キー連打で補完候補を順に表示する(d)
setopt list_packed                # 補完候補をできるだけ詰めて表示する
setopt list_types                 # 補完候補にファイルの種類も表示する
bindkey "^[[Z" reverse-menu-complete  # Shift-Tabで補完候補を逆順する("\e[Z"でも動作する)
zstyle ':completion:*' matcher-list 'm:{a-z}={A-Z}' # 補完で大文字小文字区別しない
zstyle ':completion:*' ignore-parents parent pwd .. # ../ の後はcurrentdirectoryを補完しない
# sudo の後ろでコマンドを補完する
zstyle ':completion:*:sudo:*' command-path /usr/local/sbin /usr/local/bin \
    /usr/sbin /usr/bin /sbin /bin /usr/X11R6/bin

# 色の設定
autoload -Uz colors; colors # 色を使えるようにする

## プロンプトの設定
local p_mark="%B%(?,%F{white},%F{red})%(!,#,%%)%f%b"
PROMPT="${fg[magenta]}%* ${reset_color}> ${fg[cyan]}%~${reset_color}
$p_mark "

# export LSCOLORS=Exfxcxdxbxegedabagacad # 色の設定
# export LS_COLORS='di=01;34:ln=01;35:so=01;32:ex=01;31:bd=46;34:cd=43;34:su=41;30:sg=46;30:tw=42;30:ow=43;30'

# export DIRCOLORS_FILE=$HOME/.zplug/repos/seebi/dircolors-solarized/dircolors.ansi-dark

if [ -f "$DIRCOLORS_FILE" ]; then
    if type dircolors > /dev/null 2>&1; then
        eval $(dircolors $DIRCOLORS_FILE)
    elif type gdircolors > /dev/null 2>&1; then
        eval $(gdircolors $DIRCOLORS_FILE)
    fi
fi

[ -n "$LS_COLORS" ] && zstyle ':completion:*:default' list-colors ${(s.:.)LS_COLORS}

export ZLS_COLORS=$LS_COLORS
export CLICOLOR=true # lsに色を付ける

# オプション
setopt print_eight_bit

setopt auto_pushd
setopt pushd_ignore_dups
setopt share_history
setopt hist_ignore_all_dups
setopt hist_reduce_blanks
setopt hist_ignore_space
setopt extended_history
setopt correct
setopt no_beep
setopt complete_aliases

# ターミナルのタイトルを USER@HOSTNAME: CURRENT_DIR にする
case $TERM in
  xterm*)
    precmd () {print -Pn "\e]0;%n@%m: %~\a"}
    ;;
esac

# load .zshrc_*
[ -f $HOME/.zshrc_`uname` ] && . $HOME/.zshrc_`uname`
[ -f $HOME/.zshrc_local ] && . $HOME/.zshrc_local
