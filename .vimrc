" 基本設定
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

NeoBundleFetch 'Shougo/neobundle.vim'
NeoBundle 'Shougo/unite.vim'
NeoBundle 'ujihisa/unite-colorscheme'
NeoBundle 'nanotech/jellybeans.vim'
NeoBundle 'itchyny/lightline.vim'
NeoBundle 'Shougo/neocomplete.vim'
NeoBundle 'ujihisa/neco-look'
NeoBundle 'tpope/vim-surround'
NeoBundle 'mattn/emmet-vim'
NeoBundle 'othree/html5.vim'
NeoBundle 'hail2u/vim-css3-syntax'
NeoBundle 'gorodinskiy/vim-coloresque'
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
NeoBundle 'scrooloose/nerdtree'
NeoBundle 'cohama/vim-hier'
NeoBundle 'dannyob/quickfixstatus'
NeoBundle 'tyru/caw.vim'
NeoBundle 'Shougo/unite-outline'
NeoBundle 'motemen/hatena-vim'
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

" lightlineの設定
let g:lightline = {
            \ 'colorscheme': 'wombat',
            \ 'separator': { 'left': '⮀', 'right': '⮂' },
            \ 'subseparator': { 'left': '⮁', 'right': '⮃' }
            \ }

" neocompleteの設定
" Disable AutoComplPop.
let g:acp_enableAtStartup = 0
" Use neocomplete.
let g:neocomplete#enable_at_startup = 1
" Use smartcase.
let g:neocomplete#enable_smart_case = 1
" Set minimum syntax keyword length.
let g:neocomplete#sources#syntax#min_keyword_length = 3
let g:neocomplete#lock_buffer_name_pattern = '\*ku\*'

" Define dictionary.
let g:neocomplete#sources#dictionary#dictionaries = {
            \ 'default' : '',
            \ 'vimshell' : $HOME.'/.vimshell_hist',
            \ 'scheme' : $HOME.'/.gosh_completions'
            \ }

" Define keyword.
if !exists('g:neocomplete#keyword_patterns')
    let g:neocomplete#keyword_patterns = {}
endif
let g:neocomplete#keyword_patterns['default'] = '\h\w*'

" Plugin key-mappings.
inoremap <expr><C-g>     neocomplete#undo_completion()
inoremap <expr><C-l>     neocomplete#complete_common_string()

" Recommended key-mappings.
" <CR>: close popup and save indent.
inoremap <silent> <CR> <C-r>=<SID>my_cr_function()<CR>
function! s:my_cr_function()
    return neocomplete#close_popup() . "\<CR>"
    " For no inserting <CR> key.
    "return pumvisible() ? neocomplete#close_popup() : "\<CR>"
endfunction
" <TAB>: completion.
inoremap <expr><TAB>  pumvisible() ? "\<C-n>" : "\<TAB>"
" <C-h>, <BS>: close popup and delete backword char.
inoremap <expr><C-h> neocomplete#smart_close_popup()."\<C-h>"
inoremap <expr><BS> neocomplete#smart_close_popup()."\<C-h>"
inoremap <expr><C-y>  neocomplete#close_popup()
inoremap <expr><C-e>  neocomplete#cancel_popup()
" Close popup by <Space>.
"inoremap <expr><Space> pumvisible() ? neocomplete#close_popup() : "\<Space>"

" AutoComplPop like behavior.
"let g:neocomplete#enable_auto_select = 1

" Enable omni completion.
autocmd FileType css setlocal omnifunc=csscomplete#CompleteCSS
autocmd FileType html,markdown setlocal omnifunc=htmlcomplete#CompleteTags
autocmd FileType javascript setlocal omnifunc=javascriptcomplete#CompleteJS
autocmd FileType python setlocal omnifunc=pythoncomplete#Complete
autocmd FileType xml setlocal omnifunc=xmlcomplete#CompleteTags

" Enable heavy omni completion.
if !exists('g:neocomplete#sources#omni#input_patterns')
    let g:neocomplete#sources#omni#input_patterns = {}
endif
"let g:neocomplete#sources#omni#input_patterns.php = '[^. \t]->\h\w*\|\h\w*::'
"let g:neocomplete#sources#omni#input_patterns.c = '[^.[:digit:] *\t]\%(\.\|->\)'
"let g:neocomplete#sources#omni#input_patterns.cpp = '[^.[:digit:] *\t]\%(\.\|->\)\|\h\w*::'
let g:neocomplete#sources#omni#input_patterns.perl = '\h\w*->\h\w*\|\h\w*::'

" emmet-vimの設定
"" html lang=ja
let g:user_emmet_settings = {
            \ 'variables' : {
            \   'lang' : 'ja'
            \ }
            \ }

" Syntasticの設定
"" 公式のおすすめ設定丸パクリ
set statusline+=%#warningmsg#
set statusline+={SyntasticStatuslineFlag()}
set statusline+=%*
let g:syntastic_always_populate_loc_list = 1
let g:syntastic_auto_loc_list = 1
let g:syntastic_check_on_open = 1
let g:syntastic_check_on_wq = 0
"" HTML5
let g:syntastic_html_tidy_exec = 'tidy5'

