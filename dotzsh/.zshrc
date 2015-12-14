# 環境変数
export EDITOR=vim        # エディタをvimに設定
export LANG=en_US.UTF-8  # 文字コードをUTF-8に設定
export KCODE=u           # KCODEにUTF-8を設定

# 色を使う
autoload -Uz colors # 色を使えるようにする
colors

# ヒストリの設定
HISTFILE=~/.zsh_history
HISTSIZE=1000000
SAVEHIST=1000000

# 補完
autoload -Uz compinit # 補完機能を有効にする
compinit

setopt auto_list               # 補完候補を一覧で表示する(d)
setopt auto_menu               # 補完キー連打で補完候補を順に表示する(d)
setopt list_packed             # 補完候補をできるだけ詰めて表示する
setopt list_types              # 補完候補にファイルの種類も表示する
bindkey "^[[Z" reverse-menu-complete  # Shift-Tabで補完候補を逆順する("\e[Z"でも動作する)
zstyle ':completion:*' matcher-list 'm:{a-z}={A-Z}' # 補完で大文字小文字区別しない
zstyle ':completion:*' ignore-parents parent pwd .. # ../ の後はcurrentdirectoryを補完しない
# sudo の後ろでコマンドを補完する
zstyle ':completion:*:sudo:*' command-path /usr/local/sbin /usr/local/bin \
    /usr/sbin /usr/bin /sbin /bin /usr/X11R6/bin

export LSCOLORS=Exfxcxdxbxegedabagacad # 色の設定
# 補完候補に色を付ける設定
export LS_COLORS='di=01;34:ln=01;35:so=01;32:ex=01;31:bd=46;34:cd=43;34:su=41;30:sg=46;30:tw=42;30:ow=43;30'

if [ -f ~/.dircolors ]; then
    if type dircolors > /dev/null 2>&1; then
        eval $(dircolors ~/.dircolors)
    elif type gdircolors > /dev/null 2>&1; then
        eval $(gdircolors ~/.dircolors)
    fi
fi

export ZLS_COLORS=$LS_COLORS # ZLS_COLORSとは
export CLICOLOR=true # lsに色を付ける

if [ -n "$LS_COLORS" ]; then
    zstyle ':completion:*:default' list-colors ${(s.:.)LS_COLORS}
fi

# オプション
setopt print_eight_bit # 日本語ファイル名を表示可能にする

setopt auto_pushd # cd したら自動的にpushdする
setopt pushd_ignore_dups # 重複したディレクトリを作成しない
setopt share_history # 同時に起動したzshの間でヒストリを共有する
setopt hist_ignore_all_dups # 同じコマンドをヒストリに残さない
setopt hist_reduce_blanks # ヒストリに保存するときに余分なスペースは削除する
setopt hist_ignore_space # スペースから始まるコマンド行はヒストリに残さない
setopt extended_history   # ヒストリに実行時間も保存する
setopt correct           # コマンドのスペルを訂正する
setopt no_beep           # ビープ音を鳴らさないようにする


setopt complete_aliases
export PATH="$HOME/.gem/ruby/2.2.0/bin:$PATH"
alias tnsrb='cd ~/git/ruby/tanoshii-ruby/'
alias gaa='git add -A'
alias gcam='git commit -am'
alias gst='git status'
alias gpom='git push origin master'
alias v='vim'

# load .zshrc_*
[ -f $ZDOTDIR/.zshrc_`uname` ] && . $ZDOTDIR/.zshrc_`uname`
[ -f $ZDOTDIR/.zshrc_external ] && . $ZDOTDIR/.zshrc_external
[ -f $ZDOTDIR/.zshrc_local ] && . $ZDOTDIR/.zshrc_local
