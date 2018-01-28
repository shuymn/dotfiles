if &compatible | set nocompatible | endif

" init
augroup vimrc
  autocmd!
augroup END

let $CACHE = expand('~/.cache')
if !isdirectory($CACHE) | call mkdir(expand($CACHE), 'p') | endif

"" vimrc splitting
set runtimepath+=~/.config/vim

"" disable packpath
set packpath=

" dein
let s:dein_dir = expand('$CACHE/dein') . '/repos/github.com/Shougo/dein.vim'
if !isdirectory(s:dein_dir) | execute '!git clone https://github.com/Shougo/dein.vim' s:dein_dir | endif
let &runtimepath = s:dein_dir . ',' . &runtimepath

let s:path = expand('$CACHE/dein')
if dein#load_state(s:path)
  call dein#begin(s:path)

  call dein#load_toml('~/.config/vim/dein.toml', {'lazy': 0})
  call dein#load_toml('~/.config/vim/dein_lazy.toml', {'lazy': 1})

  call dein#end()
  call dein#save_state()

  if dein#check_install() | call dein#install() | endif
endif

syntax enable
filetype plugin indent on

" Encoding
set encoding=utf-8 fileencoding=utf-8 fileformats=unix,dos,mac
set fileencodings=utf-8,iso-2022-jp,euc-jp,sjis


" Appearance
set number ruler title wrap cursorline
set showcmd showmatch noshowmode laststatus=2
set history=100
set matchtime=5

"" colorscheme
runtime! color.rc.vim

" Editing
set autoindent smartindent
set backspace=indent,eol,start textwidth=0 ambiwidth=double
set smarttab expandtab tabstop=2 shiftwidth=2 softtabstop=0
set wrapscan
set whichwrap=b,s,h,l,<,>,[,],~
set lcs=tab:›\ ,trail:␣,eol:↲,extends:»,precedes:«,nbsp:% list
set incsearch hlsearch ignorecase smartcase
set wildignorecase wildmenu wildmode=list:longest,full
set mouse=a autoread hidden

set clipboard=unnamed,unnamedplus

" File backup
let s:backup_dir = expand('$CACHE/.vim')
if !isdirectory(s:backup_dir) | call mkdir(expand(s:backup_dir), 'p') | endif

let &directory = s:backup_dir
let &backupdir = s:backup_dir
set swapfile backup

if has('persistent_undo')
  let &undodir = s:backup_dir
  set undofile
endif

" Key mappings
noremap ; :
noremap : ;

nnoremap j gj
nnoremap k gk
nnoremap <CR> o<Esc>
nnoremap <silent> <Esc><Esc> :<C-u>set nohlsearch<Return>
nnoremap <Space> <Nop>
nnoremap <Space>h ^
nnoremap <Space>l $

" Auto commands
"" 編集位置を記憶
autocmd vimrc BufRead * if line("'\"") > 0 && line("'\"") <= line("$") | exe "normal g`\"" | endif

"" 改行するときにコメントを入れない
autocmd vimrc Filetype * setlocal formatoptions-=ro
