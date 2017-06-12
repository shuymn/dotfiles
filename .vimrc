"" filename: .vimrc
"" author:   shuymn
"" references:
"" http://myfuturesightforpast.blogspot.jp/2015/11/neobundlevim.html

"" constant variable
let s:FALSE = 0
let s:TRUE = !s:FALSE

"" platform
let s:is_windows = has('win16') || has('win32') || has('win64')
let s:is_cygwin = has('win32unix')
let s:is_mac = has('mac') || has('macunix') || has('gui_macvim')
let s:is_linux = has('unix') && !s:is_mac && !s:is_cygwin

"" Charset, Line ending
set encoding=utf-8
scriptencoding utf-8
set fileencodings=ucs-bom,iso-2022-jp,utf-8,euc-jp,cp932,sjis
set fileformats=unix,dos,mac
set fileencoding=utf-8

"" Windowsのコマンドプロンプトの文字化け対策
if s:is_windows
  set termencoding=cp932
  set runtimepath^=~/.vim/
else
  set termencoding=utf-8
endif

set ambiwidth=double

autocmd BufReadPost *
      \   if &modifiable && !search('[^\x00-\x7F]', 'cnw')
      \ |   setlocal fileencoding=
      \ | endif
"" 文字エンコーディングUTF-16の時はbombをつける
autocmd BufWritePre *
      \ | if &fileencoding =~? 'utf-16*'
        \ |   setlocal bomb
        \ | endif

" dein
if &compatible
  set nocompatible
endif

set runtimepath+=~/.vim/dein/repos/github.com/Shougo/dein.vim

call dein#begin('~/.vim/dein')

call dein#add('Shougo/dein.vim')
call dein#add('Shougo/neosnippet.vim')
call dein#add('Shougo/neosnippet-snippets')
call dein#add('Shougo/neocomplete')
call dein#add('Shougo/vimproc.vim', {'build' : 'make'})
call dein#add('chriskempson/base16-vim')
call dein#add('kana/vim-fakeclip.git')
call dein#add('tmux-plugins/vim-tmux')
call dein#add('justmao945/vim-clang')
call dein#add('Shougo/neoinclude.vim')
call dein#add('Shougo/context_filetype.vim')
call dein#add('ujihisa/neco-look')
call dein#add('itchyny/lightline.vim')
call dein#add('godlygeek/tabular')
call dein#add('plasticboy/vim-markdown')
call dein#add('thinca/vim-quickrun')
call dein#add('cohama/lexima.vim')
call dein#add('KeitaNakamura/tex-conceal.vim')

call dein#end()

filetype plugin indent on
syntax enable

if dein#check_install()
  call dein#install()
endif

" ---------------------------------------------------------------------------
" neocomplete
"" Disable AutoComplPop.
let g:acp_enableAtSetup = 0
"" Use neocomplete.
let g:neocomplete#enable_at_startup = 1
"" 大文字が入力されるまで大文字小文字の区別を無視する
let g:neocomplete#enable_smart_case = 1
"" シンタックスをキャッシュするときの最小文字長
let g:neocomplete#sources#syntax#min_keyword_length = 3
"" 補完を表示する最小文字数
let g:neocomplete#auto_completion_start_length = 2
"" アンダーバー区切りの補完を有効化
let g:neocomplete#enable_underbar_completion = 1
let g:neocomplete#enable_caml_case_completion = 1
"" ポップアップメニューで表示される候補数
let g:neocomplete#max_list = 10
""
let g:neocomplete#max_keyword_width = 10000

"" keymap
inoremap <expr><C-g>  neocomplete#undo_completion()
inoremap <expr><C-l>  neocomplete#complete_common_string()

" <CR>: close popup and save indent.
inoremap <silent> <CR> <C-r>=<SID>my_cr_function()<CR>
function! s:my_cr_function()
  return (pumvisible() ? "\<C-y>" : "" ) . "\<CR>"
endfunction
" <TAB>: completion.
inoremap <expr><TAB> pumvisible() ? "\<C-n>" : "\<TAB>"
" <C-h>, <BS>: close popup and delete backword char.
inoremap <expr><C-h> neocomplete#smart_close_popup()."\<C-h>"

" Enable omni completion.
autocmd FileType css setlocal omnifunc=csscomplete#CompleteCSS
autocmd FileType html,markdown setlocal omnifunc=htmlcomplete#CompleteTags
autocmd FileType javascript setlocal omnifunc=javascriptcomplete#CompleteJS
autocmd FileType python setlocal omnifunc=pythoncomplete#Complete
autocmd FileType xml setlocal omnifunc=xmlcomplete#CompleteTags

noremap <expr><BS> neocomplete#smart_close_popup()."\<C-h>"

if !exists('g:neocomplete#force_omni_input_patterns')
  let g:neocomplete#force_omni_input_patterns = {}
