let s:dein_dir = expand('$CACHE/dein')

if &runtimepath !~# '/dein.vim'
  let s:dein_repo_dir = s:dein_dir . '/repos/github.com/Shougo/dein.vim'

  if !isdirectory(s:dein_repo_dir)
    execute '!git clone https://github.com/Shougo/dein.vim' s:dein_repo_dir
  endif

  let &runtimepath = s:dein_repo_dir . ',' . &runtimepath
endif

if !dein#load_state(s:dein_dir)
  finish
endif

let g:dein#auto_recache = v:true
let g:dein#install_message_type = 'title'
let g:dein#enable_notification = v:true

let s:dein_toml = expand('$CONFIG/nvim/rc/dein.toml')
let s:dein_lazy_toml = expand('$CONFIG/nvim/rc/dein-lazy.toml')

call dein#begin(s:dein_dir, [expand('<sfile>'), s:dein_toml, s:dein_lazy_toml])

call dein#load_toml(s:dein_toml, { 'lazy': 0 })
call dein#load_toml(s:dein_lazy_toml, { 'lazy': 1 })

call dein#end()
call dein#save_state()

if has('vim_starting') && dein#check_install()
  call dein#install()
endif

syntax on
filetype plugin indent on
