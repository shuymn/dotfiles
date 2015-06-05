" ============================================================
" NeoBundle
" ============================================================
if has('vim_starting')
    if &compatible
        set nocompatible
    endif
    set runtimepath+=~/.vim/bundle/neobundle.vim
endif

" required
call neobundle#begin(expand('~/.vim/bundle/'))

NeoBundleFetch 'Shougo/neobundle.vim'
NeoBundle 'Shougo/unite.vim'
NeoBundle 'ujihisa/unite-colorscheme'
NeoBundle 'nanotech/jellybeans.vim'
NeoBundle 'jpo/vim-railscasts-theme'
NeoBundle 'w0ng/vim-hybrid'
NeoBundle 'itchyny/lightline.vim'
NeoBundle 'Shougo/neocomplete.vim'
NeoBundle 'ujihisa/neco-look'
NeoBundle 'tpope/vim-surround'
NeoBundleLazy 'mattn/emmet-vim', {
            \ 'autoload': {
            \ 'filetypes': ['html', 'css'],
            \   }
            \ }
NeoBundleLazy 'othree/html5.vim', {
            \ 'autoload': {
            \ 'filetypes': ['html', 'css'],
            \   }
            \ }
NeoBundleLazy 'hail2u/vim-css3-syntax', {
            \ 'autoload': {
            \ 'filetypes': ['html', 'css'],
            \   }
            \ }
NeoBundleLazy 'gorodinskiy/vim-coloresque', {
            \ 'autoload': {
            \ 'filetypes': ['html', 'css'],
            \   }
            \ }
NeoBundle 'scrooloose/syntastic'
NeoBundle 'thinca/vim-ref'
NeoBundle 'mfumi/ref-dicts-en'
NeoBundle 'mattn/webapi-vim'
NeoBundle 'mattn/excitetranslate-vim'
NeoBundle 'Shougo/vimproc.vim', {
            \ 'build' : {
            \     'windows' : 'tools\\update-dll-mingw',
            \     'cygwin' : 'make -f make_cygwin.mak',
            \     'mac' : 'make -f make_mac.mak',
            \     'linux' : 'make',
            \     'unix' : 'gmake',
            \    },
            \ }
NeoBundle 'Shougo/vimshell'
NeoBundle 'h1mesuke/vim-alignta'
NeoBundle 'thinca/vim-quickrun'
NeoBundle 'osyo-manga/unite-quickfix'
NeoBundle 'osyo-manga/shabadou.vim'
"NeoBundle 'osyo-manga/vim-watchdogs'
NeoBundle 'cohama/vim-hier'
NeoBundle 'dannyob/quickfixstatus'
NeoBundle 'tyru/caw.vim'
NeoBundle 'Shougo/unite-outline'
NeoBundle 'Lokaltog/vim-easymotion'
NeoBundle 't9md/vim-textmanip'
NeoBundle 'vim-scripts/DrawIt'
NeoBundle 'sjl/gundo.vim'
NeoBundle 'tyru/open-browser.vim'
NeoBundle 'ujihisa/unite-locate'
NeoBundle 'osyo-manga/vim-over'
NeoBundle 'Shougo/neosnippet.vim'
NeoBundle 'Shougo/neosnippet-snippets'
NeoBundle 'vim-jp/vimdoc-ja'
NeoBundle 'majutsushi/tagbar'
NeoBundle 'Yggdroot/indentLine'
NeoBundle 'cohama/agit.vim'
NeoBundle 'Shougo/vimfiler.vim'
NeoBundle 'tpope/vim-fugitive'
NeoBundle 'airblade/vim-gitgutter'
NeoBundle 'Shougo/neomru.vim'
NeoBundle 'kana/vim-submode'
NeoBundle 'tmhedberg/matchit'
NeoBundle 'tpope/vim-repeat'
NeoBundle 'lambdalisue/vim-gista', {
            \ 'depends': [
            \   'Shougo/unite.vim',
            \   'tyru/open-browser.vim',
            \]}
NeoBundle 'moznion/hateblo.vim'
NeoBundle 'marcus/rsense'
NeoBundle 'supermomonga/neocomplete-rsense.vim'
NeoBundle 'yuku-t/vim-ref-ri'
NeoBundle 'szw/vim-tags'
NeoBundle 'tpope/vim-endwise'
NeoBundle 'superbrothers/vim-vimperator'

call neobundle#end()
filetype plugin indent on
NeoBundleCheck