endif
let g:neocomplete#force_overwrite_completefunc = 1
let g:neocomplete#force_omni_input_patterns.c =
      \ '[^.[:digit:] *\t]\%(\.\|->\)\w*'
let g:neocomplete#force_omni_input_patterns.cpp =
      \ '[^.[:digit:] *\t]\%(\.\|->\)\w*\|\h\w*::\w*'

"" vim-clang
let g:clang_c_options = '-std=c11'
let g:clang_cpp_options = '-std=c++11 -stdlib=libc++'

"" lightline
let g:lightline = {
      \ 'colorscheme': 'wombat',
      \ 'mode_map': {
      \   'n': 'N',
      \   'i': 'I',
      \   'R': 'R',
      \   'v': 'V',
      \   'V': 'V-L',
      \   "\<C-v>": 'V-B'
      \   }
      \ }

" vim-markdown
autocmd BufRead,BufNewFile *.{mkd,md} set filetype=markdown
autocmd! FileType markdown hi! def link markdownItalic Normal
autocmd FileType markdown set commentstring=<\!--\ %s\ -->

" for plasticboy/vim-markdown
let g:vim_markdown_folding_disabled = 1
let g:vim_markdown_no_default_key_mappings = 1
let g:vim_markdown_math = 1
let g:vim_markdown_frontmatter = 1
let g:vim_markdown_toc_autofit = 1
let g:vim_markdown_folding_style_pythonic = 1

" quickrun
let g:quickrun_config = get(g:, 'quickrun_config', {})
let g:quickrun_config._ = {
      \ 'runner'    : 'vimproc',
      \ 'runner/vimproc/updatetime' : 60,
      \ 'outputter' : 'error',
      \ 'outputter/error/success' : 'buffer',
      \ 'outputter/error/error'   : 'quickfix',
      \ 'outputter/buffer/split'  : ':rightbelow 10sp',
      \ 'outputter/buffer/close_on_empty' : 1,
      \ 'outputter/buffer/into' : 1,
      \ 'outputter/buffer/running_mark' : '',
      \ }

let g:quickrun_config.tex = { "command" : "autolatex" }

"" q で quickfixを閉じれるようにする
au FileType qf nnoremap <silent><buffer>q :quit<CR>

"" \r でquickfixを閉じて，保存してからquickrunを実行する
let g:quickrun_no_default_key_mappings = 1
nnoremap \r :cclose<CR>:write<CR>:QuickRun -mode n<CR>
xnoremap \r :<C-U>cclose<CR>:write<CR>gv:QuickRun -mode v<CR>

"" <C-c> でquickrun停止
nnoremap <expr><silent> <C-c> quickrun#is_running() ? quickrun#sweep_sessions() : "\<C-c>"

" lexima
call lexima#add_rule({'char': '$', 'input_after': '$', 'filetype': 'tex'})
call lexima#add_rule({'char': '$', 'at': '\%#\$', 'leave': 1, 'filetype': 'tex'})
call lexima#add_rule({'char': '<BS>', 'at': '\$\%#\$', 'delete': 1, 'filetype': 'tex'})
call lexima#add_rule({'char': "'", 'input_after': "", 'filetype': 'tex'})
call lexima#add_rule({'char': "'", 'at': "'\\%#", 'input_after': "", 'filetype': 'tex'})
call lexima#add_rule({'char': "'", 'at': "''\\%#", 'input_after': "", 'filetype': 'tex'})

" neosnippet
imap <C-k>     <Plug>(neosnippet_expand_or_jump)
smap <C-k>     <Plug>(neosnippet_expand_or_jump)
xmap <C-k>     <Plug>(neosnippet_expand_target)

smap <expr><TAB> neosnippet#expandable_or_jumpable() ?
\ "\<Plug>(neosnippet_expand_or_jump)" : "\<TAB>"

" tex-conceal
if has('conceal')
  set conceallevel=2
  let g:tex_conceal="adgmb"
  set concealcursor=""
endif

" ---------------------------------------------------------------------------
" 基本設定
set number       " 行番号を表示する
set ruler        " 右下に表示される行、列の番号を表示する
set title        " 編集中のファイル名を表示
set showcmd      " コマンドを画面最下部に表示する
set showmatch    " 括弧入力時の対応する括弧を表示
set showmode     " モードを最終行に表示する
set history=100 " コマンド、検索パターンを100個まで履歴に残す
set matchtime=5  " 対応括弧の表示秒数を5秒にする
set wrap         " ウィンドウの幅より長い行は折り返して次の行に表示する
set laststatus=2 " 最終行のステータスラインを2行にする

" カーソル行をハイライトする。neovimでない普通のvim(?)だとスクロールがもたつくのでneovimのみ↲
if has('nvim')
  set cursorline
endif

" backspaceキーの挙動を設定する
" indent    : 行頭の空白の削除を許す
" eol       : 改行の削除を許す
" start     : 挿入モードの開始位置での削除を許す
set backspace=indent,eol,start

