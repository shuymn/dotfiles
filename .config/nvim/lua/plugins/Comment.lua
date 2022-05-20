require("Comment").setup({
	mappings = {
		basic = true,
		extra = false,
		extended = false,
	},
	pre_hook = function()
		return require("ts_context_commentstring.internal").calculate_commentstring({
			location = require("ts_context_commentstring.utils").get_cursor_location(),
		})
	end,
})
