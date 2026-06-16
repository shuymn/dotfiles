vim.keymap.set("n", "<Esc>", "<cmd>nohlsearch<CR>", { silent = true, desc = "Clear search highlight" })
vim.keymap.set("n", "x", '"_x', { silent = true })
vim.keymap.set("x", "x", '"_x', { silent = true })

local function open_file_explorer()
	local path = vim.api.nvim_buf_get_name(0)
	if path == "" or vim.uv.fs_stat(path) == nil then
		path = vim.uv.cwd()
	end
	require("mini.files").open(path, true)
end

local open_picker

local picker_prefix_to_kind = {
	[">"] = "commands",
	["/"] = "grep",
	["#"] = "document_symbols",
	["@"] = "workspace_symbols",
	["?"] = "help",
	["h"] = "visit_paths",
	[":"] = "command_history",
}

local picker_prompt_prefix_by_kind = {
	commands = "Commands > ",
	grep = "Grep / ",
	document_symbols = "Symbols # ",
	workspace_symbols = "Workspace symbols @ ",
	help = "Help ? ",
	visit_paths = "History h ",
	command_history = "Command history : ",
}

local function open_curated_help()
	local pick = require("mini.pick")

	local function feed(keys)
		return function()
			vim.api.nvim_feedkeys(vim.keycode(keys), "m", false)
		end
	end

	local items = {
		{ text = "<leader><space>  Open picker / files",      action = function() open_picker() end },
		{ text = "<leader>e        File explorer",            action = open_file_explorer },
		{ text = "<leader>?        This help",                action = open_curated_help },
		{ text = "? <Space>        Picker help",              action = open_curated_help },
		{ text = "/ <Space>        Live grep",                action = function() open_picker("grep") end },
		{ text = "> <Space>        Commands",                 action = function() open_picker("commands") end },
		{ text = "# <Space>        Document symbols",         action = function() open_picker("document_symbols") end },
		{ text = "@ <Space>        Workspace symbols",        action = function() open_picker("workspace_symbols") end },
		{ text = "h <Space>        Visit history",            action = function() open_picker("visit_paths") end },
		{ text = ": <Space>        Command history",          action = function() open_picker("command_history") end },
		{ text = "<leader>la       LSP code action",          action = vim.lsp.buf.code_action },
		{ text = "<leader>lf       LSP format",               action = function() vim.lsp.buf.format({ async = true }) end },
		{ text = "<leader>lr       LSP rename",               action = vim.lsp.buf.rename },
		{ text = "<leader>ls       LSP document symbols",     action = function() open_picker("document_symbols") end },
		{ text = "<leader>bd       Delete buffer",            action = function() require("mini.bufremove").delete(0,
				false) end },
		{ text = "<C-w>s           Split horizontal",         action = feed("<C-w>s") },
		{ text = "<C-w>v           Split vertical",           action = feed("<C-w>v") },
		{ text = "<C-w>c           Close window",             action = feed("<C-w>c") },
		{ text = "<C-w>o           Only this window",         action = feed("<C-w>o") },
		{ text = "<C-w>w           Next window",              action = feed("<C-w>w") },
		{ text = ":copen           Open quickfix",            action = function() vim.cmd.copen() end },
		{ text = ":cclose          Close quickfix",           action = function() vim.cmd.cclose() end },
		{ text = "[q / ]q          Previous / next quickfix", action = feed("]q") },
		{ text = "<C-o> / <C-i>    Jump back / forward",      action = feed("<C-o>") },
		{ text = "[ / ]            Previous / next targets",  action = feed("]") },
	}

	return pick.start({
		source = {
			items = items,
			name = "Keymap help",
			choose = function(item)
				if item.action ~= nil then
					item.action()
				end
			end,
		},
		window = {
			prompt_prefix = "Help: ",
		},
	})
end

open_picker = function(kind)
	local pick = require("mini.pick")
	local extra = require("mini.extra")

	local function put_space()
		local query = pick.get_picker_query() or {}
		table.insert(query, " ")
		pick.set_picker_query(query)
	end

	local function delete_char_or_return_to_files()
		local query = pick.get_picker_query() or {}
		if #query == 0 then
			if kind ~= nil then
				vim.schedule(function()
					open_picker()
				end)
				return true
			end
			return false
		end

		table.remove(query)
		pick.set_picker_query(query)
		return false
	end

	local function dispatch_on_space()
		local query = pick.get_picker_query() or {}
		local next_kind = #query == 1 and picker_prefix_to_kind[query[1]] or nil
		if next_kind == nil then
			put_space()
			return false
		end

		vim.schedule(function()
			open_picker(next_kind)
		end)
		return true
	end

	local mappings = {
		delete_char = "",
		delete_or_return_to_files = { char = "<BS>", func = delete_char_or_return_to_files },
		dispatch = { char = "<Space>", func = dispatch_on_space },
	}

	local opts = {
		mappings = mappings,
		window = {
			prompt_prefix = picker_prompt_prefix_by_kind[kind] or "Files: ",
		},
	}

	if kind == "commands" then
		return extra.pickers.commands({}, opts)
	elseif kind == "grep" then
		return pick.builtin.grep_live({}, opts)
	elseif kind == "document_symbols" then
		return extra.pickers.lsp({ scope = "document_symbol" }, opts)
	elseif kind == "workspace_symbols" then
		return extra.pickers.lsp({ scope = "workspace_symbol_live" }, opts)
	elseif kind == "help" then
		return open_curated_help()
	elseif kind == "visit_paths" then
		return extra.pickers.visit_paths({}, opts)
	elseif kind == "command_history" then
		return extra.pickers.history({ scope = ":" }, opts)
	end

	return pick.builtin.files({ tool = "git" }, opts)
end

vim.keymap.set("n", "<leader><space>", open_picker, { desc = "Picker" })
vim.keymap.set("n", "<leader><leader>", open_picker, { desc = "Picker" })
vim.keymap.set("n", "<leader>e", open_file_explorer, { desc = "File explorer" })
vim.keymap.set("n", "<leader>?", open_curated_help, { desc = "Keymap help" })

vim.keymap.set("n", "<leader>la", vim.lsp.buf.code_action, { desc = "LSP code action" })
vim.keymap.set("n", "<leader>lf", function() vim.lsp.buf.format({ async = true }) end, { desc = "LSP format" })
vim.keymap.set("n", "<leader>lr", vim.lsp.buf.rename, { desc = "LSP rename" })
vim.keymap.set("n", "<leader>ls", function()
	open_picker("document_symbols")
end, { desc = "LSP document symbols" })

vim.keymap.set("n", "<leader>bd", function() require("mini.bufremove").delete(0, false) end, { desc = "Delete buffer" })
