" 基本設定
filetype off     " ファイルタイプの自動検出をしないようにする
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

" NeoBundle
" Bundleで管理するディレクトリを指定
set runtimepath+=~/.vim/bundle/neobundle.vim

" required
call neobundle#begin(expand('~/.vim/bundle/'))

 NeoBundle 'Shougo/neobundle.vim'
 NeoBundle 'ujihisa/unite-colorscheme'
 NeoBundle 'nanotech/jellybeans.vim'
 NeoBundle 'itchyny/lightline.vim'
 NeoBundle 'scrooloose/nerdtree'

" lightlineの設定
let g:lightline = {
      \ 'colorscheme': 'wombat',
      \ 'separator': { 'left': '⮀', 'right': '⮂' },
      \ 'subseparator': { 'left': '⮁', 'right': '⮃' }
      \ }

call neobundle#end()

" タブ、インデント関連
set smarttab     " 行頭の余白内でTabを打ち込むと、'shiftwidth'の数だけインデントする
set expandtab    " タブの代わりに空白文字を挿入する
set tabstop=4    " ファイル内の<Tab>が対応する空白の数
set shiftwidth=4
set autoindent   " 1つ前の行に基づくインデント
set smartindent  " 改行時に入力された行の末尾に合わせて次の行のインデントを増減させる

" 検索関連
set incsearch    " インクリメタルサーチを行う
set hlsearch     " 結果をハイライト表示
set ignorecase   " 大文字と小文字の区別なく検索する
set smartcase    " ただし大文字も含めた検索の場合はそのとおりに検索する

" カラー関連
syntax enable    " コードの色付け
colorscheme jellybeans
set t_Co=256

" 入力関連
" 左右のカーソル移動で行間移動が可能になる
set whichwrap=b,s,<,>,[,]
" INSERT中に素早くasdfと入力した場合はESCとみなす
inoremap asdf <ESC>
" ESC2回押すことでハイライトを消す
nmap <silent> <ESC><ESC> :nohlsearch<CR>
" :と;を入れ替える
nnoremap ; :
nnoremap : ;
vnoremap ; :
vnoremap : ;
" 表示行単位で行移動する
nnoremap <silent> j gj
nnoremap <silent> k gk
" 行頭/行末移動のキーを変更
"nnoremap ^ " 行頭
"nnoremap $ " 行末
" 改行時にコメントしない¬
"autocmd Filetype * set formatoptions-=o¬
"autocmd Filetype * set formatoptions-=r¬
"set formatoptions-=ro
autocmd Filetype * setlocal formatoptions-=ro

" キーマッピング
" INSERTモードでの移動
inoremap <C-d> <Enter>
inoremap <C-b> <Backspace>
inoremap <C-e> <END>
inoremap <C-a> <HOME>
inoremap <C-j> <Down>
inoremap <C-k> <Up>
inoremap <C-h> <Left>
inoremap <C-l> <Right>

" 無限undo
if has('persistent_undo')
  set undodir=~/.vim/undo
  set undofile
endif

" 編集位置の自動修復
au BufReadPost * if line("'\"") > 1 && line("'\"") <= line("$") | exe "normal! g`\""

filetype on
