-- defaults write org.hammerspoon.Hammerspoon MJConfigFile "~/.config/hammerspoon/init.lua"

hs.window.animationDuration = 0
hs.hotkey.setLogLevel(0)

local function toggleApp(name, callback)
	local app = hs.application.get(name)
	if app == nil then
		hs.application.launchOrFocus(name)
	elseif app:isFrontmost() then
		app:hide()
	elseif callback == nil then
		-- https://github.com/asmagill/hs._asm.spaces
		local space = hs.spaces.focusedSpace()
		local win = app:focusedWindow()
		app:hide()
		hs.spaces.moveWindowToSpace(win, space)
		win = win:maximize()
		win:focus()
	else
		callback(app)
	end
end

-- ctrl+mでSpotifyを開く
hs.hotkey.bind({ "control" }, "m", function()
	toggleApp("Spotify")
end)
