"" filename: .vimrc
"" author:   shuymn

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
set fileencodings=ucs-bom,iso-2022-jp,utf-8,euc-jp,cp932
set fileformats=unix,dos,mac

"" Windowsのコマンドプロンプトの文字化け対策
if s:is_windows
    set termencoding=cp932
endif

set ambiwidth=double " 全角記号をきちんと表示

autocmd BufReadPost *
            \   if &modifiable && !search('[^\x00-\x7F]', 'cnw')
            \ |   setlocal fileencoding=
            \ | endif
"" 文字エンコーディングUTF-16の時はbombをつける
autocmd BufWritePre *
            \ | if &fileencoding =~? 'utf-16*'
                \ |   setlocal bomb
                \ | endif

" ---------------------------------------------------------------------------
" Plugin Install (Using NeoBundle)

if has('vim_starting')
    set runtimepath+=~/.vim/bundle/neobundle.vim
endif

let s:is_neobundle_installed = s:TRUE
try " specify plugin installation base directory.
    call neobundle#begin(expand('~/.vim/bundle/'))
catch /^Vim\%((\a\+)\)\=:E117/ " catch error E117: Unkown function
    let s:is_neobundle_installed = s:FALSE
    set title titlestring=NeoBundle\ is\ not\installed!
endtry

if s:is_neobundle_installed
    NeoBundleFetch 'Shougo/neobundle.vim'

    if has("lua")
        NeoBundle 'Shougo/neocomplete'
    else
        NeoBundle 'Shougo/neocomplcache'
    endif

    "" neo系
    NeoBundle 'Shougo/neosnippet.vim'
    NeoBundle 'Shougo/neosnippet-snippets'
    NeoBundle 'Shougo/neomru.vim'
    NeoBundle 'ujihisa/neco-look'
    NeoBundle 'supermomonga/neocomplete-rsense.vim'
    NeoBundle 'Shougo/context_filetype.vim'
    NeoBundle 'Shougo/neco-syntax'

    "" color scheme 
    NeoBundle 'nanotech/jellybeans.vim'
    NeoBundle 'jpo/vim-railscasts-theme'
    NeoBundle 'w0ng/vim-hybrid'


    NeoBundle 'itchyny/lightline.vim'

    "" unite系
    NeoBundle 'Shougo/vimfiler', {'depends': 'Shougo/unite.vim'}
    NeoBundle 'ujihisa/unite-colorscheme'
    NeoBundle 'Shougo/unite-outline'

    if executable('make') && executable('gcc') &&executable('cc')
        NeoBundle 'Shougo/vimproc.vim', {
                    \ 'build' : {
                    \     'windows' : 'tools\\update-dll-mingw',
                    \     'cygwin' : 'make -f make_cygwin.mak',
                    \     'mac' : 'make',
                    \     'linux' : 'make',
                    \     'unix' : 'gmake',
                    \    },
                    \ }
    endif

    NeoBundle 'Shougo/vimshell'
    NeoBundle 'thinca/vim-quickrun'
    NeoBundle 'osyo-manga/unite-quickfix'
    NeoBundle 'osyo-manga/shabadou.vim'
    NeoBundle 'dannyob/quickfixstatus'
    NeoBundle 'kana/vim-submode'
    "NeoBundle 'osyo-manga/vim-watchdogs'

    NeoBundle 'tpope/vim-surround'
    NeoBundle 'h1mesuke/vim-alignta'
    NeoBundle 'Lokaltog/vim-easymotion'
    NeoBundle 't9md/vim-textmanip'
    NeoBundle 'vim-scripts/DrawIt'
    NeoBundle 'Yggdroot/indentLine'
    NeoBundle 'tyru/caw.vim'
    NeoBundle 'tpope/vim-endwise'
    NeoBundle 'tmhedberg/matchit'

    NeoBundle 'scrooloose/syntastic'
    NeoBundle 'marcus/rsense'

    NeoBundle 'sjl/gundo.vim'
    NeoBundle 'majutsushi/tagbar'
    NeoBundle 'cohama/agit.vim'
    NeoBundle 'airblade/vim-gitgutter'
    NeoBundle 'szw/vim-tags'

    NeoBundle 'thinca/vim-ref'
    NeoBundle 'mfumi/ref-dicts-en'
    NeoBundle 'mattn/webapi-vim'
    NeoBundle 'mattn/excitetranslate-vim'
    NeoBundle 'cohama/vim-hier'
    NeoBundle 'tyru/open-browser.vim'
    NeoBundle 'osyo-manga/vim-over'
    NeoBundle 'vim-jp/vimdoc-ja'
    NeoBundle 'tpope/vim-fugitive'
    NeoBundle 'tpope/vim-repeat'
    NeoBundle 'moznion/hateblo.vim'
    NeoBundle 'yuku-t/vim-ref-ri'
    NeoBundleLazy 'kchmck/vim-coffee-script', { 'autoload': {'filetypes' : ['coffee']}}

    NeoBundleLazy 'ternjs/tern_for_vim', {
                \  'build': {
                \    'others': 'npm install'
                \  },
                \  'autoload': {
                \    'functions': ['tern#Complete', 'tern#Enable'],
                \    'filetypes': ['javascript']
                \  },
                \  'commands': [
                \    'TernDef', 'TernDoc', 'TernType', 'TernRefs', 'TernRename'
                \  ]
                \ }


    NeoBundleLazy 'mattn/emmet-vim', { 'autoload': {'filetypes' : ['html', 'css']}}
    NeoBundleLazy 'othree/html5.vim', { 'autoload': {'filetypes' : ['html', 'css']}}
    NeoBundleLazy 'hail2u/vim-css3-syntax', { 'autoload': {'filetypes' : ['html', 'css']}}
    NeoBundleLazy 'gorodinskiy/vim-colorsque', { 'autoload': {'filetypes' : ['html', 'css']}}
    NeoBundle 'superbrothers/vim-vimperator'

    call neobundle#end()
    filetype plugin indent on

