" ============================================================
" 基本設定
" ============================================================
set number       " 行番号を表示する
set ruler        " 右下に表示される行、列の番号を表示する
set title        " 編集中のファイル名を表示
set showmatch    " 括弧入力時の対応する括弧を表示
set matchtime=5  " 対応括弧の表示秒数を5秒にする
set wrap         " ウィンドウの幅より長い行は折り返して次の行に表示する
set history=1024 " コマンド、検索パターンを1024個まで履歴に残す
set showcmd      " コマンドを画面最下部に表示する
set showmode     " モードを最終行に表示する
set laststatus=2 " 最終行のステータスラインを2行にする
set cursorline   " カーソル行をハイライトする
set noshowmode

" ============================================================
" タブ、インデント関連
" ============================================================
set smarttab     " 行頭の余白内でTabを打ち込むと、'shiftwidth'の数だけインデントする
set expandtab    " タブの代わりに空白文字を挿入する
set tabstop=4    " ファイル内の<Tab>が対応する空白の数
set shiftwidth=4
set autoindent   " 1つ前の行に基づくインデント
set smartindent  " 改行時に入力された行の末尾に合わせて次の行のインデントを増減させる

" ============================================================
" 検索関連
" ============================================================
set incsearch    " インクリメタルサーチを行う
set hlsearch     " 結果をハイライト表示
set ignorecase   " 大文字と小文字の区別なく検索する
set smartcase    " ただし大文字も含めた検索の場合はそのとおりに検索する

" ============================================================
" カラー関連
" ============================================================
syntax enable    " コードの色付け
set t_Co=256 
set background=dark
let g:hybrid_use_Xresources = 1
colorscheme hybrid

" ============================================================
" 入力関連
" ============================================================
" 左右のカーソル移動で行間移動が可能になる
set whichwrap=b,s,<,>,[,]
" INSERT中にCtrl+[を入力した場合はESCとみなす
inoremap <C-[> <ESC>
" ESC2回押すことでハイライトを消す
nnoremap <Esc><Esc> :<C-u>set nohlsearch<Return>
" :と;を入れ替える
noremap ; :
noremap : ;
" 表示行単位で行移動する
nnoremap <silent> j gj
nnoremap <silent> k gk
" 改行時にコメントしない¬
autocmd Filetype * setlocal formatoptions-=ro
" 空行を挿入する
nnoremap <CR> o<Esc>

" ============================================================
" キーマッピング
" ============================================================
" INSERTモードでの移動
inoremap <M-J> <Down>
inoremap <M-K> <Up>
inoremap <M-H> <Left>
inoremap <M-L> <Right>
" 矢印キーを使えないようにする
noremap <Up> <Nop>
noremap <Down> <Nop>
noremap <Left> <Nop>
noremap <Right> <Nop>
inoremap <Up> <Nop>
inoremap <Down> <Nop>
inoremap <Right> <Nop>
" 操作ミス防止
nnoremap ZZ <Nop>
nnoremap ZQ <Nop>
nnoremap Q <Nop>
nnoremap <C-O> <Nop>
nnoremap <Space>h ^
nnoremap <Space>l $
nnoremap <Space>/ *
nnoremap <Space>m %
" helpはqで閉じる
autocmd FileType help nnoremap <buffer> <silent> q :<C-u>close<CR>

" ============================================================
" その他
" ============================================================
set clipboard=unnamed,autoselect
set ambiwidth=double
set list
set listchars=eol:¬

" 無限undo
if has('persistent_undo')
    set undodir=$HOME/.vim/undo
    set undofile
endif

" 編集位置の自動修復
au BufReadPost * if line("'\"") > 1 && line("'\"") <= line("$") | exe "normal! g`\""

