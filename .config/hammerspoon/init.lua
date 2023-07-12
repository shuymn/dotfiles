-- defaults write org.hammerspoon.Hammerspoon MJConfigFile "~/.config/hammerspoon/init.lua"
hs.window.animationDuration = 0

local units = {
	right50 = { x = 0.50, y = 0.00, w = 0.50, h = 1.00 },
	left50 = { x = 0.00, y = 0.00, w = 0.50, h = 1.00 },
	top50 = { x = 0.00, y = 0.00, w = 1.00, h = 0.50 },
	bot50 = { x = 0.00, y = 0.50, w = 1.00, h = 0.50 },
}

hs.hotkey.bind({ "option", "control" }, "right", function()
	local app = hs.application.get("Vivaldi")
	if app ~= nil and app:isFrontmost() then
		hs.eventtap.keyStroke({ "command", "shift" }, "l", 0)
	end
	hs.window.focusedWindow():move(units.right50, nil, true)
end)
hs.hotkey.bind({ "option", "control" }, "left", function()
	local app = hs.application.get("Vivaldi")
	if app ~= nil and app:isFrontmost() then
		hs.eventtap.keyStroke({ "command", "shift" }, "h", 0)
	end
	hs.window.focusedWindow():move(units.left50, nil, true)
end)
hs.hotkey.bind({ "option", "control" }, "up", function()
	hs.window.focusedWindow():move(units.top50, nil, true)
end)
hs.hotkey.bind({ "option", "control" }, "down", function()
	hs.window.focusedWindow():move(units.bot50, nil, true)
end)
hs.hotkey.bind({ "option", "control" }, "return", function()
	hs.window.focusedWindow():maximize()
end)
