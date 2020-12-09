autocmd BufWritePost * call defx#redraw()
autocmd BufEnter * call defx#redraw()
autocmd TabLeave * if &filetype == 'defx' | bdel | endif
autocmd FileType defx call s:defx_my_settings()

function! s:defx_my_settings() abort
  nnoremap <silent><buffer><expr> <CR>
        \ defx#is_directory() ? defx#do_action('open') : defx#do_action('multi', ['drop', 'quit'])
  nnoremap <silent><buffer><expr> h
        \ defx#do_action('cd', ['..'])
  nnoremap <silent><buffer><expr> j
        \ line('.') == line('$') ? 'gg' : 'j'
  nnoremap <silent><buffer><expr> k
        \ line('.') == 1 ? 'G' : 'k'
  nnoremap <silent><buffer><expr> l
        \ defx#is_directory() ? defx#do_action('open') : defx#do_action('multi', ['drop', 'quit'])

  nnoremap <silent><buffer><expr> o
        \ defx#do_action('open_tree', 'toggle')
  nnoremap <silent><buffer><expr> p
        \ defx#do_action('preview')
  nnoremap <silent><buffer><expr> e
        \ defx#do_action('multi', [['drop', 'vsplit'], 'quit'])
  nnoremap <silent><buffer><expr> t
        \ defx#do_action('open', 'tabnew') 
  nnoremap <silent><buffer><expr> yy
        \ defx#do_action('yank_path')
  nnoremap <silent><buffer><expr> q
        \ defx#do_action('quit')
  nnoremap <silent><buffer><expr> .
        \ defx#do_action('toggle_ignored_files')
endfunction

function! Root(path) abort
  return fnamemodify(a:path, ':t')
endfunction

call defx#custom#source('file', {
      \ 'root': 'Root',
      \ })

call defx#custom#column('mark', {
      \ 'readonly_icon': '✗',
      \ 'selected_icon': '✓',
      \ })

let s:floating_window_width_ratio = 0.9
let s:floating_window_height_ratio = 0.8

call defx#custom#option('_', {
      \ 'split': 'floating',
      \ 'winwidth': float2nr(&columns * s:floating_window_width_ratio / 3),
      \ 'wincol': float2nr((&columns - (&columns * s:floating_window_width_ratio)) / 2),
      \ 'winheight': float2nr(&lines * s:floating_window_height_ratio),
      \ 'winrow': float2nr((&lines - (&lines * s:floating_window_height_ratio)) / 2),
      \ 'show_ignored_files': v:true,
      \ 'toggle': v:true,
      \ 'resume': v:true,
      \ 'columns': 'indent:git:icons:filename:mark',
      \ 'floating_preview': v:true,
      \ 'vertical_preview': v:true,
      \ 'preview_width': float2nr(&columns * s:floating_window_width_ratio * 2 / 3),
      \ 'preview_height': float2nr(&lines * s:floating_window_height_ratio),
      \ })