endif

" ---------------------------------------------------------------------------
" Plugin Settings

" Neobundled関数を用意
function! s:Neobundled(bundle)
    return s:is_neobundle_installed && neobundle#is_installed(a:bundle)
endfunction

" ---------------------------------------------------------------------------
" lightlineの設定

if s:Neobundled('lightline.vim')
    let g:lightline = {                                     
                \ 'colorscheme' : 'wombat',
                \ 'active' : {                              
                \ 'left' : [ [ 'mode', 'paste' ],
                \            [ 'fugitive', 'gitgutter', 'filename' ] ],
                \ 'right' : [ [ 'syntastic', 'lineinfo' ],
                \             [ 'percent' ],
                \             [ 'fileformat', 'fileencoding', 'filetype' ] ]
                \ },
                \ 'component_function' : {
                \   'mode': 'MyMode',
                \   'fugitive': 'MyFugitive',
                \   'readonly': 'MyReadonly',
                \   'filename': 'MyFilename',
                \   'modified': 'MyModified',
                \   'fileformat': 'MyFileformat',
                \   'filetype': 'MyFiletype',
                \   'fileencoding': 'MyFileencoding',
                \   'gitgutter': 'MyGitgutter',
                \ },
                \ 'component_expand' : {
                \   'syntastic': 'SyntasticStatuslineFlag',
                \ },
                \ 'component_type' : {
                \   'syntastic' : 'error',
                \ },
                \ 'separator': { 'left': '', 'right': '' },
                \ 'subseparator': { 'left': '|', 'right': '|' }
                \ }
    function! MyMode()
        let fname = expand('%:t')
        return fname == '__Tagbar__' ? 'Tagbar' :
                    \ fname == '__Gundo__' ? 'Gundo' :
                    \ fname == '__Gundo_Preview__' ? 'Gundo Preview' : 
                    \ fname == '==Translate== Excite' ? 'ExciteTranslate' :
                    \ fname =~ 'gista' ? 'Gista' :
                    \ &ft == 'agit' ? 'Agit' :
                    \ &ft == 'agit_stat' ? 'Agit Stat' :
                    \ &ft == 'agit_diff' ? 'Agit Diff' :
                    \ &ft == 'unite' ? 'Unite' :
                    \ &ft == 'vimfiler' ? 'VimFiler' :
                    \ &ft == 'vimshell' ? 'VimShell' :
                    \ &ft == 'help' ? 'Help' :
                    \ winwidth(0) > 60 ? lightline#mode() : ''
    endfunction

    function! MyModified()
        return &ft =~ 'help\|vimfiler\|gundo\|agit\|gista' ? '' : &modified ? '+' : &modifiable ? '' : '-'
    endfunction

    function! MyReadonly()
        return &ft !~? 'help\|vimfiler\|gundo\|agit\|gista' && &readonly ? '⭤' : ''
    endfunction

    function! MyFugitive()
        if expand('%:t') !~? 'Tagbar\|Gundo\|Excite' && &ft !~? 'vimfiler' && exists("*fugitive#head")
            let _ = fugitive#head()
            return strlen(_) ? '⭠ '._ : ''
        endif
        return ''
    endfunction

    function! MyFilename()
        let fname = expand('%:t')
        return fname == '__Tagbar__' ? g:lightline.fname :
                    \ fname =~ '__Gundo__' ? '' :
                    \ fname =~ '__Gundo_Preview__' ? '' :
                    \ fname =~ '==Translate== Excite' ? '' :
                    \ fname =~ 'gista' ? '' :
                    \ &ft == 'agit' ? '' :
                    \ &ft == 'agit_stat' ? '' :
                    \ &ft == 'agit_diff' ? '' :
                    \ &ft == 'vimfiler' ? vimfiler#get_status_string() : 
                    \  &ft == 'unite' ? unite#get_status_string() : 
                    \  &ft == 'vimshell' ? vimshell#get_status_string() :
                    \ ('' != MyReadonly() ? MyReadonly() . ' ' : '') .
                    \ ('' != fname ? fname : '[No Name]') .
                    \ ('' != MyModified() ? ' ' . MyModified() : '')
    endfunctio

    function! MyGitgutter()
        if ! exists('*GitGutterGetHunkSummary')
                    \ || ! get(g:, 'gitgutter_enabled', 0)
                    \ || winwidth('.') <= 70
            return ''
        endif
        let symbols = [
                    \ g:gitgutter_sign_added . ' ',
                    \ g:gitgutter_sign_modified . ' ',
                    \ g:gitgutter_sign_removed . ' '
                    \ ]
        let hunks = GitGutterGetHunkSummary()
        let ret = []
        for i in [0, 1, 2]
            if hunks[i] > 0
                call add(ret, symbols[i] . hunks[i])
            endif
        endfor
        return join(ret, ' ')
    endfunction

    function! MyFileformat()
        return winwidth(0) > 70 ? &fileformat : ''
    endfunction

    function! MyFiletype()
        return winwidth(0) > 70 ? (strlen(&filetype) ? &filetype : 'no ft') : ''
    endfunction

    function! MyFileencoding()
        return winwidth(0) > 70 ? (strlen(&fenc) ? &fenc : &enc) : ''
    endfunction

    let g:tagbar_status_func = 'TagbarStatusFunc'

    function! TagbarStatusFunc(current, sort, fname, ...) abort
        let g:lightline.fname = a:fname
        return lightline#statusline(0)
    endfunction

    let g:syntastic_mode_map = { 'mode': 'passive' }
    augroup AutoSyntastic
        autocmd!
        autocmd BufWritePost *.c,*.cpp,*.html,*.rb,*.css call s:syntastic()
    augroup END

    function! s:syntastic()
        SyntasticCheck
        call lightline#update()
    endfunction

    let g:unite_force_overwrite_statusline = 0
    let g:vimfiler_force_overwrite_statusline = 0
    let g:vimshell_force_overwrite_statusline = 0

