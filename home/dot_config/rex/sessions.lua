-- One Rex session per repository or worktree, as Herdr workspaces were.
-- A session is found again by its label: "owner/repo" for a repository's main
-- checkout and "owner/repo@branch" for its other worktrees.

local shell = "com.superlogical.terminal.shell"
local terminal = "com.superlogical.terminal"
local home = os.getenv("HOME")

-- Actions run in the Rex server, whose PATH lacks the Nix and mise tools;
-- take the PATH that ~/.zshenv builds.
local tool_path
local function run(argv, cwd)
	if tool_path == nil then
		local z, zerr = rex.exec({ "/bin/zsh", "-c", "print -rn -- $PATH" })
		if z == nil or not z.ok then
			error("cannot read PATH from zsh: " .. (zerr or z.stderr), 0)
		end
		tool_path = z.stdout
	end
	local r, err = rex.exec(argv, { cwd = cwd, timeout = 25, env = { PATH = tool_path } })
	if r == nil then
		error(err, 0)
	end
	if not r.ok then
		error(table.concat(argv, " ") .. ": " .. (r.stderr ~= "" and r.stderr or ("exit " .. r.code)), 0)
	end
	return r.stdout
end

local function lines(text)
	local out = {}
	for line in text:gmatch("[^\n]+") do
		out[#out + 1] = line
	end
	return out
end

local function basename(path)
	return path:match("([^/]+)/*$")
end

local function tilde(path)
	if path:sub(1, #home + 1) == home .. "/" then
		return "~" .. path:sub(#home + 1)
	end
	return path
end

local function repo_label(root)
	return root:match("([^/]+/[^/]+)/*$") or basename(root)
end

-- The directory of the pane an action runs from: the shell's OSC 7 report,
-- else the foreground process's directory.
local function pane_dir(ctx)
	local r = rex.block.call(terminal, "pwd", { block_id = ctx.block_id })
	if r ~= nil and r.pwd ~= nil then
		-- A program may report a file:// URL (percent-encoded) or a plain path.
		local url_path = r.pwd:match("^file://[^/]*(/.*)$")
		if url_path == nil then
			return r.pwd
		end
		return (url_path:gsub("%%(%x%x)", function(h)
			return string.char(tonumber(h, 16))
		end))
	end
	local p = rex.block.call(terminal, "process", { block_id = ctx.block_id })
	if p ~= nil and p.foreground ~= nil and p.foreground.cwd ~= nil then
		return p.foreground.cwd
	end
	error("cannot tell this pane's directory", 0)
end

-- The repository's main checkout, for a directory anywhere in it or its worktrees.
-- git lists the main worktree first.
local function main_root(dir)
	local root = run({ "git", "worktree", "list", "--porcelain" }, dir):match("^worktree ([^\n]+)")
	if root == nil then
		error("no main worktree for " .. dir, 0)
	end
	return root
end

local function select_session(session_id)
	-- Only an app can switch; from the CLI there may be none.
	pcall(rex.client.queue, "session.select", { session_id = session_id })
	return { session_id = session_id }
end

local function open_session(label, dir)
	local list, err = rex.call("session.list")
	if list == nil then
		error(err, 0)
	end
	for _, s in ipairs(list.sessions) do
		if s.label == label then
			return select_session(s.session_id)
		end
	end
	local created, cerr = rex.call("session.create", {
		label = label,
		initial_windows = { { layout = rex.layout.block({ flavor = shell, options = { cwd = dir } }) } },
	})
	if created == nil then
		error(cerr, 0)
	end
	return select_session(created.session_id)
end

local function worktree_label(root, branch, path)
	if path == root then
		return repo_label(root)
	end
	return repo_label(root) .. "@" .. (branch or basename(path))
end

rex.action({
	name = "project_session",
	title = "Open Project Session…",
	description = "Pick a ghq repository and switch to its session, creating it if needed.",
	keywords = "ghq repository workspace",
	args = { dir = "string?" },
	run = function(ctx, args)
		local dir = args.dir
		if dir == nil then
			local dotfiles = home .. "/.dotfiles"
			local items = { { id = dotfiles, title = tilde(dotfiles), icon = "folder" } }
			local ghq_root = run({ "ghq", "root" }):gsub("\n$", "")
			for _, path in ipairs(lines(run({ "ghq", "list", "--full-path" }))) do
				-- ghq also lists worktrees, whose .git is a file.
				local head = io.open(path .. "/.git/HEAD")
				if head ~= nil then
					head:close()
					items[#items + 1] = {
						id = path,
						title = path:sub(#ghq_root + 2),
						icon = "folder",
					}
				end
			end
			dir = rex.ui.pick({ title = "Open project", placeholder = "Filter repositories", items = items })
			if dir == nil then
				return
			end
		end
		return open_session(repo_label(dir), dir)
	end,
})

rex.action({
	name = "worktree_session",
	title = "Open Worktree Session…",
	description = "Pick a worktree of this pane's repository and switch to its session.",
	keywords = "git wt worktree branch",
	run = function(ctx)
		local dir = pane_dir(ctx)
		local root = main_root(dir)
		local worktrees = rex.json.decode(run({ "git-wt", "--json" }, root))
		local items, by_path = {}, {}
		for _, wt in ipairs(worktrees) do
			if not wt.bare then
				by_path[wt.path] = wt
				items[#items + 1] = {
					id = wt.path,
					title = wt.branch or "(detached)",
					subtitle = tilde(wt.path),
					detail = wt.head,
					icon = "branch",
				}
			end
		end
		local path = rex.ui.pick({ title = "Open worktree", placeholder = "Filter branches", items = items })
		if path == nil then
			return
		end
		return open_session(worktree_label(root, by_path[path].branch, path), path)
	end,
})

rex.action({
	name = "home_session",
	title = "New Session from Home",
	run = function()
		local created, err = rex.call("session.create", {
			initial_windows = { { layout = rex.layout.block({ flavor = shell, options = { cwd = home } }) } },
		})
		if created == nil then
			error(err, 0)
		end
		return select_session(created.session_id)
	end,
})

rex.bind("ctrl+b>f", "project_session")
rex.bind("ctrl+b>shift+f", "worktree_session")
rex.bind("ctrl+b>shift+c", "home_session")
