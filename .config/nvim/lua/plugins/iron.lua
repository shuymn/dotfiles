local iron = require("iron.core")

iron.setup({
	config = {
		should_map_plug = false,
		scratch_repl = true,
		repl_open_cmd = require("iron.view").curry.bottom(40),
	},
})
