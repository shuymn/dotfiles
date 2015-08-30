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
export ZLS_COLORS=$LS_COLORS # ZLS_COLORSとは
export CLICOLOR=true # lsに色を付ける
zstyle ':completion:*:default' list-colors ${(s.:.)LS_COLORS} # 補完候補に色を付ける

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

# powerline-shell
function powerline_precmd() {
PS1="$(~/.zsh/powerline-shell/powerline-shell.py $? --shell zsh 2> /dev/null)"
}

function install_powerline_precmd() {
for s in "${precmd_functions[@]}"; do
    if [ "$s" = "powerline_precmd" ]; then
        return
    fi
done
precmd_functions+=(powerline_precmd)
}

if [ "$TERM" != "linux" ]; then
    install_powerline_precmd
fi

setopt complete_aliases
export PATH="$HOME/.gem/ruby/2.2.0/bin:$PATH"
alias tnsrb='cd ~/git/ruby/tanoshii-ruby/'
alias gaa='git add -A'
alias gcam='git commit -am'
alias gst='git status'
alias gpom='git push origin master'
alias v='vim'

# OSごとに設定を分ける
case ${OSTYPE} in
    darwin*)
        # brewでインストールしたアプリのPATHを通す
        export PATH=/usr/local/bin:$PATH

        # enyenv
        if [ -d $HOME/.anyenv ] ; then
            export PATH="$HOME/.anyenv/bin:$PATH"
            eval "$(anyenv init -)"
        fi

        eval "$(pyenv init -)"

        # cdのあとにls
        function cd() {
        builtin cd $@ && gls -Fh --color;
    }
    # zsh + peco (on mac)で快適History生活
    function peco-history-selection() {
        BUFFER=`history -n 1 | tail -r | awk '!a[$0]++' | peco`
        CURSOR=$#BUFFER
        zle reset-prompt
        }

zle -N peco-history-selection
bindkey '^R' peco-history-selection

# alias
alias ls='gls -Fh --color'
alias rm='trash'
alias updatedb='sudo /usr/libexec/locate.updatedb'

# zsh-syntax-highlighting
source /usr/local/share/zsh-syntax-highlighting/zsh-syntax-highlighting.zsh

;;
linux*)
    # RVMのPATHを通す
    export PATH="$PATH:$HOME/.rvm/bin"

    # cdのあとにls
    function cd() {
    builtin cd $@ && ls -F --color=auto;
}

# alias
alias ls='ls -F --color=auto'
alias unzip='unzip -O CP932'
alias sl='ruby ~/Downloads/git/sl/sl.rb'
;;
esac
