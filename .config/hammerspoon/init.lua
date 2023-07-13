-- defaults write org.hammerspoon.Hammerspoon MJConfigFile "~/.config/hammerspoon/init.lua"

hs.window.animationDuration = 0
hs.hotkey.setLogLevel(0)

local units = {
	right50 = { x = 0.50, y = 0.00, w = 0.50, h = 1.00 },
	left50 = { x = 0.00, y = 0.00, w = 0.50, h = 1.00 },
}

local right = hs.hotkey.new({ "option", "control" }, "right", function()
	local app = hs.application.frontmostApplication()
	if app:name() == "Vivaldi" then
		hs.eventtap.keyStroke({ "command", "shift" }, "l", 200, app)
	end
	app:focusedWindow():move(units.right50, nil, true)
end)

local left = hs.hotkey.new({ "option", "control" }, "left", function()
	local app = hs.application.frontmostApplication()
	if app:name() == "Vivaldi" then
		hs.eventtap.keyStroke({ "command", "shift" }, "h", 200, app)
	end
	app:focusedWindow():move(units.left50, nil, true)
end)

local max = hs.hotkey.new({ "option", "control" }, "return", function()
	local app = hs.application.frontmostApplication()
	if app:name() == "Vivaldi" then
		hs.eventtap.keyStroke({ "command", "shift" }, "h", 200, app)
	end
	app:focusedWindow():maximize()
end)

hs.window.filter
	.new("Vivaldi")
	:subscribe(hs.window.filter.windowFocused, function()
		right:enable()
		left:enable()
		max:enable()
	end)
	:subscribe(hs.window.filter.windowUnfocused, function()
		right:disable()
		left:disable()
		max:disable()
	end)

hs.hotkey.bind({ "command", "shift" }, "p", function()
	local app = hs.application.frontmostApplication()
	if app:name() == "Vivaldi" then
		hs.eventtap.keyStroke({}, 0x66, 200)
	end
	hs.eventtap.keyStroke({ "command", "shift" }, "p", 200, app)
end)

hs.hotkey.bind({ "control" }, "t", function()
	local kitty = hs.application.get("kitty")
	if kitty == nil then
		hs.application.launchOrFocus("kitty")
	elseif kitty:isFrontmost() then
		kitty:hide()
	else
		-- https://github.com/asmagill/hs._asm.spaces
		local space = hs.spaces.focusedSpace()
		local win = kitty:focusedWindow()
		kitty:hide()
		hs.spaces.moveWindowToSpace(win, space)
		win = win:toggleFullScreen()
		win = win:toggleFullScreen()
		win:focus()
	end
end)
