local lualine = require("lualine")
local lualine_require = require("lualine_require")
local utils = require("lualine.utils.utils")

local colors = {
	-- onedark
	blue = "#61afef",
	green = "#98c379",
	purple = "#c678dd",
	cyan = "#56b6c2",
	red1 = "#e06c75",
	red2 = "#be5046",
	yellow = "#e5c07b",
	fg = "#abb2bf",
	bg = "#282c34",
	gray1 = "#828997",
	gray2 = "#2c323c",
	gray3 = "#3e4452",
}

local theme = {
	normal = {
		a = { fg = colors.bg, bg = colors.green },
		b = { fg = colors.fg, bg = colors.gray2 },
		c = { fg = colors.fg, bg = colors.gray2 },
	},
	insert = {
		a = { fg = colors.bg, bg = colors.blue },
	},
	visual = {
		a = { fg = colors.bg, bg = colors.purple },
	},
	replace = {
		a = { fg = colors.bg, bg = colors.red1 },
	},
	inactive = {
		a = { fg = colors.gray1, bg = colors.bg },
	},
}

local is_available_gps = function()
	local ok, gps = pcall(require, "nvim-gps")
	if not ok then
		return false
	end
	return gps.is_available()
end

local is_blame_text_available = function()
	local ok, gitblame = pcall(require, "gitblame")
	if not ok then
		return false
	end

	local availability = gitblame.is_blame_text_available()
	if not availability or (gitblame.get_current_blame_text() == "  Not Committed Yet") then
		return false
	end
	return true
end

local format_filetype = function(buf_ft)
	local ft_table = {}
	ft_table["cpp"] = "C++"
	ft_table["typescript"] = "TypeScript"
	ft_table["javascript"] = "JavaScript"
	ft_table["typescriptreact"] = "TypeScript React"
	ft_table["javascriptreact"] = "JavaScript React"
	ft_table["json"] = "JSON"
	ft_table["jsonc"] = "JSON with Comments"
	ft_table["html"] = "HTML"
	ft_table["css"] = "CSS"
	ft_table["scss"] = "SCSS"
	ft_table["php"] = "PHP"
	ft_table["sql"] = "SQL"
	ft_table["ignore"] = "gitignore"
	ft_table["editorconfig"] = "EditorConfig"
	ft_table["git-commit"] = "Git Commit Message"
	ft_table["git-rebase"] = "Git Rebase Message"
	ft_table["dotenv"] = "Environment Variables"
	ft_table["gomod"] = "Go Module file"
	ft_table["proto"] = "Protocol Buffers"
	ft_table["sh"] = "Shell Script"
	ft_table["yaml"] = "YAML"
	ft_table["toml"] = "TOML"
	ft_table["vim"] = "Vim Script"
	ft_table["sshconfig"] = "SSH Config"

	local ft = ""
	if ft_table[buf_ft] ~= nil then
		ft = ft_table[buf_ft]
	elseif buf_ft == "" then
		ft = "Plain Text"
	else
		ft = string.gsub(buf_ft, "^%l", string.upper)
	end

	if buf_ft ~= "" then
		local clients = vim.lsp.get_active_clients()
		if next(clients) ~= nil then
			for _, client in ipairs(clients) do
				if client.name ~= "null-ls" then
					local filetypes = client.config.filetypes
					if filetypes and vim.fn.index(filetypes, buf_ft) ~= -1 then
						return string.format(" %s", ft)
					end
				end
			end
		end
	end
	return string.format(" %s", ft)
end

local indent = function()
	local tabstop = vim.o.tabstop
	if vim.o.expandtab then
		return string.format("Spaces:%s", tabstop)
	else
		return string.format("Tab Size:%s", tabstop)
	end
end

