local install_path = vim.fn.stdpath("data") .. "/lazy/lazy.nvim"

if not vim.loop.fs_stat(install_path) then
	vim.fn.system({
		"git",
		"clone",
		"--filter=blob:none",
		"https://github.com/folke/lazy.nvim.git",
		"--branch=stable",
		install_path,
	})
end

vim.opt.rtp:prepend(install_path)

return require("lazy").setup({
	-- lua library
	{ "nvim-lua/plenary.nvim", lazy = true },
	{ "MunifTanjim/nui.nvim", lazy = true },

	-- font
	{ "nvim-tree/nvim-web-devicons", lazy = true },

	-- colorscheme
	{
		"catppuccin/nvim",
		name = "catppuccin",
		priority = 1000,
		config = function()
			require("catppuccin").setup({
				flavour = "mocha",
				integrations = {
					fidget = true,
					lsp_saga = true,
					mason = true,
					noice = true,
					treesitter_context = true,
					lsp_trouble = true,
					illuminate = true,
					which_key = true,
				},
			})

			vim.cmd.colorscheme("catppuccin")
		end,
	},

	-- auto completion
	{
		"hrsh7th/nvim-cmp",
		event = "InsertEnter",
		dependencies = {
			{
				"L3MON4D3/LuaSnip",
				dependencies = "rafamadriz/friendly-snippets",
				config = function()
					local ls = require("luasnip")
					local types = require("luasnip.util.types")

					ls.config.set_config({
						history = true,
						updateevents = "TextChanged,TextChangedI",
						delete_check_events = "TextChanged",
						ext_opts = { [types.choiceNode] = { active = { virt_text = { { "choiceNode", "Comment" } } } } },
						ext_base_prio = 300,
						ext_prio_increase = 1,
						enable_autosnippets = true,
						store_selection_keys = "<Tab>",
						ft_func = function()
							return vim.split(vim.bo.filetype, ".", true)
						end,
					})

					require("luasnip.loaders.from_vscode").lazy_load()
					require("luasnip.loaders.from_lua").lazy_load({ paths = "~/.config/nvim/luasnip-snippets" })
				end,
			},
			{
				"onsails/lspkind.nvim",
				config = function()
					require("lspkind").init({
						mode = "symbol_text",
					})
				end,
			},
			"hrsh7th/cmp-nvim-lsp",
			"hrsh7th/cmp-nvim-lsp-document-symbol",
			"hrsh7th/cmp-buffer",
			"hrsh7th/cmp-path",
			"hrsh7th/cmp-nvim-lua",
			"saadparwaiz1/cmp_luasnip",
			"hrsh7th/cmp-calc",
			"hrsh7th/cmp-emoji",
			"f3fora/cmp-spell",
			"ray-x/cmp-treesitter",
			"hrsh7th/cmp-cmdline",
			{
				"uga-rosa/cmp-dictionary",
				config = function()
					local file = "/usr/share/dict/words"
					local dic = {}
					if vim.fn.filereadable(file) ~= 0 then
						dic = file
					end

					require("cmp_dictionary").setup({
						dic = { ["*"] = dic },
						exact = 2,
						async = false,
						capacity = 5,
						debug = false,
					})
				end,
			},
		},
		config = function()
			vim.opt.completeopt = { "menu", "menuone", "noselect" }

			local cmp = require("cmp")
			local types = require("cmp.types")
			local luasnip = require("luasnip")

			local has_words_before = function()
				local line, col = unpack(vim.api.nvim_win_get_cursor(0))
				return col ~= 0
					and vim.api.nvim_buf_get_lines(0, line - 1, line, true)[1]:sub(col, col):match("%s") == nil
			end

			cmp.setup({
				formatting = {
					format = require("lspkind").cmp_format({
						with_text = true,
						menu = {
							buffer = "[Buffer]",
							nvim_lsp = "[LSP]",
							luasnip = "[LuaSnip]",
							nvim_lua = "[Lua]",
							path = "[Path]",
							spell = "[Spell]",
							emoji = "[Emoji]",
							calc = "[Calc]",
							treesitter = "[TS]",
							dictionary = "[Dict]",
						},
					}),
				},
				snippet = {
					expand = function(args)
						luasnip.lsp_expand(args.body)
					end,
				},
				sorting = {
					comparators = {
						cmp.config.compare.offset,
						cmp.config.compare.exact,
						cmp.config.compare.score,
						function(entry1, entry2)
							local kind1 = entry1:get_kind()
							kind1 = kind1 == types.lsp.CompletionItemKind.Text and 100 or kind1
							local kind2 = entry2:get_kind()
							kind2 = kind2 == types.lsp.CompletionItemKind.Text and 100 or kind2
							if kind1 ~= kind2 then
								if kind1 == types.lsp.CompletionItemKind.Snippet then
									return false
								end
								if kind2 == types.lsp.CompletionItemKind.Snippet then
									return true
								end
								local diff = kind1 - kind2
								if diff < 0 then
									return true
								elseif diff > 0 then
									return false
								end
							end
						end,
						cmp.config.compare.sort_text,
						cmp.config.compare.length,
						cmp.config.compare.order,
					},
				},
				mapping = {
					["<C-p>"] = cmp.mapping(cmp.mapping.select_prev_item(), { "i", "c" }),
					["<C-n>"] = cmp.mapping(cmp.mapping.select_next_item(), { "i", "c" }),
					["<C-b>"] = cmp.mapping(cmp.mapping.scroll_docs(-4), { "i", "c" }),
					["<C-f>"] = cmp.mapping(cmp.mapping.scroll_docs(4), { "i", "c" }),
					["<C-Space>"] = cmp.mapping(cmp.mapping.complete(), { "i", "c" }),
					["<C-y>"] = cmp.config.disable,
					["<C-q>"] = cmp.mapping({ i = cmp.mapping.abort(), c = cmp.mapping.close() }),
					["<CR>"] = cmp.mapping.confirm({ select = false }),
					["<Tab>"] = cmp.mapping(function(fallback)
						if cmp.visible() then
							cmp.select_next_item()
						elseif luasnip.expand_or_jumpable() then
							luasnip.expand_or_jump()
						elseif has_words_before() then
							cmp.complete()
						else
							fallback()
						end
					end, { "i", "s" }),
					["<S-Tab>"] = cmp.mapping(function(fallback)
						if cmp.visible() then
							cmp.select_prev_item()
						elseif luasnip.jumpable(-1) then
							luasnip.jump(-1)
						else
							fallback()
						end
					end, { "i", "s" }),
				},
				sources = cmp.config.sources({
					{ name = "nvim_lsp", priority = 100 },
					{ name = "luasnip", priority = 20 },
					{ name = "path", priority = 100 },
					{ name = "emoji", insert = true, priority = 60 },
					{ name = "nvim_lua", priority = 50 },
				}, {
					{ name = "buffer", priority = 50 },
					{ name = "spell", priority = 40 },
					{ name = "calc", priority = 50 },
					{ name = "treesitter", priority = 30 },
					{ name = "dictionary", keyword_length = 2, priority = 10 },
				}),
			})

			cmp.setup.filetype({ "gitcommit", "markdown" }, {
				sources = cmp.config.sources({
					{ name = "nvim_lsp", priority = 100 },
					{ name = "luasnip", priority = 80 },
					{ name = "path", priority = 100 },
					{ name = "emoji", insert = true, priority = 60 },
				}, {
					{ name = "buffer", priority = 50 },
					{ name = "omni", priority = 40 },
					{ name = "spell", priority = 40 },
					{ name = "calc", priority = 50 },
					{ name = "treesitter", priority = 30 },
					{ name = "mocword", priority = 60 },
					{ name = "dictionary", keyword_length = 2, priority = 10 },
				}),
			})

			cmp.setup.cmdline("/", {
				mapping = cmp.mapping.preset.cmdline(),
				sources = cmp.config.sources({
					{ name = "nvim_lsp_document_symbol" },
				}, {
					{ name = "buffer" },
				}),
			})

			cmp.setup.cmdline(":", {
				mapping = {
					["<Tab>"] = cmp.mapping(function(fallback)
						if cmp.visible() then
							cmp.select_next_item()
						else
							fallback()
						end
					end, { "c" }),

					["<S-Tab>"] = cmp.mapping(function(fallback)
						if cmp.visible() then
							cmp.select_prev_item()
						else
							fallback()
						end
					end, { "c" }),
					["<C-y>"] = {
						c = cmp.mapping.confirm({ select = false }),
					},
					["<C-q>"] = {
						c = cmp.mapping.abort(),
					},
				},
				sources = cmp.config.sources({ { name = "path" } }, { { name = "cmdline" } }),
			})
		end,
	},

	-- text object
	{
		"nvim-treesitter/nvim-treesitter",
		build = ":TSUpdateSync",
		event = "VeryLazy",
		dependencies = {
			"yioneko/nvim-yati",
			"p00f/nvim-ts-rainbow",
			"JoosepAlviste/nvim-ts-context-commentstring",
			"nvim-treesitter/nvim-treesitter-textobjects",
			{
				"David-Kunz/treesitter-unit",
				keys = {
					{
						"iu",
						function()
							require("treesitter-unit").select()
						end,
						mode = "x",
						noremap = true,
					},
					{
						"au",
						function()
							require("treesitter-unit").select(true)
						end,
						mode = "x",
						noremap = true,
					},
					{
						"iu",
						function()
							require("treesitter-unit").select()
						end,
						mode = "o",
						noremap = true,
					},
					{
						"au",
						function()
							require("treesitter-unit").select(true)
						end,
						mode = "o",
						noremap = true,
					},
				},
			},
		},
		config = function()
			require("nvim-treesitter.configs").setup({
				ensure_installed = "all",
				ignore_install = { "phpdoc" },
				highlight = {
					enable = true,
					additional_vim_regex_highlighting = false,
				},
				incremental_selection = {
					enable = true,
					keymaps = {
						init_selection = "<CR>",
						scope_incremental = "<CR>",
						node_incremental = "<TAB>",
						node_decremental = "<S-TAB>",
					},
				},
				indent = { enable = false },
				textobjects = {
					select = {
						enable = true,
						disable = {},
						keymaps = {
							["af"] = "@function.outer",
							["if"] = "@function.inner",
							["ac"] = "@class.outer",
							["ic"] = "@class.inner",
							["iB"] = "@block.inner",
							["aB"] = "@block.outer",
							["ii"] = "@conditional.inner",
							["ai"] = "@conditional.outer",
							["il"] = "@loop.inner",
							["al"] = "@loop.outer",
							["ip"] = "@parameter.inner",
							["ap"] = "@parameter.outer",
						},
					},
					swap = {
						enable = true,
						swap_next = { ["'>"] = "@parameter.inner" },
						swap_previous = { ["'<"] = "@parameter.inner" },
					},
					move = {
						enable = true,
						goto_next_start = { ["]m"] = "@function.outer", ["]]"] = "@class.outer" },
						goto_next_end = { ["]M"] = "@function.outer", ["]["] = "@class.outer" },
						goto_previous_start = { ["[m"] = "@function.outer", ["[["] = "@class.outer" },
						goto_previous_end = { ["[M"] = "@function.outer", ["[]"] = "@class.outer" },
					},
				},
				rainbow = {
					enable = true,
					extended_mode = true,
					max_file_lines = nil,
				},
				matchup = { enable = true },
				context_commentstring = { enable = true },
				yati = { enable = true },
			})
		end,
	},
	{
		"machakann/vim-sandwich",
		event = "VeryLazy",
		config = function()
			vim.cmd.runtime("macros/sandwich/keymap/surround.vim")
		end,
	},

	-- lsp
	{
		"neovim/nvim-lspconfig",
		event = "VimEnter",
		config = function()
			local signs = { Error = "", Warn = "", Hint = "", Info = "" }

			for type, icon in pairs(signs) do
				local hl = "DiagnosticSign" .. type
				vim.fn.sign_define(hl, { text = icon, texthl = hl, numhl = hl })
			end
		end,
	},
	{
		"williamboman/mason.nvim",
		event = "VimEnter",
		config = true,
	},
	{
		"williamboman/mason-lspconfig.nvim",
		event = "VimEnter",
		dependencies = {
			"RRethy/vim-illuminate",
			config = function()
				vim.g.Illuminate_delay = 300
			end,
		},
		config = function()
			local on_attach = function(client, bufnr)
				local function buf_set_keymap(...)
					vim.api.nvim_buf_set_keymap(bufnr, ...)
				end
				local function buf_set_option(...)
					vim.api.nvim_buf_set_option(bufnr, ...)
				end

				-- Enable completion triggered by <c-x><c-o>
				buf_set_option("omnifunc", "v:lua.vim.lsp.omnifunc")

				require("illuminate").on_attach(client)
			end

			local server_configs = {
				["lua_ls"] = {
					settings = {
						Lua = {
							completion = { callSnippet = "Replace" },
							format = { enable = false },
							workspace = { preloadFileSize = 500 },
							runtime = { version = "LuaJIT" },
							diagnostics = {
								globals = { "vim" },
								disable = { "different-requires" },
							},
							telemetry = { enable = false },
						},
					},
				},
			}

			local capabilities = vim.lsp.protocol.make_client_capabilities()
			capabilities = require("cmp_nvim_lsp").default_capabilities(capabilities)

			require("mason-lspconfig").setup({
				handlers = {
					function(server_name)
						local opts = {
							capabilities = capabilities,
							on_attach = on_attach,
						}
						if server_configs[server_name] then
							opts = vim.tbl_deep_extend("force", opts, server_configs[server_name])
						end
						require("lspconfig")[server_name].setup(opts)
					end,
				},
			})
		end,
	},
	{
		"jay-babu/mason-null-ls.nvim",
		event = "VimEnter",
		dependencies = "jose-elias-alvarez/null-ls.nvim",
		config = function()
			local null_ls = require("null-ls")

			-- ref: https://github.com/jose-elias-alvarez/null-ls.nvim/wiki/Avoiding-LSP-formatting-conflicts
			local lsp_disable = {
				["lua_ls"] = true,
			}

			local lsp_formatting = function(bufnr)
				vim.lsp.buf.format({
					filter = function(client)
						-- filter out client that you don't want to use
						if lsp_disable[client.name] then
							return false
						else
							return true
						end
					end,
					bufnr = bufnr,
				})
			end

			local augroup = vim.api.nvim_create_augroup("LspFormatting", {})

			null_ls.setup({
				sources = {
					null_ls.builtins.formatting.stylua,
					null_ls.builtins.formatting.goimports,
					null_ls.builtins.formatting.prettier,
					null_ls.builtins.formatting.shfmt,
					null_ls.builtins.code_actions.gitsigns,
				},
				-- disable format on save
				-- on_attach = function(client, bufnr)
				-- 	if client.supports_method("textDocument/formatting") then
				-- 		vim.api.nvim_clear_autocmds({ group = augroup, buffer = bufnr })
				-- 		vim.api.nvim_create_autocmd("BufWritePre", {
				-- 			group = augroup,
				-- 			buffer = bufnr,
				-- 			callback = function()
				-- 				lsp_formatting(bufnr)
				-- 			end,
				-- 		})
				-- 	end
				-- end,
			})

			require("mason-null-ls").setup({
				ensure_installed = nil,
				automatic_installation = true,
			})
		end,
	},
	{
		"nvimdev/lspsaga.nvim",
		event = "VeryLazy",
		keys = {
			{
				"gh",
				"<cmd>Lspsaga lsp_finder<CR>",
				mode = "n",
				desc = "Find the symbol's definition",
			},
			{
				"K",
				"<cmd>Lspsaga hover_doc<CR>",
				mode = "n",
				desc = "Hover document",
			},
		},
		config = function()
			require("lspsaga").setup({
				-- default
				debug = false,
				use_saga_diagnostic_sign = true,
				-- code action title icon
				code_action_prompt = { enable = true, sign = true, sign_priority = 40, virtual_text = true },
				max_preview_lines = 10,
				finder_action_keys = {
					open = "o",
					vsplit = "s",
					split = "i",
					quit = "q",
					scroll_down = "<C-f>",
					scroll_up = "<C-b>",
				},
				code_action_keys = { quit = "q", exec = "<CR>" },
				rename_action_keys = { quit = "<C-c>", exec = "<CR>" },
				border_style = "single",
				server_filetype_map = {},
				diagnostic_prefix_format = "%d. ",
				ui = {
					kind = require("catppuccin.groups.integrations.lsp_saga").custom_kind(),
				},
			})
		end,
	},
	{
		"j-hui/fidget.nvim",
		event = "VeryLazy",
		branch = "legacy",
		opts = {
			window = {
				blend = 0,
			},
			sources = {
				["null-ls"] = {
					ignore = true,
				},
			},
		},
	},
	{
		"ErichDonGubler/lsp_lines.nvim",
		event = "VeryLazy",
		config = function()
			vim.diagnostic.config({ virtual_text = false })
			require("lsp_lines").setup()
		end,
	},

	-- fuzzy-finder
	{
		"nvim-telescope/telescope.nvim",
		branch = "0.1.x",
		dependencies = {
			"nvim-telescope/telescope-fzf-native.nvim",
			build = "make",
			cond = function()
				return vim.fn.executable("make") == 1
			end,
			config = function()
				require("telescope").load_extension("fzf")
			end,
		},
		keys = {
			{
				"<leader>/",
				function()
					return require("telescope.builtin").current_buffer_fuzzy_find(
						require("telescope.themes").get_dropdown({
							winblend = 10,
							previewer = false,
						})
					)
				end,
				mode = "n",
				desc = "[/] Fuzzily search in current buffer",
			},
			{
				"<leader>gf",
				function()
					return require("telescope.builtin").git_files()
				end,
				mode = "n",
				desc = "Search [G]it [F]iles",
			},
			{
				"<leader>sf",
				function()
					return require("telescope.builtin").find_files()
				end,
				mode = "n",
				desc = "[S]earch [F]iles",
			},
			{
				"<leader>sw",
				function()
					return require("telescope.builtin").grep_string()
				end,
				mode = "n",
				desc = "[S]earch [W]ord",
			},
			{
				"<leader>sg",
				function()
					return require("telescope.builtin").live_grep()
				end,
				mode = "n",
				desc = "[S]earch by [G]rep",
			},
			{
				"<leader>sd",
				function()
					return require("telescope.builtin").diagnostics()
				end,
				mode = "n",
				desc = "[S]earch [D]iagnostics",
			},
		},
	},

	-- status line
	{
		"nvim-lualine/lualine.nvim",
		event = "VimEnter",
		dependencies = {
			{
				"f-person/git-blame.nvim",
				config = function()
					vim.g.gitblame_display_virtual_text = 0
					vim.g.gitblame_date_format = "%r"
					vim.g.gitblame_message_template = "<author>, <date>"
					vim.g.gitblame_ignored_filetypes = { "lazy" }
				end,
			},
		},
		config = function()
			local lualine = require("lualine")
			local lualine_require = require("lualine_require")
			local utils = require("lualine.utils.utils")

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
									return string.format("%s", ft)
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
					{ "branch", icon = "" },
					{
						"diagnostics",
						sections = { "error", "warn" },
						colored = false,
						always_visible = true,
					},
				},
				lualine_c = {},
				lualine_x = {
					{
						'require("gitblame").get_current_blame_text()',
						cond = is_blame_text_available,
					},
					{
						"location",
						fmt = function()
							return " %l  %v"
						end,
					},
					{ indent },
					{ "encoding", fmt = string.upper, icon = "" },
					{
						"fileformat",
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

			lualine.setup({
				options = {
					icon_enabled = true,
					theme = "catppuccin",
					section_separators = "",
					component_separators = "",
				},
				sections = sections_1,
			})
		end,
	},

	-- git
	{
		"lewis6991/gitsigns.nvim",
		event = "VeryLazy",
		config = true,
	},

	-- brackets
	{
		"andymass/vim-matchup",
		event = "VeryLazy",
		config = function()
			vim.g.matchup_matchparen_offscreen = { method = "popup" }
		end,
	},
	{
		"hrsh7th/nvim-insx",
		event = "InsertEnter",
		config = function()
			require("insx.preset.standard").setup()
		end,
	},

	-- UI
	{
		"folke/noice.nvim",
		event = "VeryLazy",
		dependencies = "rcarriga/nvim-notify",
		opts = {
			lsp = {
				override = {
					["vim.lsp.util.convert_input_to_markdown_lines"] = true,
					["vim.lsp.util.stylize_markdown"] = true,
					["cmp.entry.get_documentation"] = true,
				},
			},
			-- you can enable a preset for easier configuration
			presets = {
				command_palette = true, -- position the cmdline and popupmenu together
				long_message_to_split = true, -- long messages will be sent to a split
				lsp_doc_border = true, -- add a border to hover docs and signature help
			},
		},
	},

	-- syntax
	{
		"norcalli/nvim-colorizer.lua",
		event = { "BufNewFile", "BufReadPost" },
		config = true,
	},
	{
		"folke/todo-comments.nvim",
		event = "VeryLazy",
		config = true,
	},

	-- scroll bar
	{
		"petertriho/nvim-scrollbar",
		event = "VeryLazy",
		dependencies = "kevinhwang91/nvim-hlslens",
		config = function()
			require("scrollbar").setup({
				show = true,
				set_highlights = true,
				handle = {
					text = " ",
					color = "#3F4A5A",
					cterm = nil,
					highlight = "CursorColumn",
					hide_if_all_visible = true, -- Hides handle if all lines are visible
				},
				marks = {
					Search = {
						text = { "-", "=" },
						priority = 0,
						color = nil,
						cterm = nil,
						highlight = "Search",
					},
					Error = {
						text = { "-", "=" },
						priority = 1,
						color = nil,
						cterm = nil,
						highlight = "DiagnosticVirtualTextError",
					},
					Warn = {
						text = { "-", "=" },
						priority = 2,
						color = nil,
						cterm = nil,
						highlight = "DiagnosticVirtualTextWarn",
					},
					Info = {
						text = { "-", "=" },
						priority = 3,
						color = nil,
						cterm = nil,
						highlight = "DiagnosticVirtualTextInfo",
					},
					Hint = {
						text = { "-", "=" },
						priority = 4,
						color = nil,
						cterm = nil,
						highlight = "DiagnosticVirtualTextHint",
					},
					Misc = {
						text = { "-", "=" },
						priority = 5,
						color = nil,
						cterm = nil,
						highlight = "Normal",
					},
				},
				excluded_buftypes = {
					"terminal",
				},
				excluded_filetypes = {
					"prompt",
					"TelescopePrompt",
					"lazy",
				},
				autocmd = {
					render = {
						"BufWinEnter",
						"TabEnter",
						"TermEnter",
						"WinEnter",
						"CmdwinLeave",
						"VimResized",
						"WinScrolled",
					},
				},
				handlers = {
					diagnostic = true,
					search = true, -- Requires hlslens to be loaded, will run require("scrollbar.handlers.search").setup() for you
				},
			})
		end,
	},

	-- move
	{
		"folke/flash.nvim",
		event = "VeryLazy",
		keys = {
			{
				"f",
				mode = { "n", "x", "o" },
				function()
					require("flash").jump({
						search = { forward = true, wrap = false, multi_window = false },
					})
				end,
				desc = "Flash Forward",
			},
			{
				"F",
				mode = { "n", "x", "o" },
				function()
					require("flash").jump({
						search = { forward = false, wrap = false, multi_window = false },
					})
				end,
				desc = "Flash Backward",
			},
		},
	},

	-- join
	{
		"AckslD/nvim-trevJ.lua",
		event = "VeryLazy",
		keys = {
			{
				"J",
				function()
					require("trevj").format_at_cursor()
				end,
				mode = "v",
				noremap = true,
				silent = true,
			},
		},
		config = true,
	},

	-- manual
	{
		"folke/which-key.nvim",
		event = "VeryLazy",
		init = function()
			vim.o.timeout = true
			vim.o.timeoutlen = 300
		end,
		opts = {
			plugins = {
				marks = false,
				registers = false,
				presets = {
					operators = false,
					motions = false,
					text_objects = false,
					windows = false,
					nav = false,
					z = false,
					g = false,
				},
			},
			icons = {
				breadcrumb = "»",
				separator = "➜",
				group = "+",
			},
			window = {
				border = "none",
				position = "bottom",
				margin = { 1, 0, 1, 0 },
				padding = { 2, 2, 2, 2 },
			},
			layout = {
				height = { min = 4, max = 25 },
				width = { min = 20, max = 50 },
				spacing = 3,
			},
			hidden = { "<silent>", "<cmd>", "<Cmd>", "<CR>", "call", "lua", "^:", "^ " },
			show_help = true,
			triggers = { "<Leader>" },
		},
	},

	-- coding
	{
		"zsugabubus/crazy8.nvim",
		event = { "BufNewFile", "BufReadPost" },
	},
	{
		"lukas-reineke/indent-blankline.nvim",
		event = "VeryLazy",
		config = function()
			require("indent_blankline").setup({
				show_current_context = true,
				buftype_exclude = { "terminal" },
				filetype_exclude = {
					"help",
					"lazy",
					"log",
					"lspsagafinder",
					"lspinfo",
				},
			})
		end,
	},

	-- comment
	{
		"numToStr/Comment.nvim",
		event = "VeryLazy",
		config = function()
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
		end,
	},

	-- csv
	{
		"chen244/csv-tools.lua",
		ft = "csv",
		config = function()
			require("csvtools").setup({
				before = 10,
				after = 10,
				clearafter = false,
				showoverflow = false,
				titelflow = true,
			})
		end,
	},

	-- log
	{ "MTDL9/vim-log-highlighting", ft = "log" },
})
