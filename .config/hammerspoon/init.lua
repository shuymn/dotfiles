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

-- Vivaldi
-- ctrl+spaceでVivaldiを開く
hs.hotkey.bind({ "control" }, "space", function()
	toggleApp("Vivaldi", function(vivaldi)
		local space = hs.spaces.focusedSpace()
		local win = vivaldi:focusedWindow()
		hs.spaces.moveWindowToSpace(win, space)
		win:focus()
	end)
end)

local units = {
	right50 = { x = 0.50, y = 0.00, w = 0.50, h = 1.00 },
	left50 = { x = 0.00, y = 0.00, w = 0.50, h = 1.00 },
}

-- opt+ctrl+→で右半分に移動して、タブ位置を右寄せにする
local right = hs.hotkey.new({ "option", "control" }, "right", function()
	local app = hs.application.frontmostApplication()
	if app:name() == "Vivaldi" then
		hs.eventtap.keyStroke({ "command", "shift" }, "l", 200, app)
	end
	app:focusedWindow():move(units.right50, nil, true)
end)

-- opt+ctrl+←で左半分に移動して、タブ位置を左寄せにする
local left = hs.hotkey.new({ "option", "control" }, "left", function()
	local app = hs.application.frontmostApplication()
	if app:name() == "Vivaldi" then
		hs.eventtap.keyStroke({ "command", "shift" }, "h", 200, app)
	end
	app:focusedWindow():move(units.left50, nil, true)
end)

-- opt+ctrl+returnで最大化して、タブ位置を左寄せにする
local max = hs.hotkey.new({ "option", "control" }, "return", function()
	local app = hs.application.frontmostApplication()
	if app:name() == "Vivaldi" then
		hs.eventtap.keyStroke({ "command", "shift" }, "h", 200, app)
	end
	app:focusedWindow():maximize()
end)

-- ↑をVivaldiにフォーカスがある時だけ有効にする
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

-- Vivaldiでcmd+shift+pを押したときにIMEを英語入力にする
hs.hotkey.bind({ "command", "shift" }, "p", function()
	local app = hs.application.frontmostApplication()
	if app:name() == "Vivaldi" then
		hs.eventtap.keyStroke({}, 0x66, 200)
	end
	hs.eventtap.keyStroke({ "command", "shift" }, "p", 200, app)
end)

-- Vivaldiでctrl+shift+j/kを押したときにoption+↓/↑に変換する
hs.hotkey.bind({ "control", "shift" }, "j", function()
	local app = hs.application.frontmostApplication()
	if app:name() == "Vivaldi" then
		hs.eventtap.keyStroke({ "option" }, "down", 200, app)
	else
		hs.eventtap.keyStroke({ "control", "shift" }, "j", 200, app)
	end
end)

hs.hotkey.bind({ "control", "shift" }, "k", function()
	local app = hs.application.frontmostApplication()
	if app:name() == "Vivaldi" then
		hs.eventtap.keyStroke({ "option" }, "up", 200, app)
	else
		hs.eventtap.keyStroke({ "control", "shift" }, "k", 200, app)
	end
end)

-- ctrl+tでkittyを画面右半分に開く
hs.hotkey.bind({ "control" }, "t", function()
	toggleApp("kitty", function(kitty)
		local space = hs.spaces.focusedSpace()
		local win = kitty:focusedWindow()
		kitty:hide()
		hs.spaces.moveWindowToSpace(win, space)
		win:move(units.right50, nil, true)
		win:focus()
	end)
end)

-- ctrl+sでSlackを開く
hs.hotkey.bind({ "control" }, "s", function()
	toggleApp("Slack")
end)

-- ctrl+mでSpotifyを開く
hs.hotkey.bind({ "control" }, "m", function()
	toggleApp("Spotify")
end)
