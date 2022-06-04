local actions = require("telescope.actions")
local action_layout = require("telescope.actions.layout")
local pickers = require("telescope.pickers")
local finders = require("telescope.finders")
local make_entry = require("telescope.make_entry")
local utils = require("telescope.utils")
local conf = require("telescope.config").values
local telescope_builtin = require("telescope.builtin")
local Path = require("plenary.path")

local action_state = require("telescope.actions.state")
local custom_actions = {}

function custom_actions._multiopen(prompt_bufnr, open_cmd)
	local picker = action_state.get_current_picker(prompt_bufnr)
	local num_selections = #picker:get_multi_selection()
	if num_selections > 1 then
		vim.cmd("bw!")
		for _, entry in ipairs(picker:get_multi_selection()) do
			vim.cmd(string.format("%s %s", open_cmd, entry.value))
		end
		vim.cmd("stopinsert")
	else
		if open_cmd == "vsplit" then
			actions.file_vsplit(prompt_bufnr)
		elseif open_cmd == "split" then
			actions.file_split(prompt_bufnr)
		elseif open_cmd == "tabe" then
			actions.file_tab(prompt_bufnr)
		else
			actions.file_edit(prompt_bufnr)
		end
	end
end

function custom_actions.multi_selection_open_vsplit(prompt_bufnr)
	custom_actions._multiopen(prompt_bufnr, "vsplit")
end
function custom_actions.multi_selection_open_split(prompt_bufnr)
	custom_actions._multiopen(prompt_bufnr, "split")
end
function custom_actions.multi_selection_open_tab(prompt_bufnr)
	custom_actions._multiopen(prompt_bufnr, "tabe")
end
function custom_actions.multi_selection_open(prompt_bufnr)
	custom_actions._multiopen(prompt_bufnr, "edit")
end

require("telescope").setup({
	defaults = {
		vimgrep_arguments = {
			"rg",
			"--color=never",
			"--no-heading",
			"--with-filename",
			"--line-number",
			"--column",
			"--smart-case",
			"--hidden",
		},
		prompt_prefix = "> ",
		selection_caret = "> ",
		entry_prefix = "  ",
		initial_mode = "insert",
		selection_strategy = "reset",
		sorting_strategy = "ascending",
		layout_strategy = "flex",
		layout_config = {
			width = 0.8,
			horizontal = {
				mirror = false,
				prompt_position = "top",
				preview_cutoff = 120,
				preview_width = 0.5,
			},
			vertical = {
				mirror = false,
				prompt_position = "top",
				preview_cutoff = 120,
				preview_width = 0.5,
			},
		},
		file_sorter = require("telescope.sorters").get_fuzzy_file,
		file_ignore_patterns = {
			"node_modules/*",
			".git/*",
		},
		generic_sorter = require("telescope.sorters").get_generic_fuzzy_sorter,
		path_display = {},
		winblend = 0,
		border = {},
		borderchars = {
			{ "─", "│", "─", "│", "┌", "┐", "┘", "└" },
			prompt = { "─", "│", " ", "│", "┌", "┬", "│", "│" },
			results = { "─", "│", "─", "│", "├", "┤", "┴", "└" },
			preview = { "─", "│", "─", " ", "─", "┐", "┘", "─" },
		},
		color_devicons = true,
		use_less = true,
		scroll_strategy = "cycle",
		set_env = { ["COLORTERM"] = "truecolor" },
		buffer_previewer_maker = require("telescope.previewers").buffer_previewer_maker,
		mappings = {
			n = { ["<C-t>"] = action_layout.toggle_preview },
			i = {
				["<C-t>"] = action_layout.toggle_preview,
				["<C-x>"] = false,
				["<C-s>"] = actions.select_horizontal,
				["<Tab>"] = actions.toggle_selection + actions.move_selection_next,
				["<C-q>"] = actions.send_selected_to_qflist,
				["<CR>"] = actions.select_default + actions.center,
				["<C-g>"] = custom_actions.multi_selection_open,
			},
		},
		history = { path = "~/.local/share/nvim/databases/telescope_history.sqlite3", limit = 100 },
	},
	pickers = {
		find_files = {
			find_command = { "fd", "--type", "file", "--strip-cwd-prefix", "--hidden" },
		},
	},
	extensions = {
		frecency = {
			ignore_patterns = {
				"*.git/*",
				"*/tmp/*",
				"*/node_modules/*",
			},
			db_safe_mode = false,
		},
	},
})

