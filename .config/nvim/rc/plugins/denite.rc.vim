autocmd Filetype denite call s:denite_my_settings()
function! s:denite_my_settings() abort
      nnoremap <silent><buffer><expr> <CR>
                        \ denite#do_map('do_action')
      nnoremap <silent><buffer><expr> q
                        \ denite#do_map('quit')
      nnoremap <silent><buffer><expr> i
                        \ denite#do_map('open_filter_buffer')
endfunction

autocmd Filetype denite-filter call s:denite_filter_my_settings()
function! s:denite_filter_my_settings() abort
      inoremap <silent><buffer><expr> <ESC>
                        \ denite#do_map('quit')
      nnoremap <silent><buffer><expr> <ESC>
                        \ denite#do_map('quit')
      inoremap <silent><buffer><expr> <C-[>
                        \ denite#do_map('quit')
      nnoremap <silent><buffer><expr> <C-[>
                        \ denite#do_map('quit')
endfunction

let s:floating_window_width_ratio = 0.9
let s:floating_window_height_ratio = 0.7

call denite#custom#option('default', {
                  \ 'auto_action': 'preview',
                  \ 'floating_preview': v:true,
                  \ 'preview_height': float2nr(&lines * s:floating_window_height_ratio),
                  \ 'preview_width': float2nr(&columns * s:floating_window_width_ratio / 2),
                  \ 'prompt': '% ',
                  \ 'split': 'floating',
                  \ 'vertical_preview': v:true,
                  \ 'wincol': float2nr((&columns - (&columns * s:floating_window_width_ratio)) / 2),
                  \ 'winheight': float2nr(&lines * s:floating_window_height_ratio),
                  \ 'winrow': float2nr((&lines - (&lines * s:floating_window_height_ratio)) / 2),
                  \ 'winwidth': float2nr(&columns * s:floating_window_width_ratio / 2),
                  \ 'start_filter': v:true,
                  \ })

call denite#custom#var('file/rec', 'command', ['rg', '--files', '--glob', '!.git'])

call denite#custom#var('grep', 'command', ['rg'])
call denite#custom#var('grep', 'default_opts', ['-i', '--vimgrep', '--no-heading'])
call denite#custom#var('grep', 'recursive_opts', [])
call denite#custom#var('grep', 'pattern_opt', ['--regexp'])
call denite#custom#var('grep', 'separator', ['--'])
call denite#custom#var('grep', 'final_opts', [])