endif

" ---------------------------------------------------------------------------
" neocompleteの設定
if s:Neobundled('neocomplete')

    " 起動時に有効化
    let g:neocomplete#enable_at_startup = 1
    " 大文字が入力されるまで大文字小文字の区別を無視する
    let g:neocomplete#enable_smart_case = 1
    " アンダーバー区切りの補完を有効化
    let g:neocomplete#enable_underbar_completion = 1
    let g:neocomplete#enable_camel_case_completion = 1
    " ポップアップで表示される候補の数
    let g:neocomplete#max_list = 20
    " シンタックスをキャッシュするときの最小文字長
    let g:neocomplete#sources#syntax#min_keyword_length = 3
    " 補完を表示する最低文字数
    let g:neocomplete#auto_completion_start_length = 2
    " preview windowを閉じない
    let g:neocomplete#eneble_auto_close_preview = 0
    autocmd InsertLeave * silent! pclose!

    let g:neocomplete#max_keyword_width = 10000

    if !exists('g:neocomplete#keyword_patterns')
        let g:neocomplete#keyword_patterns = {}
    endif

    if !exists('g:neocomplete#force_omni_input_patterns')
        let g:neocomplete#force_omni_input_patterns = {}
    endif

    let g:neocomplete#force_omni_input_patterns.ruby = '[^.*\t]\.\w*\|\h\w*::'

    autocmd FileType css setlocal omnifunc=csscomplete#CompleteCSS
    autocmd FileType html,markdown setlocal omnifunc=htmlcomplete#CompleteTags
    autocmd FileType javascript setlocal omnifunc=javascriptcomplete#CompleteJS

    let g:neocomplete#data_directory = $HOME . '/.vim/cache/neocomplete'

    call neocomplete#custom#source('look', 'min_pattern_length', 1)

endif

" ============================================================
" Unite.vim
" ============================================================
" prefix key
nnoremap [unite] <Nop>
nmap <Space>f [unite]