local function join_uniq(tbl, tbl2)
	local res = {}
	local hash = {}
	for _, v1 in ipairs(tbl) do
		res[#res + 1] = v1
		hash[v1] = true
	end

	for _, v in pairs(tbl2) do
		if not hash[v] then
			table.insert(res, v)
		end
	end
	return res
end

local function filter_by_cwd_paths(tbl, cwd)
	local res = {}
	local hash = {}
	for _, v in ipairs(tbl) do
		if v:find(cwd, 1, true) then
			local v1 = Path:new(v):normalize(cwd)
			if not hash[v1] then
				res[#res + 1] = v1
				hash[v1] = true
			end
		end
	end
	return res
end

local function requiref(module)
	require(module)
end

telescope_builtin.my_mru = function(opts)
	local get_mru = function(options)
		local res = pcall(requiref, "telescope._extensions.frecency")
		if not res then
			return vim.tbl_filter(function(val)
				return 0 ~= vim.fn.filereadable(val)
			end, vim.v.oldfiles)
		else
			local db_client = require("telescope._extensions.frecency.db_client")
			db_client.init()
			-- too slow
			-- local tbl = db_client.get_file_scores(opts, vim.fn.getcwd())
			local tbl = db_client.get_file_scores(options)
			local get_filename_table = function(table)
				local result = {}
				for _, v in pairs(table) do
					result[#result + 1] = v["filename"]
				end
				return result
			end
			return get_filename_table(tbl)
		end
	end
	local results_mru = get_mru(opts)
	local results_mru_cur = filter_by_cwd_paths(results_mru, vim.loop.cwd())

	local show_untracked = utils.get_default(opts.show_untracked, true)
	local recurse_submodules = utils.get_default(opts.recurse_submodules, false)
	if show_untracked and recurse_submodules then
		error("Git does not suppurt both --others and --recurse-submodules")
	end
	local cmd = {
		"git",
		"ls-files",
		"--exclude-standard",
		"--cached",
		show_untracked and "--others" or nil,
		recurse_submodules and "--recurse-submodules" or nil,
	}
	local results_git = utils.get_os_command_output(cmd)

	local results = join_uniq(results_mru_cur, results_git)

	pickers.new(opts, {
		prompt_title = "MRU",
		finder = finders.new_table({
			results = results,
			entry_maker = opts.entry_maker or make_entry.gen_from_file(opts),
		}),
		-- default_text = vim.fn.getcwd(),
		sorter = conf.file_sorter(opts),
		previewkr = conf.file_previewer(opts),
	}):find()
end

telescope_builtin.grep_prompt = function(opts)
	opts.search = vim.fn.input("Grep String > ")
	telescope_builtin.my_grep(opts)
end

telescope_builtin.my_grep = function(opts)
	require("telescope.builtin").grep_string({
		opts = opts,
		prompt_title = "grep_string: " .. opts.search,
		search = opts.search,
	})
end

telescope_builtin.my_grep_in_dir = function(opts)
	opts.search = vim.fn.input("Grep String > ")
	opts.search_dirs = {}
	opts.search_dirs[1] = vim.fn.input("Target Directory > ")
	require("telescope.builtin").grep_string({
		opts = opts,
		prompt_title = "grep_string(dir): " .. opts.search,
		search = opts.search,
		search_dirs = opts.search_dirs,
	})
end

telescope_builtin.memo = function(opts)
	require("telescope.builtin").find_files({
		opts = opts,
		prompt_title = "MemoList",
		find_command = { "find", vim.g.memolist_path, "-type", "f", "-exec", "ls", "-1ta", "{}", "+" },
	})
end
