if exists('g:loaded_vimrc') || &compatible
  finish
else
  let g:loaded_vimrc = v:true
endif

" disable vi defaults
set nocompatible

" reset augroup
augroup vimrc
  autocmd!
augroup END

let $CACHE = empty($XDG_CACHE_HOME) ? expand('$HOME/.cache') : $XDG_CACHE_HOME
if !isdirectory($CACHE)
  call mkdir(expand($CACHE), 'p')
endif

let $CONFIG = empty($XDG_CONFIG_HOME) ? expand('$HOME/.config') : $XDG_CONFIG_HOME
if !isdirectory($CONFIG)
  call mkdir(expand($CONFIG), 'p')
endif

" disable packpath
set packpath=

set shell=/bin/zsh

" encoding
set encoding=utf-8 fileencoding=utf-8 fileformats=unix,dos,mac
set fileencodings=utf-8,iso-2022-jp,euc-jp,sjis

" appearance
set number ruler title wrap cursorline
set showcmd showmatch noshowmode laststatus=2
set history=100
set matchtime=5

set autoindent smartindent
set backspace=indent,eol,start textwidth=0 ambiwidth=double
set smarttab expandtab tabstop=2 shiftwidth=2 softtabstop=0
set wrapscan
set whichwrap=b,s,h,l,<,>,[,],~
set incsearch hlsearch ignorecase smartcase
set wildignorecase wildmenu wildmode=list:longest,full
set mouse=a autoread hidden

set clipboard=unnamed,unnamedplus

if &t_Co >= 256
  set termguicolors
end

let s:cache_dir = expand('$CACHE/.vim')
if !isdirectory(s:cache_dir)
  call mkdir(expand(s:cache_dir), 'p')
endif

let &directory = s:cache_dir
set swapfile

if has('persistent_undo')
  let &undodir = s:cache_dir
  set undofile
endif

function! s:load(file) abort
  let s:path = expand('$CONFIG/nvim/rc/' . a:file . '.rc.vim')

  if filereadable(s:path)
    source `=s:path`
  endif
endfunction

call s:load('dein')
call s:load('providers')

let mapleader = "\<Space>"

noremap ; :
noremap : ;

nnoremap j gj
nnoremap k gk
nnoremap H B
nnoremap J <C-d>
nnoremap K <C-u>
nnoremap L W
nnoremap <C-j> :<C-u>tabprevious<CR>
nnoremap <C-k> :<C-u>tabnext<CR>

nnoremap <CR> o<Esc>
nnoremap <silent> <Esc><Esc> :<C-u>set nohlsearch<Return>

nnoremap <Space> <Nop>
nnoremap <Space>h ^
nnoremap <Space>l $
nnoremap d<Space>h d^
nnoremap d<Space>l d$

vnoremap x "_x
nnoremap x "_x

nnoremap <C-w>w <Nop>
nnoremap <C-w><C-w> <Nop>
nnoremap <C-w>+ <Nop>
nnoremap <C-w>- <Nop>
nnoremap <C-w>> <Nop>
nnoremap <C-w>< <Nop>
nnoremap <C-w>h <C-w><
nnoremap <C-w>j <C-w>-
nnoremap <C-w>k <C-w>+
nnoremap <C-w>l <C-w>>

autocmd vimrc BufRead * if line("'\"") > 0 && line("'\"") <= line("$") | exe "normal g`\"" | endif