" ---------------------------------------------------------------------------
" タブ、インデント関連
set smarttab     " 行頭の余白内でTabを打ち込むと、'shiftwidth'の数だけインデントする
set expandtab    " タブの代わりに空白文字を挿入する
set tabstop=2    " ファイル内の<Tab>が対応する空白の数
set shiftwidth=2 " cindentやautoindentの時に挿入されるタブの幅
set softtabstop=0 " Tabキー使用時にTabではなくスペースを入れる
set wrapscan      " 最後尾まで検索を終えたら先頭に戻って検索を続ける

set cindent
set textwidth=0
set autoindent   " 1つ前の行に基づくインデント
set smartindent  " 改行時に入力された行の末尾に合わせて次の行のインデントを増減させる

if !isdirectory(expand('~/.vim/tmp'))
  call mkdir(expand('~/.vim/tmp'),'p')
endif

set directory=~/.vim/tmp
set backupdir=~/.vim/tmp
set undodir=~/.vim/tmp

set swapfile  " swapファイルを生成する。↓ 保存ディレクトリ
set backup    " バックアップファイルを生成する。 ↓ 保存ディレクトリ
set undofile  " undo記録ファイルを生成する。 ↓ 保存ディレクトリ

set autoread  " 編集中のファイルが更新された時に自動でロードする
set hidden

set mouse=a

" :e でファイルを開くときのファイル名補完のやり方を設定
set wildignorecase
set wildmenu
set wildmode=list:longest,full

set scrolloff=6       " スクロール時上下に確保する行数
set sidescrolloff=15  " 左右スクロール時に確保する行数
set sidescroll=1      " 左右スクロールは1文字ずつ行う

" ---------------------------------------------------------------------------
" 検索関連
set incsearch    " インクリメタルサーチを行う
set hlsearch     " 結果をハイライト表示
set ignorecase   " 大文字と小文字の区別なく検索する
set smartcase    " ただし大文字も含めた検索の場合はそのとおりに検索する

" ---------------------------------------------------------------------------
" カラー関連
syntax enable
set background=dark

if filereadable(expand('~/.vim/colors/base16-monokai.vim'))
  "  colorscheme base16-monokai 
else
  colorscheme desert
endif

if &term == "cygwin"
  colorscheme desert
else
  set t_Co=256
endif

if filereadable(expand("~/.vimrc_background"))
  let base16colorspace=256
  source ~/.vimrc_background
endif

" ---------------------------------------------------------------------------
" 入力関連

" 左右のカーソル移動で行間移動が可能になる
set whichwrap=b,s,h,l,<,>,[,],~
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

" 一部フォーマットでの折り返し無効化
" http://qiita.com/noboru/items/5d7358000329a6adcbe5
autocmd BufRead,BufNewFile *.html set nowrap
autocmd BufRead,BufNewFile *.js set nowrap

" texの設定
au BufRead,BufNewFile *.tex set filetype=tex

" ---------------------------------------------------------------------------
" キーマッピング

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

" ---------------------------------------------------------------------------
" その他

" neovimでのエラーを回避
if !has('nvim')
  set clipboard=unnamed,autoselect
endif

set lcs=tab:›\ ,trail:␣,eol:↲,extends:»,precedes:«,nbsp:%
"set lcs=tab:>.,trail:_,eol:｣
set list " 不可視文字を表示

" 無限undo
if has('persistent_undo')
  set undodir=$HOME/.vim/tmp
  set undofile
endif

" 編集位置の自動修復
augroup vimrcEx/d
  au BufRead * if line("'\"") > 0 && line("'\"") <= line("$") |
        \ exe "normal g`\"" | endif
augroup END

" itermでカーソルをモードごとに変える
" http://qiita.com/itkrt2y/items/ead0250f037f2c79b3e7
let &t_SI = "\<Esc>Ptmux;\<Esc>\<Esc>]50;CursorShape=1\x7\<Esc>\\"
let &t_EI = "\<Esc>Ptmux;\<Esc>\<Esc>]50;CursorShape=0\x7\<Esc>\\"

if has('gui_macvim') && has('gui_running')
  " メニューバー非表示
  set guioptions-=m

  " ツールバー非表示
  set guioptions-=T

  " 左右のスクロールバー非表示
  set guioptions-=r
  set guioptions-=R
  set guioptions-=l
  set guioptions-=L

  " 水平スクロールバー非表示
  set guioptions-=b

  " font
  set guifont=Ricty\ Discord:h15
  " set guifontwide=Myrica_M:h15

  " カーソル行をハイライトする
  set cursorline

  " 起動時のウィンドウサイズ
  set lines=40
  set columns=130

  " Insert Modeで勝手にIMEがONになるのをやめる
  set iminsert=0
  set imsearch=-1

endif
