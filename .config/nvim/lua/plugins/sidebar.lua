require("sidebar-nvim").setup({
	disable_default_keybindings = 0,
	bindings = {
		["q"] = function()
			require("sidebar-nvim").close()
		end,
	},
	open = false,
	side = "right",
	initial_width = 35,
	update_interval = 1000,
	section_separator = "-----",
})