" vim-refの設定
"" vim-refのバッファをqで閉じれるようにする
autocmd FileType ref-* nnoremap <buffer> <silent> q :<C-u>close<CR>
"" 辞書定義
let g:ref_source_webdict_sites = {
            \   'je': {
            \     'url': 'http://dictionary.infoseek.ne.jp/jeword/%s',
            \   },
            \   'ej': {
            \     'url': 'http://dictionary.infoseek.ne.jp/ejword/%s',
            \   },
            \   'wiki': {
            \     'url': 'http://ja.wikipedia.org/wiki/%s',
            \   },
            \ }
"" デフォルトサイト
let g:ref_source_webdict_sites.default = 'ej'
"" 出力に対するフィルタ
"" 最初の数行を削除
function! g:ref_source_webdict_sites.je.filter(output)
    return join(split(a:output, "\n")[15 :], "\n")
endfunction
function! g:ref_source_webdict_sites.ej.filter(output)
    return join(split(a:output, "\n")[15 :], "\n")
endfunction
function! g:ref_source_webdict_sites.wiki.filter(output)
    return join(split(a:output, "\n")[17 :], "\n")
endfunction

" ecitetranslate-vimの設定
"" 開いたバッファを q で閉じれるようにする
autocmd BufEnter ==Translate==\ Excite nnoremap <buffer> <silent> q :<C-u>close<CR>

" quickrun.vimの設定
let g:quickrun_config = {
            \   "_" : {
            \       "hook/close_unite_quickfix/enable_hook_loaded" : 1,
            \       "hook/unite_quickfix/enable_failure" : 1,
            \       "hook/close_quickfix/enable_exit" : 1,
            \       "hook/close_buffer/enable_failure" : 1,
            \       "hook/close_buffer/enable_empty_data" : 1,
            \       "runner" : "vimproc",
            \       "runner/vimproc/updatetime" : 60,
            \       "outputter" : "multi:buffer:quickfix",
            \       "outputter/buffer/split" : ":botright 8sp",
            \   },
            \}
" caw.vimの設定
nmap <C-K> <Plug>(caw:i:toggle)
vmap <C-K> <Plug>(caw:i:toggle)

" easymotionの設定
nmap s <Plug>(easymotion-s2)

" vim-textmanipの設定
xmap <Space>d <Plug>(textmanip-duplicate-down)
nmap <Space>d <Plug>(textmanip-duplicate-down)
xmap <Space>D <Plug>(textmanip-duplicate-up)
nmap <Space>D <Plug>(textmanip-duplicate-up)

xmap <C-j> <Plug>(textmanip-move-down)
xmap <C-k> <Plug>(textmanip-move-up)
xmap <C-h> <Plug>(textmanip-move-left)
xmap <C-l> <Plug>(textmanip-move-right)

" toggle insert/replace with <F10>
nmap <F10> <Plug>(textmanip-toggle-mode)
xmap <F10> <Plug>(textmanip-toggle-mode)

" GUN道
nnoremap <F5> :GundoToggle<CR>
call neobundle#end()

" tagbar
nnoremap <F8> :TagbarToggle<CR> 

" indentLine
let g:indentLine_color_term = 239 
let g:indentLine_char = '▸'

" Plugin key-mappings.
imap <C-k>     <Plug>(neosnippet_expand_or_jump)
smap <C-k>     <Plug>(neosnippet_expand_or_jump)
" xmap <C-k>     <Plug>(neosnippet_expand_target)

" SuperTab like snippets behavior.
imap <expr><TAB> neosnippet#expandable_or_jumpable() ?
            \ "\<Plug>(neosnippet_expand_or_jump)"
            \: pumvisible() ? "\<C-n>" : "\<TAB>"
smap <expr><TAB> neosnippet#expandable_or_jumpable() ?
            \ "\<Plug>(neosnippet_expand_or_jump)"
            \: "\<TAB>"

" For snippet_complete marker.
if has('conceal')
    set conceallevel=2 concealcursor=i
endif

filetype on
filetype plugin indent on
NeoBundleCheck

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
" INSERT中にCtrl+[を入力した場合はESCとみなす
inoremap <C-[> <ESC>
" ESC2回押すことでハイライトを消す
nmap <silent> <ESC><ESC> :nohlsearch<CR>
" :と;を入れ替える
noremap ; :
noremap : ;
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
" 補完
inoremap {} {}<Left>
inoremap [] []<Left>
inoremap () ()<Left>
inoremap "" ""<Left>
inoremap '' ''<Left>
inoremap <> <><Left>

set clipboard=unnamed,autoselect
set ambiwidth=double
set list
set listchars=eol:¬

" 無限undo
if has('persistent_undo')
    set undodir=~/.vim/undo
    set undofile
endif

" 編集位置の自動修復
au BufReadPost * if line("'\"") > 1 && line("'\"") <= line("$") | exe "normal! g`\""

