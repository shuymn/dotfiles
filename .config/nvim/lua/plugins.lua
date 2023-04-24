local install_path = vim.fn.stdpath("data") .. "/site/pack/packer/start/packer.nvim"

if vim.fn.empty(vim.fn.glob(install_path)) > 0 then
	return
end

require("plugins/packer")

return require("packer").startup({
	function(use)
		use({ "wbthomason/packer.nvim" })

		-- vim script library
		use({ "tpope/vim-repeat" })

		-- lua library
		use({ "nvim-lua/popup.nvim" })
		use({ "nvim-lua/plenary.nvim" })
		use({ "tami5/sqlite.lua", module = "sqlite" })
		use({ "MunifTanjim/nui.nvim" })

		-- font
		use({ "kyazdani42/nvim-web-devicons" })

		-- notify
		use({ "rcarriga/nvim-notify", event = "VimEnter" })

		-- colorscheme
		local colorscheme = "onedark.nvim"
		use({
			"navarasu/onedark.nvim",
			config = function()
				require("plugins/onedark")
			end,
		})
		-- use({
		-- 	"EdenEast/nightfox.nvim",
		-- 	disable = true,
		-- 	config = function()
		-- 		require("plugins/nightfox")
		-- 	end,
		-- })

		-- auto completion
		-- use({
		-- 	"hrsh7th/nvim-cmp",
		-- 	requires = {
		-- 		{ "L3MON4D3/LuaSnip", opt = true, event = "VimEnter" },
		-- 		{ "windwp/nvim-autopairs", opt = true, event = "VimEnter" },
		-- 	},
		-- 	after = { "lspkind-nvim", "LuaSnip", "nvim-autopairs" },
		-- 	config = function()
		-- 		require("plugins/nvim-cmp")
		-- 	end,
		-- })
		-- use({
		-- 	"onsails/lspkind-nvim",
		-- 	event = "VimEnter",
		-- 	config = function()
		-- 		require("plugins/lspkind")
		-- 	end,
		-- })
		-- use({ "hrsh7th/cmp-nvim-lsp", after = "nvim-cmp" })
		-- use({ "hrsh7th/cmp-nvim-lsp-signature-help", after = "nvim-cmp" })
		-- use({ "hrsh7th/cmp-nvim-lsp-document-symbol", after = "nvim-cmp" })
		-- use({ "hrsh7th/cmp-buffer", after = "nvim-cmp" })
		-- use({ "hrsh7th/cmp-path", after = "nvim-cmp" })
		-- use({ "hrsh7th/cmp-nvim-lua", after = "nvim-cmp" })
		-- use({ "saadparwaiz1/cmp_luasnip", after = "nvim-cmp" })
		-- use({ "hrsh7th/cmp-omni", after = "nvim-cmp" })
		-- use({ "hrsh7th/cmp-calc", after = "nvim-cmp" })
		-- use({ "hrsh7th/cmp-emoji", after = "nvim-cmp" })
		-- use({ "f3fora/cmp-spell", after = "nvim-cmp" })
		-- use({ "yutkat/cmp-mocword", after = "nvim-cmp" })
		-- use({
		-- 	"uga-rosa/cmp-dictionary",
		-- 	after = "nvim-cmp",
		-- 	config = function()
		-- 		require("plugins/cmp-dictionary")
		-- 	end,
		-- })
		-- use({ "ray-x/cmp-treesitter", after = { "nvim-cmp", "nvim-treesitter" } })
		-- use({ "hrsh7th/cmp-cmdline", after = "nvim-cmp" })

		-- lsp
		-- use({
		-- 	"neovim/nvim-lspconfig",
		-- 	after = "cmp-nvim-lsp",
		-- 	config = function()
		-- 		require("plugins/nvim-lspconfig")
		-- 	end,
		-- })
		-- use({
		-- 	"williamboman/nvim-lsp-installer",
		-- 	requires = { { "RRethy/vim-illuminate", opt = true } },
		-- 	after = { "nvim-lspconfig", "vim-illuminate", "nlsp-settings.nvim" },
		-- 	config = function()
		-- 		require("plugins/nvim-lsp-installer")
		-- 	end,
		-- })
		-- use({
		-- 	"tamago324/nlsp-settings.nvim",
		-- 	after = { "nvim-lspconfig" },
		-- 	config = function()
		-- 		require("plugins/nlsp-settings")
		-- 	end,
		-- })
		-- use({ "weilbith/nvim-lsp-smag", after = "nvim-lspconfig" })

		-- lsp ui
		-- use({
		-- 	"tami5/lspsaga.nvim",
		-- 	after = "nvim-lsp-installer",
		-- 	config = function()
		-- 		require("plugins/lspsaga")
		-- 	end,
		-- })
		-- use({ "folke/lsp-colors.nvim", event = "VimEnter" })
		-- use({
		-- 	"folke/trouble.nvim",
		-- 	after = { "nvim-lsp-installer", "lsp-colors.nvim" },
		-- 	config = function()
		-- 		require("plugins/trouble")
		-- 	end,
		-- })
		-- use({
		-- 	"j-hui/fidget.nvim",
		-- 	after = "nvim-lsp-installer",
		-- 	config = function()
		-- 		require("plugins/fidget")
		-- 	end,
		-- })

		-- fuzzy finder
		-- use({
		-- 	"nvim-telescope/telescope.nvim",
		-- 	event = "VimEnter",
		-- 	config = function()
		-- 		require("plugins/telescope")
		-- 	end,
		-- })
		-- use({
		-- 	"nvim-telescope/telescope-frecency.nvim",
		-- 	after = { "telescope.nvim" },
		-- 	config = function()
		-- 		require("telescope").load_extension("frecency")
		-- 	end,
		-- })
		-- use({
		-- 	"nvim-telescope/telescope-packer.nvim",
		-- 	after = { "telescope.nvim" },
		-- 	config = function()
		-- 		require("telescope").load_extension("packer")
		-- 	end,
		-- })
		-- use({ "nvim-telescope/telescope-symbols.nvim", after = { "telescope.nvim" } })

		-- treesitter
		use({
			"nvim-treesitter/nvim-treesitter",
			event = "VimEnter",
			run = ":TSUpdate",
			config = function()
				require("plugins/nvim-treesitter")
			end,
		})
		use({ "yioneko/nvim-yati", after = "nvim-treesitter" })
		use({
			"romgrk/nvim-treesitter-context",
			disable = true,
			after = "nvim-treesitter",
		})
		use({ "p00f/nvim-ts-rainbow", after = { "nvim-treesitter" } })
		use({ "JoosepAlviste/nvim-ts-context-commentstring", after = { "nvim-treesitter" } })
		use({
			"haringsrob/nvim_context_vt",
			after = { "nvim-treesitter", colorscheme },
			config = function()
				require("plugins/nvim_context_vt")
			end,
		})
		-- use({
		-- 	"m-demare/hlargs.nvim",
		-- 	after = { "nvim-treesitter" },
		-- 	config = function()
		-- 		require("plugins/hlargs")
		-- 	end,
		-- })

		-- treesitter textobject & operator
		use({ "nvim-treesitter/nvim-treesitter-textobjects", after = { "nvim-treesitter" } })
		use({
			"mfussenegger/nvim-ts-hint-textobject",
			after = { "nvim-treesitter" },
			config = function()
				require("plugins/nvim-ts-hint-textobject")
			end,
		})
		use({
			"David-Kunz/treesitter-unit",
			after = { "nvim-treesitter" },
			config = function()
				require("plugins/treesitter-unit")
			end,
		})
		-- use({
		-- 	"mizlan/iswap.nvim",
		-- 	after = { "nvim-treesitter" },
		-- 	disable = true,
		-- 	config = function()
		-- 		require("plugins/iswap")
		-- 	end,
		-- })

		-- status line
		use({
			"nvim-lualine/lualine.nvim",
			after = { colorscheme },
			requires = { "kyazdani42/nvim-web-devicons", opt = true },
			config = function()
				require("plugins/lualine")
			end,
		})
		use({
			"SmiteshP/nvim-gps",
			requires = { { "nvim-treesitter/nvim-treesitter", opt = true } },
			after = "nvim-treesitter",
			config = function()
				require("nvim-gps").setup()
			end,
		})

		-- buffer line
		-- use({
		-- 	"akinsho/bufferline.nvim",
		-- 	after = colorscheme,
		-- 	config = function()
		-- 		require("plugins/bufferline")
		-- 	end,
		-- })

		-- syntax
		use({
			"RRethy/vim-illuminate",
			event = "VimEnter",
			config = function()
				require("plugins/vim-illuminate")
			end,
		})
		use({
			"norcalli/nvim-colorizer.lua",
			event = "VimEnter",
			config = function()
				require("colorizer").setup()
			end,
			use({
				"t9md/vim-quickhl",
				event = "VimEnter",
				config = function()
					vim.cmd("source ~/.config/nvim/rc/plugins/vim-quickhl.vim")
				end,
			}),
		})
		use({
			"folke/todo-comments.nvim",
			event = "VimEnter",
			config = function()
				require("plugins/todo-comments")
			end,
		})
		use({
			"mvllow/modes.nvim",
			event = "VimEnter",
			config = function()
				require("plugins/modes")
			end,
		})

		-- sidebar
		-- use({
		-- 	"GustavoKatel/sidebar.nvim",
		-- 	disable = true,
		-- 	config = function()
		-- 		require("plugins/sidebar")
		-- 	end,
		-- })

		-- menu
		-- use({
		-- 	"sunjon/stylish.nvim",
		-- 	event = "VimEnter",
		-- 	config = function()
		-- 		require("plugins/stylish")
		-- 	end,
		-- })

		-- startup
		-- use({
		-- 	"goolord/alpha-nvim",
		-- 	config = function()
		-- 		require("plugins/alpha-nvim")
		-- 	end,
		-- })

		-- scrollbar
		use({
			"petertriho/nvim-scrollbar",
			requires = { { "kevinhwang91/nvim-hlslens", opt = true } },
			after = { colorscheme, "nvim-hlslens" },
			config = function()
				require("plugins/nvim-scrollbar")
			end,
		})

		-- move
		use({
			"phaazon/hop.nvim",
			event = "VimEnter",
			config = function()
				require("plugins/hop")
			end,
		})
		use({
			"unblevable/quick-scope",
			event = "VimEnter",
			config = function()
				vim.cmd("source ~/.config/nvim/rc/plugins/quick-scope.vim")
			end,
		})
		use({
			"ggandor/lightspeed.nvim",
			event = "VimEnter",
			config = function()
				require("plugins/lightspeed")
			end,
		})
		use({
			"haya14busa/vim-edgemotion",
			event = "VimEnter",
			config = function()
				vim.cmd("source ~/.config/nvim/rc/plugins/vim-edgemotion.vim")
			end,
		})
		use({
			"machakann/vim-columnmove",
			event = "VimEnter",
			config = function()
				vim.cmd("source ~/.config/nvim/rc/plugins/vim-columnmove.vim")
			end,
		})
		use({
			"justinmk/vim-ipmotion",
			event = "VimEnter",
			config = function()
				vim.cmd("source ~/.config/nvim/rc/plugins/vim-ipmotion.vim")
			end,
		})
		use({
			"bkad/CamelCaseMotion",
			event = "VimEnter",
			config = function()
				vim.cmd("source ~/.config/nvim/rc/plugins/CamelCaseMotion.vim")
			end,
		})

		-- jump
		use({
			"osyo-manga/vim-milfeulle",
			event = "VimEnter",
			config = function()
				vim.cmd("source ~/.config/nvim/rc/plugins/vim-milfeulle.vim")
			end,
		})

		-- select
		use({
			"kana/vim-niceblock",
			event = "VimEnter",
			config = function()
				vim.cmd("source ~/.config/nvim/rc/plugins/vim-niceblock.vim")
			end,
		})

		-- edit
		use({
			"thinca/vim-partedit",
			cmd = { "Partedit" },
		})

		-- operator
		use({
			"mopp/vim-operator-convert-case",
			requires = { { "kana/vim-operator-user", event = "VimEnter" } },
			after = { "vim-operator-user" },
			config = function()
				vim.cmd("source ~/.config/nvim/rc/plugins/vim-operator-convert-case.vim")
			end,
		})
		use({
			"gbprod/substitute.nvim",
			event = "VimEnter",
			config = function()
				require("plugins/substitute")
			end,
		})
		use({
			"machakann/vim-sandwich",
			config = function()
				vim.cmd("source ~/.config/nvim/rc/plugins/vim-sandwich.vim")
			end,
		})

		-- join
		use({
			"AckslD/nvim-trevJ.lua",
			module = "trevj",
			after = { "nvim-treesitter" },
			config = function()
				require("plugins/nvim-trevJ")
			end,
		})

		-- calc
		-- use({
		-- 	"deris/vim-rengbang",
		-- 	event = "VimEnter",
		-- 	config = function()
		-- 		vim.cmd("source ~/.config/nvim/rc/plugins/vim-rengbang.vim")
		-- 	end,
		-- })
		-- use({
		-- 	"monaqa/dial.nvim",
		-- 	config = function()
		-- 		require("plugins/dial")
		-- 	end,
		-- })

		-- yank
		use({
			"gbprod/yanky.nvim",
			event = "VimEnter",
			config = function()
				require("plugins/yanky")
			end,
		})
		-- use({
		-- 	"AckslD/nvim-neoclip.lua",
		-- 	requires = { { "nvim-telescope/telescope.nvim", opt = true }, { "tami5/sqlite.lua", opt = true } },
		-- 	after = { "telescope.nvim", "sqlite.lua" },
		-- 	config = function()
		-- 		require("plugins/nvim-neoclip")
		-- 	end,
		-- })

		-- paste
		-- use({
		-- 	"tversteeg/registers.nvim",
		-- 	event = "VimEnter",
		-- 	config = function()
		-- 		vim.cmd("source ~/.config/nvim/rc/plugins/registers.vim")
		-- 	end,
		-- })
		-- use({
		-- 	"AckslD/nvim-anywise-reg.lua",
		-- 	event = "VimEnter",
		-- 	config = function()
		-- 		require("plugins/nvim-anywise-reg")
		-- 	end,
		-- })

		-- find
		use({
			"kevinhwang91/nvim-hlslens",
			event = "VimEnter",
			config = function()
				vim.cmd("source ~/.config/nvim/rc/plugins/nvim-hlslens.vim")
			end,
		})
		use({
			"haya14busa/vim-asterisk",
			event = "VimEnter",
			config = function()
				vim.cmd("source ~/.config/nvim/rc/plugins/vim-asterisk.vim")
			end,
		})

		-- replace
		-- use({ "lambdalisue/reword.vim", event = "VimEnter" })
		-- use({ "haya14busa/vim-metarepeat", event = "VimEnter" })

		-- grep
		-- use({
		-- 	"windwp/nvim-spectre",
		-- 	event = "VimEnter",
		-- 	config = function()
		-- 		require("plugins/nvim-spectre")
		-- 	end,
		-- })

		-- filer
		-- use({
		-- 	"nvim-neo-tree/neo-tree.nvim",
		-- 	branch = "main",
		-- 	requires = {
		-- 		"MunifTanjim/nui.nvim",
		-- 	},
		-- 	event = "VimEnter",
		-- 	config = function()
		-- 		require("plugins/neo-tree")
		-- 	end,
		-- })

		-- buffer operation
		use({ "wsdjeg/vim-fetch", event = "VimEnter" })
		use({ "famiu/bufdelete.nvim", event = "VimEnter" })
		use({
			"stevearc/stickybuf.nvim",
			event = "VimEnter",
			config = function()
				require("plugins/stickybuf")
			end,
		})

		-- window
		use({
			"kwkarlwang/bufresize.nvim",
			event = "VimEnter",
			config = function()
				require("plugins/bufresize")
			end,
		})

		-- undo
		use({
			"simnalamburt/vim-mundo",
			cmd = { "MundoShow" },
		})

		-- diff
		-- use({
		-- 	"AndrewRadev/linediff.vim",
		-- 	cmd = { "Linediff" },
		-- })

		-- mark
		-- use({
		-- 	"chentoast/marks.nvim",
		-- 	event = "VimEnter",
		-- 	config = function()
		-- 		require("plugins/marks")
		-- 	end,
		-- })

		-- fold
		-- use({
		-- 	"lambdalisue/readablefold.vim",
		-- 	event = "VimEnter",
		-- })

		-- manual
		-- use({
		-- 	"folke/which-key.nvim",
		-- 	event = "VimEnter",
		-- 	config = function()
		-- 		require("plugins/which-key")
		-- 	end,
		-- })

		-- quickfix
		use({
			"drmingdrmer/vim-toggle-quickfix",
			event = "VimEnter",
			config = function()
				vim.cmd("source ~/.config/nvim/rc/plugins/vim-toggle-quickfix.vim")
			end,
		})
		use({
			"kevinhwang91/nvim-bqf",
			ft = "qf",
			config = function()
				require("plugins/nvim-bqf")
			end,
		})
		use({
			"gabrielpoca/replacer.nvim",
			event = "VimEnter",
			config = function()
				vim.cmd("source ~/.config/nvim/rc/plugins/replacer.vim")
			end,
		})

		-- spell
		-- use({
		-- 	"Pocco81/AbbrevMan.nvim",
		-- 	event = "VimEnter",
		-- 	config = function()
		-- 		require("plugins/AbbrevMan")
		-- 	end,
		-- })

		-- command
		-- use({
		-- 	"tyru/capture.vim",
		-- 	cmd = { "Capture" },
		-- })
		-- use({
		-- 	"jghauser/mkdir.nvim",
		-- 	event = "VimEnter",
		-- 	config = function()
		-- 		require("mkdir")
		-- 	end,
		-- })
		-- use({ "sQVe/sort.nvim", cmd = { "Sort" } })

		-- terminal
		-- use({
		-- 	"akinsho/toggleterm.nvim",
		-- 	event = "VimEnter",
		-- 	config = function()
		-- 		require("plugins/toggleterm")
		-- 	end,
		-- })

		-- screenshot
		-- use({ "segeljakt/vim-silicon", cmd = { "Silicon" } })

		-- command palette
		-- use({
		-- 	"mrjones2014/legendary.nvim",
		-- 	config = function()
		-- 		require("plugins/legendary")
		-- 	end,
		-- })
		-- use({
		-- 	"stevearc/dressing.nvim",
		-- 	event = "VimEnter",
		-- 	config = function()
		-- 		require("plugins/dressing")
		-- 	end,
		-- })

		-- browser integration
		-- use({
		-- 	"tyru/open-browser.vim",
		-- 	event = "VimEnter",
		-- 	config = function()
		-- 		vim.cmd("source ~/.config/nvim/rc/plugins/open-browser.vim")
		-- 	end,
		-- })
		-- use({ "tyru/open-browser-github.vim", after = { "open-browser.vim" } })

		-- template
		-- use({
		-- 	"mattn/vim-sonictemplate",
		-- 	cmd = { "Template" },
		-- })

		-- coding
		use({ "zsugabubus/crazy8.nvim", event = { "BufNewFile", "BufReadPost" } })
		use({
			"lfilho/cosco.vim",
			event = "VimEnter",
			config = function()
				vim.cmd("source ~/.config/nvim/rc/plugins/cosco.vim")
			end,
		})
		use({
			"lukas-reineke/indent-blankline.nvim",
			-- after = { colorscheme },
			event = "VimEnter",
			config = function()
				require("plugins/indent-blankline")
			end,
		})

		-- comment
		use({
			"numToStr/Comment.nvim",
			event = "VimEnter",
			config = function()
				require("plugins/Comment")
			end,
		})

		-- annotation
		-- use({
		-- 	"danymat/neogen",
		-- 	after = { "nvim-treesitter" },
		-- 	config = function()
		-- 		require("plugins/neogen")
		-- 	end,
		-- })

		-- brackets
		use({
			"andymass/vim-matchup",
			after = { "nvim-treesitter" },
			config = function()
				vim.cmd("source ~/.config/nvim/rc/plugins/vim-matchup.vim")
			end,
		})
		use({
			"windwp/nvim-autopairs",
			event = "VimEnter",
			config = function()
				require("plugins/nvim-autopairs")
			end,
		})
		-- use({
		-- 	"windwp/nvim-ts-autotag",
		-- 	requires = { { "nvim-treesitter/nvim-treesitter", opt = true } },
		-- 	after = { "nvim-treesitter" },
		-- 	config = function()
		-- 		require("plugins/nvim-ts-autotag")
		-- 	end,
		-- })
		-- code jump
		-- use({
		-- 	"rgroli/other.nvim",
		-- 	event = "VimEnter",
		-- 	config = function()
		-- 		require("plugins/other")
		-- 	end,
		-- })

		-- test
		-- use({
		-- 	"klen/nvim-test",
		-- 	after = { "nvim-treesitter" },
		-- 	config = function()
		-- 		require("plugins/nvim-test")
		-- 	end,
		-- })
		-- if vim.fn.executable("cargo") == 1 then
		-- 	use({
		-- 		"michaelb/sniprun",
		-- 		disable = true,
		-- 		run = "bash install.sh",
		-- 		cmd = { "SnipRun" },
		-- 	})
		-- end

		-- lint
		-- use({
		-- 	"jose-elias-alvarez/null-ls.nvim",
		-- 	after = "nvim-lsp-installer",
		-- 	config = function()
		-- 		require("plugins/null-ls")
		-- 	end,
		-- })

		-- format
		use({ "gpanders/editorconfig.nvim", event = "VimEnter" })
		use({
			"ntpeters/vim-better-whitespace",
			event = "VimEnter",
			config = function()
				vim.cmd("source ~/.config/nvim/rc/plugins/vim-better-whitespace.vim")
			end,
		})

		-- outline
		-- use({
		-- 	"stevearc/aerial.nvim",
		-- 	event = "VimEnter",
		-- 	config = function()
		-- 		require("plugins/aerial")
		-- 	end,
		-- })

		-- snippet
		-- use({
		-- 	"L3MON4D3/LuaSnip",
		-- 	after = { "friendly-snippets" },
		-- 	config = function()
		-- 		require("plugins/LuaSnip")
		-- 	end,
		-- })
		-- use({
		-- 	"kevinhwang91/nvim-hclipboard",
		-- 	after = { "LuaSnip" },
		-- 	config = function()
		-- 		require("hclipboard").start()
		-- 	end,
		-- })

		-- snippet pack
		-- use({ "rafamadriz/friendly-snippets", event = "VimEnter" })
		-- project
		-- use({
		-- 	"ahmedkhalf/project.nvim",
		-- 	after = { "telescope.nvim" },
		-- 	config = function()
		-- 		require("plugins/project")
		-- 	end,
		-- })
		-- use({
		-- 	"klen/nvim-config-local",
		-- 	config = function()
		-- 		require("plugins/nvim-config-local")
		-- 	end,
		-- })

		-- git
		-- use({
		-- 	"TimUntersberger/neogit",
		-- 	event = "VimEnter",
		-- 	config = function()
		-- 		require("plugins/neogit")
		-- 	end,
		-- })
		-- use({
		-- 	"sindrets/diffview.nvim",
		-- 	event = "VimEnter",
		-- 	config = function()
		-- 		require("plugins/diffview")
		-- 	end,
		-- })
		-- use({
		-- 	"akinsho/git-conflict.nvim",
		-- 	event = "VimEnter",
		-- 	config = function()
		-- 		require("git-conflict").setup()
		-- 	end,
		-- })
		use({
			"lewis6991/gitsigns.nvim",
			requires = { "nvim-lua/plenary.nvim" },
			event = "VimEnter",
			config = function()
				require("plugins/gitsigns")
			end,
		})
		-- use({ "rhysd/committia.vim" })
		-- use({ "hotwatermorning/auto-git-diff", ft = { "gitrebase" } })
		-- use({
		-- 	"f-person/git-blame.nvim",
		-- 	config = function()
		-- 		vim.cmd("source ~/.config/nvim/rc/plugins/git-blame.vim")
		-- 	end,
		-- })

		-- GitHub
		-- use({ "pwntester/octo.nvim", cmd = { "Octo" } })

		-- repl
		-- use({
		-- 	"hkupty/iron.nvim",
		-- 	event = "VimEnter",
		-- 	disable = true,
		-- 	config = function()
		-- 		require("plugins/iron")
		-- 	end,
		-- })

		-- javascript
		-- use({
		-- 	"vuki656/package-info.nvim",
		-- 	requires = "MunifTanjim/nui.nvim",
		-- 	event = "VimEnter",
		-- 	config = function()
		-- 		require("plugins/package-info")
		-- 	end,
		-- })
		-- use({
		-- 	"bennypowers/nvim-regexplainer",
		-- 	requires = {
		-- 		"nvim-lua/plenary.nvim",
		-- 		"MunifTanjim/nui.nvim",
		-- 		{ "nvim-treesitter/nvim-treesitter", opt = true },
		-- 	},
		-- 	after = { "nvim-treesitter" },
		-- 	config = function()
		-- 		require("plugins/nvim-regexplainer")
		-- 	end,
		-- })

		-- rust
		-- use({
		-- 	"simrat39/rust-tools.nvim",
		-- 	after = { "nvim-lspconfig", "nvim-lsp-installer" },
		-- 	config = function()
		-- 		require("plugins/rust-tools")
		-- 	end,
		-- })

		-- markdown
		-- use({ "iamcco/markdown-preview.nvim", ft = { "markdown" }, run = ":call mkdp#util#install()" })
		-- use({
		-- 	"SidOfc/mkdx",
		-- 	ft = { "markdown" },
		-- 	setup = function()
		-- 		vim.cmd("source ~/.config/nvim/rc/plugins/mkdx.vim")
		-- 	end,
		-- })
		-- use({
		-- 	"dhruvasagar/vim-table-mode",
		-- 	cmd = { "tablemodeenable" },
		-- 	config = function()
		-- 		vim.cmd("source ~/.config/nvim/rc/plugins/vim-table-mode.vim")
		-- 	end,
		-- })

		-- sql
		use({ "alcesleo/vim-uppercase-sql", event = "VimEnter" })

		-- csv
		use({
			"chen244/csv-tools.lua",
			ft = { "csv" },
			config = function()
				require("plugins/csv-tools")
			end,
		})

		-- log
		use({ "MTDL9/vim-log-highlighting", ft = { "log" } })
	end,
	config = {
		max_jobs = 10,
	},
})