" keymapping
nnoremap [unite]u :<C-u>Unite<Space>
nnoremap <silent> [unite]o :<C-u>Unite outline -winheight=15<CR>
nnoremap <silent> [unite]l :<C-u>Unite locate -winheight=15<CR>i
nnoremap <silent> [unite]m :<C-u>Unite file_mru -winheight=15<CR>
nnoremap <silent> [unite]b :<C-u>Unite buffer -winheight=15<CR>
nnoremap <silent> [unite]B :<C-u>Unite bookmark<CR>
nnoremap <silent> [unite]A :<C-u>UniteBookmarkAdd<CR>
nnoremap <silent> [unite]g :<C-u>Unite gista -winheight=15<CR>

" neomruの履歴保存数
let g:unite_source_file_mru_limit = 30

" neomruの表示フォーマット設定
let g:unite_source_file_mru_filename_format = ''

" 大文字小文字を区別しない
let g:unite_enable_ignore_case = 1
let g:unite_enable_smart_case = 1

" grep検索
nnoremap <silent> ,g :<C-u>Unite grep:. -buffer-name=search-buffer<CR>

" カーソルの位置の単語をgrep検索
nnoremap <silent> ,cg :<C-u>Unite grep:. -buffer-name=search-buffer<CR><C-R><C-W>

" grep検索結果の再呼び出し
nnoremap <silent> ,r :<C-u>UniteResume search-buffer<CR>
" unite grep に ag(The Silver Searcher) を使う
if executable('ag')
    let g:unite_source_grep_command = 'ag'
    let g:unite_source_grep_default_opts = '--nogroup --nocolor --column'
    let g:unite_source_grep_recursive_opt = ''
endif

let g:unite_source_history_yank_enable = 1
try
    let g:unite_source_rec_async_command='ag --nocolor --hidden  --nogroup -g ""'
    call unite#filters#matcher_default#use(['matcher_fuzzy'])
catch
endtry
" search a file in the filetree
nnoremap <space><space> :split<cr> :<C-u>Unite -start-insert file_rec/async<cr>
" reset not it is <C-l> normally
:nnoremap <space>r <Plug>(unite_restart)

" ============================================================
" Syntasticの設定
" ============================================================
let g:syntastic_error_symbol = '✘'
let g:syntastic_warning_symbol = '⚠'
let g:syntastic_always_populate_loc_list = 1
let g:syntastic_enable_signs = 1
let g:syntastic_auto_loc_list = 2
let g:syntastic_check_on_open = 1
let g:syntastic_check_on_wq = 0
" HTML5
let g:syntastic_html_tidy_exec = 'tidy5'
let g:syntastic_html_tidy_ignore_errors = [ 'trimming empty <i>' ]
" ruby
let g:syntastic_ruby_checkers = ['rubocop']

" ============================================================
" emmet-vimの設定
" ============================================================
" html lang=ja
let g:user_emmet_settings = {
            \ 'variables' : {
            \   'lang' : 'ja'
            \ }
            \ }

" ============================================================
" vim-refの設定
" ============================================================
" vim-refのバッファをqで閉じれるようにする
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

let g:ref_refe_cmd = $HOME.'/.gem/ruby/2.2.0/bin/refe'

" ============================================================
" ecitetranslate-vimの設定
" ============================================================
"" 開いたバッファを q で閉じれるようにする
autocmd BufEnter ==Translate==\ Excite nnoremap <buffer> <silent> q :<C-u>close<CR>
nnoremap ,et :<C-u>ExciteTranslate<CR>

" ============================================================
" quickrun.vimの設定
" ============================================================
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
            \       "outputter/buffer/into" : 1,
            \       "outputter/buffer/split" : ":botright 10sp"
            \   },
            \}

" ============================================================
" caw.vimの設定
" ============================================================
nmap <C-c> <Plug>(caw:i:toggle)
vmap <C-c> <Plug>(caw:i:toggle)

" ============================================================
" easymotionの設定
" ============================================================
nmap s <Plug>(easymotion-s2)

" ============================================================
" vim-textmanipの設定
" ============================================================
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

" ============================================================
" gundo 
" ============================================================
nnoremap <F5> :GundoToggle<CR>
let g:gundo_width = 55
let g:gundo_preview_height = 30

" ============================================================
" tagbar
" ============================================================
nnoremap <F8> :TagbarToggle<CR> 
let g:tagbar_type_css = {
            \ 'ctagstype' : 'Css',
            \ 'kinds'     : [
            \ 'c:classes',
            \ 's:selectors',
            \ 'i:identities'
            \ ]
            \ }

