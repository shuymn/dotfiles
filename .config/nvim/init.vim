if &compatible
  set nocompatible
endif

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

function! s:load(file) abort
  let s:path = expand('$CONFIG/nvim/rc/' . a:file . '.vim')

  if filereadable(s:path)
    source `=s:path`
  endif
endfunction

call s:load('plugins')
call s:load('providers')

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

let s:backup_dir = expand('$CACHE/.vim')
if !isdirectory(s:backup_dir)
  call mkdir(expand(s:backup_dir), 'p')
endif

let &directory = s:backup_dir
let &backupdir = s:backup_dir
set swapfile backup

if has('persistent_undo')
  let &undodir = s:backup_dir
  set undofile
endif

noremap ; :
noremap : ;

nnoremap j gj
nnoremap k gk
nnoremap <CR> o<Esc>
nnoremap <silent> <Esc><Esc> :<C-u>set nohlsearch<Return>
nnoremap <Space> <Nop>
nnoremap <Space>h ^
nnoremap <Space>l $

autocmd vimrc BufRead * if line("'\"") > 0 && line("'\"") <= line("$") | exe "normal g`\"" | endif

autocmd vimrc Filetype * setlocal formatoptions-=ro
