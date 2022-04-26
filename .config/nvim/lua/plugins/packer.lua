local my_packer = {}

vim.api.nvim_exec(
	[[
augroup vimrc_packer
  autocmd!
  autocmd BufWritePost .config/nvim/lua/rc/plugins.lua,.config/nvim/lua/plugins/*.lua PackerCompile
augroup END
]],
	true
)

vim.api.nvim_exec(
	[[
function! IsPluginInstalled(name) abort
  return luaeval("_G.packer_plugins['" .. a:name .. "'] ~= nil")
endfunction
]],
	true
)

my_packer.is_plugin_installed = function(name)
	return _G.packer_plugins[name] ~= nil
end

function AutocmdLazyConfig(plugin_name)
	local timer = vim.loop.new_timer()
	timer:start(
		1000,
		0,
		vim.schedule_wrap(function()
			if _G.packer_plugins[plugin_name].loaded then
				timer:close() -- Always close handles to avoid leaks.
				vim.cmd(string.format("doautocmd User %s", "packer-" .. plugin_name))
			end
		end)
	)
end

local function get_table_size(t)
	local count = 0
	for _, _ in pairs(t) do
		count = count + 1
	end
	return count
end

my_packer.count_plugins = function()
	return get_table_size(_G.packer_plugins)
end

require("packer").init({
	compile_path = vim.fn.stdpath("data") .. "/site/pack/loader/start/my-packer/plugin/packer.lua",
})

vim.api.nvim_create_user_command("ShowPluginReadme", function()
	local plugin_name = string.match(vim.fn.expand("<cWORD>"), "['\"].*/(.*)['\"]")
	local path = vim.fn.stdpath("data") .. "/site/pack/packer/*/" .. plugin_name .. "/README.md"

	vim.cmd("edit " .. vim.fn.resolve(path))
end, { force = true })

return my_packer
