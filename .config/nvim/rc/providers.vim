" python
let $PYTHON2_VENV_DIR = expand('$PYENV_ROOT/versions/neovim-python2')
let $PYTHON3_VENV_DIR = expand('$PYENV_ROOT/versions/neovim-python3')

if has('nvim') && isdirectory($PYTHON2_VENV_DIR)
	let g:python_host_prog = expand('$PYTHON2_VENV_DIR/bin/python')
endif

if has('nvim') && isdirectory($PYTHON3_VENV_DIR)
	let g:python3_host_prog = expand('$PYTHON3_VENV_DIR/bin/python')
endif

