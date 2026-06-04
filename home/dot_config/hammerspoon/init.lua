-- defaults write org.hammerspoon.Hammerspoon MJConfigFile "~/.config/hammerspoon/init.lua"

hs.window.animationDuration = 0
hs.hotkey.setLogLevel(0)
hs.application.enableSpotlightForNameSearches(true)

local function toggleApp(name, callback)
	local app = hs.application.get(name)
	if app == nil then
		hs.application.launchOrFocus(name)
	elseif app:isFrontmost() then
		app:hide()
	elseif callback == nil then
		local space = hs.spaces.focusedSpace()
		local win = app:focusedWindow()
		app:hide()
		hs.spaces.moveWindowToSpace(win, space)
		win:focus()
		win:maximize()
	else
		callback(app)
	end
end

local function getWindow(name, opts)
	opts = opts or {}

	local app = hs.application.get(name)
	if not app then
		if opts.launchIfMissing then
			hs.application.launchOrFocus(name)
			app = hs.application.get(name)
		end
		if not app then
			return nil
		end
	end

	-- 1) フォーカス中のウィンドウを最優先
	if opts.preferFocused ~= false then
		local fw = app:focusedWindow()
		if fw and (not opts.onlyStandard or fw:isStandard()) and (not opts.onlyVisible or fw:isVisible()) then
			return fw
		end
	end

	-- 2) 標準・可視ウィンドウを探索
	local wins = app:allWindows() or {}
	for _, w in ipairs(wins) do
		if (not opts.onlyStandard or w:isStandard()) and (not opts.onlyVisible or w:isVisible()) then
			return w
		end
	end

	-- 3) 最後の手段
	return app:mainWindow() or app:focusedWindow()
end

local function pickSecondaryScreen(primary, opts)
	-- opts.secondarySelector があればそれを優先
	if opts and opts.secondarySelector then
		local s = opts.secondarySelector(primary)
		if s then
			return s
		end
	end

	for _, s in ipairs(hs.screen.allScreens()) do
		if s:id() ~= primary:id() then
			return s
		end
	end
	return nil
end

local function moveWindowToActiveSpaceOnScreen(win, targetScreen, onDone)
	local targetSpace = hs.spaces.activeSpaceOnScreen(targetScreen)
	if targetSpace then
		hs.spaces.moveWindowToSpace(win, targetSpace)
	end

	local function finish(ok)
		if onDone then
			onDone(ok)
		end
	end

	if win:screen():id() == targetScreen:id() then
		finish(true)
		return
	end

	win:moveToScreen(targetScreen)
	hs.timer.doAfter(0.01, function()
		finish(false)
	end)
end

local function toggleBetweenPrimaryAndSecondaryActive(appName, opts)
	opts = opts or {}
	local win = getWindow(appName, { onlyStandard = true, onlyVisible = true, launchIfMissing = false })
	if not win then
		hs.alert.show(appName .. " window not found")
		return
	end

	-- メインディスプレイ上にあってバックグラウンドなら「前面化」だけする
	do
		local primary = hs.screen.primaryScreen()
		local currentScreen = win:screen()
		local app = win:application()
		if currentScreen and primary and currentScreen:id() == primary:id() and app and not app:isFrontmost() then
			-- アプリをアクティブ化し、該当ウィンドウを前面へ
			app:activate(true)
			win:focus()
			win:maximize()
			return
		end
	end

	local primary = hs.screen.primaryScreen()
	local secondary = pickSecondaryScreen(primary, opts)
	if not secondary then
		hs.alert.show("No secondary screen found")
		return
	end

	local fromScreen = win:screen()
	local target = (fromScreen:id() == primary:id()) and secondary or primary

	moveWindowToActiveSpaceOnScreen(win, target, function(_ok)
		win:focus()
	end)
end

-- open "hammerspoon://toggle?app=name" でアプリケーションを呼べる
hs.urlevent.bind("toggle", function(_, params)
	if not params or not params.app then
		hs.alert.show("toggle: missing ?app=")
		return
	end

	toggleBetweenPrimaryAndSecondaryActive(params.app)
end)
