" ============================================================
" neocompleteの設定
" ============================================================
if neobundle#tap('neocomplete')
    call neobundle#config({
        \   'depends': ['Shougo/context_filetype.vim', 'ujihisa/neco-look', 'pocke/neco-gh-issues', 'Shougo/neco-syntax'],
        \ })

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
    let g:neocomplete#aneble_auto_close_preview = 0
    AutoCmd InsertLeave * silent! pclose!

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

    call neocomplete#custom#source('look', 'min_pattern_length', 1)

    call neobundle#untap()
endif
