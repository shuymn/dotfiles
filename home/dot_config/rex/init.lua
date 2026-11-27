-- Rex keeps the prefix keys of the terminals used before it (kitty, tmux,
-- Herdr) and Ghostty's Cmd shortcuts. Prefix is ctrl+b.

local shell = "com.superlogical.terminal.shell"
local terminal = "com.superlogical.terminal"

-- Prefix basics
rex.bind("ctrl+b>ctrl+b", "pane.send_key", { key = "ctrl+b" })
rex.bind("ctrl+b>r", "client.config.reload")
rex.bind("ctrl+b>,", "client.settings")

-- Tabs (kitty/tmux)
rex.bind("ctrl+b>c", "client.tab.new")
rex.bind("ctrl+b>n", "client.tab.next")
rex.bind("ctrl+b>p", "client.tab.previous")
for i = 1, 9 do
	rex.bind("ctrl+b>" .. i, "client.tab.goto", { index = i })
end

-- Panes (kitty/tmux)
rex.bind("ctrl+b>s", "pane.split", { direction = "down" })
rex.bind("ctrl+b>v", "pane.split", { direction = "right" })
rex.bind("ctrl+b>h", "pane.focus", { direction = "left" })
rex.bind("ctrl+b>j", "pane.focus", { direction = "down" })
rex.bind("ctrl+b>k", "pane.focus", { direction = "up" })
rex.bind("ctrl+b>l", "pane.focus", { direction = "right" })
rex.bind("ctrl+b>z", "pane.zoom")
-- tmux's prefix+y popup
rex.bind("ctrl+b>y", "pane.new_floating")

-- Sessions (Herdr workspaces)
rex.bind("ctrl+b>shift+k", "session.previous")
rex.bind("ctrl+b>shift+j", "session.next")
rex.bind("ctrl+b>w", "session.switch")
rex.bind("ctrl+b>g", "pane.go_to")
-- Project, worktree and home sessions: sessions.lua
require("sessions")

-- Resize mode (Herdr); h/j/k/l also work, as tmux's prefix+HJKL did.
rex.bind("ctrl+b>shift+r", "client.mode.enter", { name = "resize" })
rex.mode("resize", { exclusive = true })
rex.bind("resize/enter", "client.mode.exit")
rex.bind("resize/escape", "client.mode.exit")
for key, direction in pairs({ left = "left", down = "down", up = "up", right = "right", h = "left", j = "down", k = "up", l = "right" }) do
	rex.bind("resize/" .. key, "pane.resize", { direction = direction })
	rex.bind("resize/shift+" .. key, "pane.resize", { direction = direction, amount = 15 })
end
rex.bind("resize/=", "pane.balance")

-- Copy mode, and the scrollback in Neovim as kitty_scrollback_nvim did.
rex.bind("ctrl+b>[", "pane.copy_mode.enter")

rex.action({
	name = "scrollback_nvim",
	title = "Open Scrollback in Neovim",
	keywords = "scrollback history nvim",
	run = function(ctx)
		-- Without max_bytes, format fails with too_large on a big scrollback; with it,
		-- the rest comes back in parts to read with blob_read. 960 KiB is the cap.
		local screen, err = rex.block.call(terminal, "format", {
			block_id = ctx.block_id,
			format = "text",
			trim = true,
			max_bytes = 983040,
		})
		if screen == nil then
			error(err, 0)
		end
		local parts = { screen.content or "" }
		if screen.id ~= nil then
			local offset = #parts[1]
			repeat
				local part, perr = rex.block.call(terminal, "blob_read", { block_id = ctx.block_id, id = screen.id, offset = offset })
				if part == nil then
					error(perr, 0)
				end
				parts[#parts + 1] = part.data
				offset = offset + #part.data
			until part.eof or #part.data == 0
		end

		local path = os.tmpname()
		local f = assert(io.open(path, "w"))
		f:write(table.concat(parts))
		f:close()

		local _, lerr = rex.session.new_layer({
			bounds = { 0.03, 0.03, 0.94, 0.94 },
			focus = true,
			layout = rex.layout.block({
				flavor = shell,
				-- Open the file, remove it, then let nvim read it from stdin, so
				-- closing the layer (which kills nvim) leaves nothing behind.
				options = { command = { "sh", "-c", 'exec 3<"$1" && rm -f -- "$1" && exec nvim -R + - <&3', "sh", path } },
			}),
		})
		if lerr ~= nil then
			os.remove(path)
			error(lerr, 0)
		end
	end,
})
rex.bind("ctrl+b>]", "scrollback_nvim")

-- Ghostty
rex.bind("cmd+c", "pane.copy")
rex.bind("cmd+v", "pane.paste")
rex.bind("cmd+0", "client.font.reset")
rex.bind("shift+cmd+,", "client.config.reload")
