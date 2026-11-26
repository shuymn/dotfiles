-- Lays out the windows of the apps in APPS that are assigned to a FlashSpace workspace
-- (read from ~/.config/flashspace/profiles.json); any other app is never watched or
-- queried. Within each showing workspace, multiple windows of a single app default to
-- "accordion" (a diagonal cascade where every window keeps its own uncovered corners),
-- while mixed apps default to "tiles" (an even split along the display's longer side).

-- `hs` CLI access (Hammerspoon.app/Contents/Frameworks/hs/hs), e.g. to reload.
require("hs.ipc")

hs.window.animationDuration = 0

local GAP = 10
local ACCORDION_PADDING = 30
local SETTLE_SECONDS = 0.1
local RETRY_SECONDS = 0.5
local FLASHSPACE = "/Applications/FlashSpace.app/Contents/Resources/flashspace"
local FLASHSPACE_DIR = os.getenv("HOME") .. "/.config/flashspace"
local FLASHSPACE_PROFILES = FLASHSPACE_DIR .. "/profiles.json"
local FLASHSPACE_BUNDLE = "pl.wojciechkulik.FlashSpace"
local FLASHSPACE_PLIST = os.getenv("HOME") .. "/Library/Preferences/" .. FLASHSPACE_BUNDLE .. ".plist"
-- host.toml [displays] (rendered by chezmoi); see followMainDisplay.
local DISPLAYS_FILE = os.getenv("HOME") .. "/.config/hammerspoon/displays.json"
-- FlashSpace's CLI socket is not ready the moment the app launches.
local FLASHSPACE_READY_SECONDS = 3

-- Opt-in: bundle IDs to lay out, in layout order within a workspace. FlashSpace
-- auto-assigns every app that gets focus, so being assigned alone does not opt an app in.
local APPS = {
	"com.google.Chrome",
	"com.superlogical.rex",
	"com.spotify.client",
	"com.hnc.Discord",
	"com.openai.codex",
	"com.tinyspeck.slackmacgap",
}

-- alt-shift-space toggles the frontmost app in or out of layout; the choice persists in
-- hs.settings as { [bundleID] = true | false } and overrides APPS.
local TOGGLED_KEY = "toggledApps"

local function isOptedIn(bundleID)
	local toggled = hs.settings.get(TOGGLED_KEY) or {}
	if toggled[bundleID] ~= nil then
		return toggled[bundleID]
	end
	return hs.fnutils.contains(APPS, bundleID)
end

-- Optional manual layout override per workspace ("tiles" or "accordion"); cleared on reload.
-- When unset, a workspace with 1 distinct app uses "accordion", and 2+ apps use "tiles".
local layoutOverrides = {}

local function round(n)
	return math.floor(n + 0.5)
end

local function frameMatches(a, b)
	return math.abs(a.x - b.x) <= 2 and math.abs(a.y - b.y) <= 2 and math.abs(a.w - b.w) <= 2 and math.abs(a.h - b.h) <= 2
end

local function lines(text)
	return text:gmatch("[^\n]+")
end

local function runningApps(bundleID)
	return hs.application.applicationsForBundleID(bundleID)
end

local scheduleTile -- defined once the layout exists
local syncWatchers -- defined once watchers exist

-- FlashSpace state ------------------------------------------------------------------
-- Assignments come directly from profiles.json (single source of truth). Active
-- workspaces per display are queried asynchronously via the CLI.

local function runAsync(command, args, done)
	local task = hs.task.new(command, function(code, output)
		done(code, output or "")
	end, args)
	if not (task and task:start()) then
		done(-1, "")
	end
end

local orderedApps = {} -- APPS entries currently assigned, in APPS order
local workspaceOf = {} -- bundle ID -> workspace name, for those entries only
local displayOf = {} -- workspace name -> display name

local function selectProfile(profiles)
	local prefs = hs.plist.read(FLASHSPACE_PLIST)
	local selectedID = prefs and prefs.selectedProfileId
	if selectedID then
		for _, profile in ipairs(profiles) do
			if type(profile) == "table" and profile.id == selectedID then
				return profile
			end
		end
	end
	return profiles[1]
end

-- With [displays].main empty and secondary set, the main display is whichever one is not
-- the secondary: when exactly two displays are connected and one is the secondary, every
-- workspace not saved on the secondary is moved to the other one. With one display
-- FlashSpace already shows every workspace there; three or more are left alone. The
-- update rewrites profiles.json, which reloads assignments and finds nothing left to move.
-- displays.json is read on every call so a later chezmoi apply takes effect without a reload.
local movingTo = {} -- workspace -> display of an update still running
local function followMainDisplay(displays)
	local config = hs.fs.attributes(DISPLAYS_FILE) and hs.json.read(DISPLAYS_FILE)
	if type(config) ~= "table" then
		return
	end
	local secondary = config.secondary
	if (config.main or "") ~= "" or type(secondary) ~= "string" or secondary == "" then
		return
	end
	local screens = hs.screen.allScreens()
	if #screens ~= 2 then
		return
	end
	local main, hasSecondary
	for _, screen in ipairs(screens) do
		if screen:name() == secondary then
			hasSecondary = true
		else
			main = screen:name()
		end
	end
	if not hasSecondary or not main or main == "" then
		return
	end
	for workspace, saved in pairs(displays) do
		if saved ~= secondary and saved ~= main and movingTo[workspace] ~= main then
			movingTo[workspace] = main
			runAsync(FLASHSPACE, { "update-workspace", "--workspace", workspace, "--display", main }, function(code, output)
				if movingTo[workspace] == main then
					movingTo[workspace] = nil
				end
				if code ~= 0 then
					print("update-workspace " .. workspace .. " failed: " .. output)
				end
			end)
		end
	end
end

local loadAssignments
local retryAssignments = hs.timer.delayed.new(RETRY_SECONDS, function()
	loadAssignments()
end)

loadAssignments = function()
	local data = hs.json.read(FLASHSPACE_PROFILES)
	local profiles = type(data) == "table" and data.profiles
	if type(profiles) ~= "table" or #profiles == 0 then
		retryAssignments:start()
		return
	end
	local profile = selectProfile(profiles)
	if type(profile) ~= "table" or type(profile.workspaces) ~= "table" then
		retryAssignments:start()
		return
	end
	retryAssignments:stop()

	local assigned, displays = {}, {}
	for _, ws in ipairs(profile.workspaces) do
		if type(ws) == "table" and type(ws.name) == "string" then
			displays[ws.name] = type(ws.display) == "string" and ws.display or ""
			if type(ws.apps) == "table" then
				for _, app in ipairs(ws.apps) do
					local bundleID = type(app) == "table" and app.bundleIdentifier
					if type(bundleID) == "string" then
						assigned[bundleID] = ws.name
					end
				end
			end
		end
	end
	-- Other apps' workspaces are never kept, so nothing below can reach them.
	-- APPS keep their order; apps opted in by hand follow, sorted for a stable order.
	local candidates = hs.fnutils.copy(APPS)
	local extra = {}
	for bundleID, on in pairs(hs.settings.get(TOGGLED_KEY) or {}) do
		if on == true and not hs.fnutils.contains(APPS, bundleID) then
			table.insert(extra, bundleID)
		end
	end
	table.sort(extra)
	hs.fnutils.concat(candidates, extra)

	local apps, workspaces = {}, {}
	for _, bundleID in ipairs(candidates) do
		if assigned[bundleID] and isOptedIn(bundleID) then
			workspaces[bundleID] = assigned[bundleID]
			table.insert(apps, bundleID)
		end
	end

	orderedApps, workspaceOf, displayOf = apps, workspaces, displays
	followMainDisplay(displays)
	syncWatchers()
	scheduleTile()
end

local function connectedScreen(name)
	for _, screen in ipairs(hs.screen.allScreens()) do
		if screen:name() == name then
			return screen
		end
	end
end

-- A display FlashSpace names but that is not connected means the focused one, as in
-- FlashSpace itself.
local function screenNamed(name)
	return connectedScreen(name) or hs.screen.mainScreen()
end

-- Frames ------------------------------------------------------------------------------

-- Cell `index` of `count` along the display's longer side, GAP around and between.
local function cellFrame(screen, index, count)
	local area = screen:frame()
	local landscape = area.w >= area.h
	local origin = landscape and area.x or area.y
	local length = (landscape and area.w or area.h) - 2 * GAP
	local cell = (length - GAP * (count - 1)) / count
	local first = round(origin + GAP + (cell + GAP) * (index - 1))
	local last = round(origin + GAP + (cell + GAP) * (index - 1) + cell)
	if landscape then
		return hs.geometry.rect(first, round(area.y + GAP), last - first, round(area.h - 2 * GAP))
	end
	return hs.geometry.rect(round(area.x + GAP), first, round(area.w - 2 * GAP), last - first)
end

-- Accordion window `index` of `count`: all the same size, each offset one padding step
-- right and down. Every window's top-right and bottom-left padding-sized corners overlap
-- no other window, so each stays clickable whatever the Z-order and nothing is restacked.
local function accordionFrame(screen, index, count)
	local area = screen:frame()
	local shift = ACCORDION_PADDING * (index - 1)
	local shrink = ACCORDION_PADDING * (count - 1)
	return hs.geometry.rect(
		round(area.x + GAP + shift),
		round(area.y + GAP + shift),
		round(area.w - 2 * GAP - shrink),
		round(area.h - 2 * GAP - shrink)
	)
end

-- Layout ------------------------------------------------------------------------------

local applied = {} -- window id -> { target, result } of the last setFrame
local windowWatchers = {} -- window id -> { watcher, pid }

-- Apps may clamp a frame (minimum sizes); do not resend a frame they already declined.
-- An explicit re-tile clears `applied` to retry.
local function place(win, frame)
	local current = win:frame()
	if frameMatches(current, frame) then
		return
	end
	local id = win:id()
	local last = id and id ~= 0 and applied[id]
	if last and frameMatches(last.target, frame) and frameMatches(last.result, current) then
		return
	end
	win:setFrame(frame)
	if id and id ~= 0 then
		applied[id] = { target = frame, result = win:frame() }
	end
end

-- Window-level events (close, minimize, unminimize) are watched per window of a
-- managed app: app watchers report creation with elements that are not always windows.
local function watchWindow(win, pid)
	local id = win:id()
	if not id or id == 0 or windowWatchers[id] then
		return
	end
	local watcher = win:newWatcher(function(_, event)
		if event == hs.uielement.watcher.elementDestroyed then
			windowWatchers[id].watcher:stop()
			windowWatchers[id] = nil
			applied[id] = nil
		end
		scheduleTile()
	end)
	watcher:start({
		hs.uielement.watcher.elementDestroyed,
		hs.uielement.watcher.windowMinimized,
		hs.uielement.watcher.windowUnminimized,
	})
	windowWatchers[id] = { watcher = watcher, pid = pid }
end

local function isAccordionLayout(workspace, windows, bundleOf)
	local override = layoutOverrides[workspace]
	if override then
		return override == "accordion"
	end
	local seen, distinct = {}, 0
	for _, win in ipairs(windows) do
		local bundleID = bundleOf[win:id()]
		if bundleID and not seen[bundleID] then
			seen[bundleID] = true
			distinct = distinct + 1
			if distinct > 1 then
				return false
			end
		end
	end
	return true
end

-- `showing`: workspace -> display name for the workspaces to lay out.
local function layout(showing)
	local groups, bundleOf = {}, {}
	for _, bundleID in ipairs(orderedApps) do
		local workspace = workspaceOf[bundleID]
		for _, app in ipairs(workspace and showing[workspace] and runningApps(bundleID) or {}) do
			if not app:isHidden() then
				groups[workspace] = groups[workspace] or {}
				local windows = app:allWindows()
				table.sort(windows, function(a, b)
					return a:id() < b:id()
				end)
				for _, win in ipairs(windows) do
					local id = win:id()
					-- Windows without a usable id (0) cannot be told apart; leave them alone.
					if id and id ~= 0 and win:isStandard() then
						bundleOf[id] = bundleID
						watchWindow(win, app:pid())
						if not win:isMinimized() and not win:isFullScreen() then
							table.insert(groups[workspace], win)
						end
					end
				end
			end
		end
	end

	for workspace, windows in pairs(groups) do
		local count = #windows
		local screen = screenNamed(showing[workspace])
		local accordion = isAccordionLayout(workspace, windows, bundleOf)
		for index, win in ipairs(windows) do
			place(win, accordion and accordionFrame(screen, index, count) or cellFrame(screen, index, count))
		end
	end
end

-- A workspace is shown where FlashSpace reports it active; on a display where nothing
-- has been activated yet, every workspace assigned there counts (nothing is hidden).
local refreshing, rerun = false, false
local function tileAll()
	if refreshing then
		rerun = true
		return
	end
	refreshing = true
	runAsync(FLASHSPACE, { "list-workspaces", "--active", "--with-display" }, function(code, output)
		refreshing = false
		-- Something changed while asking; this answer may already be stale.
		if rerun then
			rerun = false
			tileAll()
			return
		end
		if code ~= 0 then
			return
		end
		-- Active workspaces whose display is unknown or gone (e.g. just unplugged) are
		-- left alone rather than piled onto the focused display.
		local showing, claimed, skipped = {}, {}, {}
		for line in lines(output) do
			local workspace, display = line:match("^([^,]+),([^,]*)")
			if workspace and connectedScreen(display) then
				showing[workspace] = display
				claimed[display] = true
			elseif workspace then
				skipped[workspace] = true
			end
		end
		-- With one display FlashSpace puts every workspace there, whatever display is saved.
		local screens = hs.screen.allScreens()
		local only = #screens == 1 and screens[1]:name()
		for workspace, saved in pairs(displayOf) do
			local display = only or saved
			if not claimed[display] and not showing[workspace] and not skipped[workspace] and connectedScreen(display) then
				showing[workspace] = display
			end
		end
		local laidOut, err = pcall(layout, showing)
		if not laidOut then
			print("layout failed: " .. tostring(err))
		end
	end)
end

-- An app shown again reports its windows one event at a time; laying out each would
-- show a partial set first and flicker, so lay out once the events settle.
local pendingTile = hs.timer.delayed.new(SETTLE_SECONDS, tileAll)
scheduleTile = function()
	if refreshing then
		rerun = true
	end
	pendingTile:start()
end

-- Watchers (FlashSpace-assigned apps only) --------------------------------------------

local appWatchers = {} -- pid -> { watcher, bundleID }

local function watchApp(app)
	local bundleID, pid = app:bundleID(), app:pid()
	if appWatchers[pid] then
		return
	end
	local watcher = app:newWatcher(function()
		scheduleTile()
	end)
	-- Focus changes also catch windows appearing without a creation event (e.g. on a
	-- macOS Space switch); a layout pass with nothing to move changes nothing.
	watcher:start({ hs.uielement.watcher.windowCreated, hs.uielement.watcher.focusedWindowChanged })
	appWatchers[pid] = { watcher = watcher, bundleID = bundleID }
end

local function forgetApp(pid)
	if appWatchers[pid] then
		appWatchers[pid].watcher:stop()
		appWatchers[pid] = nil
	end
	for id, entry in pairs(windowWatchers) do
		if entry.pid == pid then
			entry.watcher:stop()
			windowWatchers[id] = nil
			applied[id] = nil
		end
	end
end

syncWatchers = function()
	for pid, entry in pairs(appWatchers) do
		if not workspaceOf[entry.bundleID] then
			forgetApp(pid)
		end
	end
	for _, bundleID in ipairs(orderedApps) do
		for _, app in ipairs(runningApps(bundleID)) do
			watchApp(app)
		end
	end
end

local flashSpaceReady = hs.timer.delayed.new(FLASHSPACE_READY_SECONDS, loadAssignments)

AppWatcher = hs.application.watcher
	.new(function(_, event, app)
		if not app then
			return
		end
		-- A terminated app may no longer report its bundle ID; clean up by pid.
		if event == hs.application.watcher.terminated then
			if appWatchers[app:pid()] then
				forgetApp(app:pid())
				scheduleTile()
			end
			return
		end
		-- FlashSpace started after Hammerspoon (e.g. at login): the CLI calls made so far
		-- failed, so re-read once it can answer.
		if event == hs.application.watcher.launched and app:bundleID() == FLASHSPACE_BUNDLE then
			flashSpaceReady:start()
			return
		end
		if not workspaceOf[app:bundleID()] then
			return
		end
		if event == hs.application.watcher.launched then
			watchApp(app)
		end
		scheduleTile()
	end)
	:start()

-- Watch the directory so atomic renames of profiles.json are never missed.
ProfilesWatcher = hs.pathwatcher
	.new(FLASHSPACE_DIR, function(files)
		for _, path in ipairs(files) do
			if path == FLASHSPACE_PROFILES then
				loadAssignments()
				return
			end
		end
	end)
	:start()

-- Display changes can change the displays FlashSpace resolves; re-read, then lay out.
ScreenWatcher = hs.screen.watcher
	.new(function()
		scheduleTile()
		loadAssignments()
	end)
	:start()

local function setLayout(name)
	local frontmost = hs.application.frontmostApplication()
	local workspace = frontmost and workspaceOf[frontmost:bundleID()]
	if workspace then
		layoutOverrides[workspace] = name
		tileAll()
	end
end

-- Explicit re-tile: re-read assignments and retry frames apps declined before.
hs.hotkey.bind({ "alt", "shift" }, "r", function()
	applied = {}
	loadAssignments()
end)
hs.hotkey.bind({ "alt", "shift" }, "space", function()
	local app = hs.application.frontmostApplication()
	local bundleID = app and app:bundleID()
	if not bundleID then
		return
	end
	local on = not isOptedIn(bundleID)
	local toggled = hs.settings.get(TOGGLED_KEY) or {}
	-- Store only departures from the APPS default.
	if on == hs.fnutils.contains(APPS, bundleID) then
		toggled[bundleID] = nil
	else
		toggled[bundleID] = on
	end
	hs.settings.set(TOGGLED_KEY, toggled)
	hs.alert.show((on and "Layout: " or "Floating: ") .. app:name())
	loadAssignments()
end)
hs.hotkey.bind({ "alt" }, "/", function()
	setLayout("tiles")
end)
hs.hotkey.bind({ "alt" }, ",", function()
	setLayout("accordion")
end)

loadAssignments()
