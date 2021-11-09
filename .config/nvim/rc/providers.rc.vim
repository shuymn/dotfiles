" python
let $PYTHON2_VENV_DIR = expand('$PYENV_ROOT/versions/neovim-python2')
let $PYTHON3_VENV_DIR = expand('$PYENV_ROOT/versions/neovim-python3')

if has('nvim') && isdirectory($PYTHON2_VENV_DIR)
	let g:python_host_prog = expand('$PYTHON2_VENV_DIR/bin/python')
endif

if has('nvim') && isdirectory($PYTHON3_VENV_DIR)
	let g:python3_host_prog = expand('$PYTHON3_VENV_DIR/bin/python')
endif

" Node.js
let $NODEJS_NEOVIM_DIR = expand('~/.volta/tools/image/packages/neovim')

if has('nvim') && isdirectory($NODEJS_NEOVIM_DIR)
	let g:node_host_prog = expand('$NODEJS_NEOVIM_DIR/lib/node_modules/neovim/bin/cli.js')
endif
