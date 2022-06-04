require("project_nvim").setup({
	respect_buf_cwd = true,
	update_cwd = true,
	update_focused_file = {
		enable = true,
		update_cwd = true,
	},
})

require("telescope").load_extension("projects")
