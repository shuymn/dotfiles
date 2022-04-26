vim.opt.completeopt = { "menu", "menuone", "noselect" }

local cmp = require("cmp")
local types = require("cmp.types")
local luasnip = require("luasnip")

local has_words_before = function()
	local line, col = unpack(vim.api.nvim_win_get_cursor(0))
	return col ~= 0 and vim.api.nvim_buf_get_lines(0, line - 1, line, true)[1]:sub(col, col):match("%s") == nil
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
				omni = "[Omni]",
				spell = "[Spell]",
				emoji = "[Emoji]",
				calc = "[Calc]",
				treesitter = "[TS]",
				dictionary = "[Dict]",
				mocword = "[Mocword]",
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
		{ name = "nvim_lsp_signature_help", priority = 80 },
	}, {
		{ name = "buffer", priority = 50 },
		{ name = "omni", priority = 40 },
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

-- autopairs
local cmp_autopairs = require("nvim-autopairs.completion.cmp")
cmp.event:on("confirm_done", cmp_autopairs.on_confirm_done({ map_char = { tex = "" } }))