" ============================================================
" indentLine
" ============================================================
let g:indentLine_faster = 1
let g:indentLine_color_term = 235 
let g:indentLine_char = '▸'

" ============================================================
" neosnippet
" ============================================================
" <TAB>: conpletion.
inoremap <expr><S-TAB>  pumvisible() ? "\<C-p>" : "<S-TAB>"

" Plugin key-mappings.
imap <C-k> <Plug>(neosnippet_expand_or_jump)
smap <C-k> <Plug>(neosnippet_expand_or_jump)

" SuperTab like snippets behavior.
imap <expr><TAB> pumvisible() ? "\<C-n>" : neosnippet#jumpable() ? "\<Plug>(neosnippet_expand_or_jump)" : "\<TAB>"
smap <expr><TAB> neosnippet#jumpable() ? "\<Plug>(neosnippet_expand_or_jump)" : "\<TAB>"


" For snippet_complete marker.
if has('conceal')
    set conceallevel=2 concealcursor=i
endif

" Enable snipMate compatibility feature.
let g:neosnippet#enable_snipmate_compatibility = 1
let g:neosnippet#snippets_directory = '~/.vim/snippet/'

autocmd InsertLeave * syntax clear neosnippetConcealExpandSnippets

" ============================================================
" vimfiler
" ============================================================
let g:vimfiler_as_default_explorer = 1
nnoremap ,vf :<C-u>VimFilerExplorer -toggle<CR>
nnoremap ,vvf :<C-u>VimFiler<CR>

" ============================================================
" gitgutter
" ============================================================
let g:gitgutter_sign_added = '✚'
let g:gitgutter_sign_modified = '➜'
let g:gitgutter_sign_removed = '✘'
nnoremap <F6> :GitGutterToggle<CR>
let g:gitgutter_enabled = 0 

" ============================================================
" vinshellの設定
" ============================================================
nnoremap ,vs :<C-u>VimShell<CR>

" ============================================================
" vim-submodeの設定
" ============================================================
function! s:my_x()
    undojoin
    normal! "_x
endfunction
nnoremap <silent> <Plug>(my-x) :<C-u>call <SID>my_x()<CR>
call submode#enter_with('my_x', 'n', '', 'x', '"_x')
call submode#map('my_x', 'n', 'r', 'x', '<Plug>(my-x)')

" ============================================================
" Gistaの設定
" ============================================================
autocmd FileType gista-list nnoremap <buffer> <silent> q :<C-u>close<CR>
let g:gista#github_user = 'shuymn'
let g:gista#update_on_write = 1 " :w で開いている記事を更新
let g:gista#post_private = 1 " Postを標準でPrivateにする
let g:gista#close_list_after_open = 1 " listからgistを編集しようとした時にlistを自動で閉じる
let g:gista#list_opener = 'topleft 15 split +set\ winfixheight'
nnoremap ,gl :<C-u>Gista -l<CR>
nnoremap ,gd :<C-u>Gista -d
nnoremap ,gpd :<C-u>Gista -P -d
nnoremap .gg :<C-u>Gista<Space>

" ============================================================
" emmet-vim の設定
" ============================================================
let g:user_emmet_leader_key = "<C-e>"
let g:user_emmet_install_global = 0
autocmd FileType html,css EmmetInstall

" ============================================================
" hateblo.vimの設定
" ============================================================
nnoremap ,hbc :<C-u>HatebloCreate<CR>
nnoremap ,hbd :<C-u>HatebloCreateDraft<CR>
nnoremap ,hbl :<C-u>HatebloList<CR>

" ============================================================
" Rsense
" ============================================================
let g:rsenseHome = '/opt/rsense-0.3'
let g:rsenseUseOmniFunc = 1

" ===========================================================
" Coffee Script
" ===========================================================
au BufRead,BufNewFile,BufReadPre *.coffee   set filetype=coffee
autocmd FileType coffee setlocal sw=2 sts=2 ts=2 et

" ============================================================ 
" tern for vim
" ============================================================ 
if s:Neobundled('tern_for_vim')
    let g:tern_map_keys = 0
endif


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
set list
set listchars=eol:¬

" 無限undo
if has('persistent_undo')
    set undodir=$HOME/.vim/undo
    set undofile
endif

" 編集位置の自動修復
au BufReadPost * if line("'\"") > 1 && line("'\"") <= line("$") | exe "normal! g`\""

" ============================================================
" カラー関連
" ============================================================
syntax enable    " コードの色付け
set t_Co=256 
set background=dark
let g:hybrid_use_Xresources = 1
colorscheme hybrid


