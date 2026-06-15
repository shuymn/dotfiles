local cwd = ya.sync(function()
	return cx.active.current.cwd
end)

local function fail(content)
	ya.notify({ title = "git-root", content = content, timeout = 5, level = "warn" })
end

local function entry()
	local output, err = Command("git")
		:cwd(tostring(cwd()))
		:arg({ "rev-parse", "--show-toplevel" })
		:output()

	if err then
		return fail("Failed to run git: " .. err)
	elseif not output.status.success then
		return fail("Not in a git repository")
	end

	local root = output.stdout:gsub("\r\n$", ""):gsub("\n$", "")
	if root ~= "" then
		ya.emit("cd", { Url(root) })
	end
end

return { entry = entry }