local sections_1 = {
	lualine_a = {
		{
			"mode",
			fmt = function()
				return ""
			end,
		},
	},
	lualine_b = {
		{ "branch", icon = "שׂ" },
		{
			"diagnostics",
			sections = { "error", "warn" },
			colored = false,
			always_visible = true,
		},
	},
	lualine_c = {
		{
			'require("nvim-gps").get_location()',
			cond = is_available_gps,
		},
	},
	lualine_x = {
		{
			'require("gitblame").get_current_blame_text()',
			cond = is_blame_text_available,
			icon = "ﰖ",
		},
		{
			"location",
			fmt = function()
				return " %l  %v"
			end,
		},
		{ indent, icon = "ﲒ" },
		{ "encoding", fmt = string.upper, icon = "" },
		{
			"fileformat",
			icon = "﬋",
			fmt = function(icon)
				if icon == "" then
					return "LF"
				elseif icon == "" then
					return "CRLF"
				elseif icon == "" then
					return "CR"
				else
					return icon
				end
			end,
		},
		{
			"filetype",
			icons_enabled = false,
			fmt = format_filetype,
		},
	},
	lualine_y = {},
	lualine_z = {},
}

local sections_2 = {
	lualine_a = { { "mode" } },
	lualine_b = { "" },
	lualine_c = { { "filetype", icon_only = true }, { "filename", path = 1 } },
	lualine_x = { "encoding", "fileformat", "filetype" },
	lualine_y = { "filesize", "progress" },
	lualine_z = { { "location" } },
}

vim.keymap.set("n", "!", function()
	local modules = lualine_require.lazy_require({ config_module = "lualine.config" })

	local current_config = modules.config_module.get_config()
	if vim.inspect(current_config.sections) == vim.inspect(sections_1) then
		current_config.sections = utils.deepcopy(sections_2)
	else
		current_config.sections = utils.deepcopy(sections_1)
	end
	lualine.setup(current_config)
end, { noremap = true, silent = true })

local terminal_status_color = function(status)
	local mode_colors = {
		Running = colors.yellow,
		Finished = colors.purple,
		Success = colors.blue,
		Error = colors.red1,
		Command = colors.green,
	}
	return mode_colors[status]
end

local get_exit_status = function()
	local ln = vim.api.nvim_buf_line_count(0)
	while ln >= 1 do
		local l = vim.api.nvim_buf_get_lines(0, ln - 1, ln, true)[1]
		ln = ln - 1
		local exit_code = string.match(l, "^%[Process exited ([0-9]+)%]$")
		if exit_code ~= nil then
			return tonumber(exit_code)
		end
	end
end

local terminal_status = function()
	if
		vim.api.nvim_exec(
			[[echo trim(execute("filter /" . escape(nvim_buf_get_name(bufnr()), '~/') . "/ ls! uaF"))]],
			true
		) ~= ""
	then
		local result = get_exit_status()
		if result == nil then
			return "Finished"
		elseif result == 0 then
			return "Success"
		elseif result >= 1 then
			return "Error"
		end
		return "Finished"
	end
	if
		vim.api.nvim_exec(
			[[echo trim(execute("filter /" . escape(nvim_buf_get_name(bufnr()), '~/') . "/ ls! uaR"))]],
			true
		) ~= ""
	then
		return "Running"
	end
	return "Command"
end

local get_terminal_status = function()
	if vim.bo.buftype ~= "terminal" then
		return ""
	end
	local status = terminal_status()
	vim.api.nvim_command(
		"hi LualineToggleTermStatus guifg=" .. colors.background .. " guibg=" .. terminal_status_color(status)
	)
	return status
end

local toggleterm_statusline = function()
	return "ToggleTerm #" .. vim.b.toggle_number
end

local my_toggleterm = {
	sections = {
		lualine_a = { toggleterm_statusline },
		lualine_z = { { get_terminal_status, color = "LualineToggleTermStatus" } },
	},
	filetypes = { "toggleterm" },
}

lualine.setup({
	options = {
		icon_enabled = true,
		theme = theme,
		section_separators = "",
		component_separators = "",
	},
	sections = sections_1,
	extensions = { "quickfix", my_toggleterm },
})
