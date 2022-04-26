vim.cmd([[hi TabLineSel guibg=#ddc7a1]])

require("bufferline").setup({
	options = {
		numbers = function(opts)
			return string.format("%s", opts.ordinal)
		end,
		custom_filter = function(buf_number)
			if vim.bo[buf_number].filetype == "qf" then
				return false
			end
			if vim.bo[buf_number].buftype == "terminal" then
				return false
			end
			-- -- filter out by buffer name
			if vim.fn.bufname(buf_number) == "" or vim.fn.bufname(buf_number) == "[No Name]" then
				return false
			end
			return true
		end,
		max_name_length = 30,
		diagnostics = "nvim_lsp",
		diagnostics_indicator = function(_, level, _, _)
			local icon = level:match("error") and " " or " "
			return " " .. icon
		end,
		offsets = {
			{
				filetype = "neo-tree",
				text = "",
				highlight = "Directory",
				text_align = "left",
			},
			{
				filetype = "SidebarNvim",
				text = "",
				highlight = "Directory",
				text_align = "left",
			},
		},
		show_buffer_close_icons = false,
		show_close_icon = false,
	},
})
