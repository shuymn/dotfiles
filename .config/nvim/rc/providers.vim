" python
let $PYTHON2_VENV_DIR = expand('$HOME/.asdf/installs/python/2.7.18')
let $PYTHON3_VENV_DIR = expand('$HOME/.asdf/installs/python/3.9.0')

if has('nvim') && isdirectory($PYTHON2_VENV_DIR)
	let g:python_host_prog = expand('$PYTHON2_VENV_DIR/bin/python')
endif

if has('nvim') && isdirectory($PYTHON3_VENV_DIR)
	let g:python3_host_prog = expand('$PYTHON3_VENV_DIR/bin/python')
endif

