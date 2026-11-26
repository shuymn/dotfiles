-- Rex config migrated from Herdr, Ghostty and kitty.

-- Herdr (~/.config/herdr/config.toml), prefix ctrl+b
rex.bind("ctrl+b>ctrl+b", "pane.send_key", { key = "ctrl+b" })
rex.bind("ctrl+b>s", "pane.split", { direction = "down" })
rex.bind("ctrl+b>shift+k", "session.previous")
rex.bind("ctrl+b>shift+j", "session.next")
rex.bind("ctrl+b>shift+r", "client.mode.enter", { name = "resize" })
rex.bind("ctrl+b>[", "pane.copy_mode.enter")

rex.mode("resize", { exclusive = true })
rex.bind("resize/enter", "client.mode.exit")
rex.bind("resize/escape", "client.mode.exit")
rex.bind("resize/left", "pane.resize", { direction = "left" })
rex.bind("resize/down", "pane.resize", { direction = "down" })
rex.bind("resize/up", "pane.resize", { direction = "up" })
rex.bind("resize/right", "pane.resize", { direction = "right" })

-- Ghostty (~/.config/ghostty/config.ghostty)
rex.bind("cmd+c", "pane.copy")
rex.bind("cmd+v", "pane.paste")
rex.bind("cmd+0", "client.font.reset")
rex.bind("shift+cmd+,", "client.config.reload")

-- kitty (~/.config/kitty/kitty.conf)
rex.bind("ctrl+b>c", "client.tab.new")
rex.bind("ctrl+b>n", "client.tab.next")
rex.bind("ctrl+b>p", "client.tab.previous")
rex.bind("ctrl+b>v", "pane.split", { direction = "right" })
rex.bind("ctrl+b>h", "pane.focus", { direction = "left" })
rex.bind("ctrl+b>j", "pane.focus", { direction = "down" })
rex.bind("ctrl+b>k", "pane.focus", { direction = "up" })
rex.bind("ctrl+b>l", "pane.focus", { direction = "right" })
rex.bind("ctrl+b>z", "pane.zoom")
