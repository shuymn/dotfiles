-- Lays out the windows of the apps in APPS that are assigned to a FlashSpace workspace
-- (read from ~/.config/flashspace/profiles.json); any other app is never watched or
-- queried. Within each showing workspace, windows are laid out along the display's longer
-- side: multiple windows of a single app default to "accordion" (offset strips with the
-- focused window on top), while mixed apps default to "tiles" (even split).

-- `hs` CLI access (Hammerspoon.app/Contents/Frameworks/hs/hs), e.g. to reload.
require("hs.ipc")

hs.window.animationDuration = 0

local GAP = 10
local ACCORDION_PADDING = 30
local SETTLE_SECONDS = 0.1
local STACK_STEP_SECONDS = 0.02
local RETRY_SECONDS = 0.5
local FLASHSPACE = "/Applications/FlashSpace.app/Contents/Resources/flashspace"
local FLASHSPACE_DIR = os.getenv("HOME") .. "/.config/flashspace"
local FLASHSPACE_PROFILES = FLASHSPACE_DIR .. "/profiles.json"
local FLASHSPACE_PLIST = os.getenv("HOME") .. "/Library/Preferences/pl.wojciechkulik.FlashSpace.plist"

-- Opt-in: bundle IDs to lay out, in layout order within a workspace. FlashSpace
-- auto-assigns every app that gets focus, so being assigned alone does not opt an app in.
local APPS = {
	"com.google.Chrome",
	"com.mitchellh.ghostty",
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

-- Accordion window `index` of `count`: all the same size, each offset one padding
-- step, so every window's edge stays visible as a strip once stacked (raiseAccordion).
local function accordionFrame(screen, index, count)
	local area = screen:frame()
	local x, y = area.x + GAP, area.y + GAP
	local w, h = area.w - 2 * GAP, area.h - 2 * GAP
	local shift = ACCORDION_PADDING * (index - 1)
	local shrink = ACCORDION_PADDING * (count - 1)
	if w >= h then
		return hs.geometry.rect(round(x + shift), round(y), round(w - shrink), round(h))
	end
	return hs.geometry.rect(round(x), round(y + shift), round(w), round(h - shrink))
end

-- Layout ------------------------------------------------------------------------------

local lastFocused = {} -- workspace -> window id
local restackTimers = {} -- workspace -> active cross-app stacking timer
local restacking = {} -- workspace -> true ("stale" once a layout was skipped) while focusing to fix cross-app Z-order
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

local function cancelRestack(workspace)
	if restackTimers[workspace] then
		restackTimers[workspace]:stop()
		restackTimers[workspace] = nil
	end
	restacking[workspace] = nil
end

local function windowZOrder()
	-- WindowServer's front-to-back list; unlike hs.window.orderedWindows() it does not
	-- query every app's windows through Accessibility.
	local rank = {}
	for index, info in ipairs(hs.window.list()) do
		rank[info.kCGWindowNumber] = rank[info.kCGWindowNumber] or index
	end
	return rank
end

local function allRanked(windows, rank)
	for _, win in ipairs(windows) do
		if not rank[win:id()] then
			return false
		end
	end
	return true
end

-- True when every strip on both sides of `focus` is uncovered: windows farther from
-- `focus` sit lower in Z-order (larger rank).
local function isAccordionStacked(windows, focus, rank)
	if not allRanked(windows, rank) then
		return false
	end
	for index = 1, focus - 1 do
		if rank[windows[index]:id()] <= rank[windows[index + 1]:id()] then
			return false
		end
	end
	for index = focus, #windows - 1 do
		if rank[windows[index]:id()] >= rank[windows[index + 1]:id()] then
			return false
		end
	end
	return true
end

-- Stack the windows so the farther a window is from the focused one, the lower it sits;
-- then every strip stays uncovered. Skipped when the current Z-order already satisfies this.
local function raiseAccordion(workspace, windows, focus, refocus, pidOf)
	if restacking[workspace] then
		-- Lay out again once the restack settles.
		restacking[workspace] = "stale"
		return
	end
	local rank = windowZOrder()
	if isAccordionStacked(windows, focus, rank) then
		return
	end

	local multiApp = false
	local firstPid = pidOf[windows[1]:id()]
	for index = 2, #windows do
		if pidOf[windows[index]:id()] ~= firstPid then
			multiApp = true
			break
		end
	end

	local order = {}
	for index = 1, #windows do
		table.insert(order, index)
	end
	table.sort(order, function(a, b)
		local da, db = math.abs(a - focus), math.abs(b - focus)
		if da ~= db then
			return da > db
		end
		return a < b
	end)

	-- AXRaise only reorders windows within one app, so cross-app accordions go through
	-- win:focus() — only when this workspace is frontmost, to avoid stealing
	-- focus from another display or workspace.
	if multiApp then
		if not refocus then
			return
		end
		-- Without every window's place in the Z-order the steps cannot be chosen; wait for
		-- a later layout pass.
		if not allRanked(windows, rank) then
			return
		end
		-- Any bottom prefix of `order` already descending in Z-order can stay untouched;
		-- focusing the remaining windows in order stacks them cleanly above it.
		local start = 2
		while start <= #order do
			local prevRank = rank[windows[order[start - 1]]:id()]
			local currRank = rank[windows[order[start]]:id()]
			if prevRank > currRank then
				start = start + 1
			else
				break
			end
		end
		local steps = {}
		for i = start, #order do
			table.insert(steps, windows[order[i]])
		end

		cancelRestack(workspace)
		restacking[workspace] = true
		local focusID = windows[focus]:id()
		local function finishRestack()
			lastFocused[workspace] = focusID
			restackTimers[workspace] = hs.timer.doAfter(SETTLE_SECONDS, function()
				local stale = restacking[workspace] == "stale"
				restackTimers[workspace] = nil
				restacking[workspace] = nil
				-- Focus events were ignored while restacking; keep a window the user
				-- focused meanwhile, and lay out again if anything changed.
				local current = hs.window.focusedWindow()
				local currentID = current and current:id()
				for _, win in ipairs(windows) do
					if win:id() == currentID and currentID ~= focusID then
						lastFocused[workspace] = currentID
						stale = true
					end
				end
				if stale then
					scheduleTile()
				end
			end)
		end
		-- The user may switch away, or a window may close, before a delayed step; never pull
		-- focus back or focus a window that left the screen. Returns the current ranks.
		local function canContinue()
			local app = hs.application.frontmostApplication()
			local now = windowZOrder()
			if app and workspaceOf[app:bundleID()] == workspace and allRanked(windows, now) then
				return now
			end
			local stale = restacking[workspace] == "stale"
			cancelRestack(workspace)
			if stale then
				scheduleTile()
			end
			return nil
		end
		-- Try synchronous focus first so intermediate windows do not stay on top long
		-- enough to flicker; fall back to stepped focus only if WindowServer drops a step.
		if not canContinue() then
			return
		end
		for _, win in ipairs(steps) do
			win:focus()
		end
		restackTimers[workspace] = hs.timer.doAfter(STACK_STEP_SECONDS, function()
			local now = canContinue()
			if not now then
				return
			end
			if isAccordionStacked(windows, focus, now) then
				finishRestack()
				return
			end
			local stepIndex = 1
			local function runStep()
				if not canContinue() then
					return
				end
				steps[stepIndex]:focus()
				stepIndex = stepIndex + 1
				if stepIndex <= #steps then
					restackTimers[workspace] = hs.timer.doAfter(STACK_STEP_SECONDS, runStep)
				else
					finishRestack()
				end
			end
			runStep()
		end)
		return
	end

	for _, index in ipairs(order) do
		windows[index]:raise()
	end
	-- Raising can move keyboard focus inside the frontmost app; give it back.
	if refocus then
		windows[focus]:focus()
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
	local frontmost = hs.application.frontmostApplication()
	local frontmostID = frontmost and frontmost:bundleID()

	local groups, pidOf, bundleOf = {}, {}, {}
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
						pidOf[id] = app:pid()
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

	for workspace in pairs(restackTimers) do
		if not groups[workspace] then
			cancelRestack(workspace)
		end
	end

	for workspace, windows in pairs(groups) do
		local count = #windows
		local screen = screenNamed(showing[workspace])
		local accordion = isAccordionLayout(workspace, windows, bundleOf)
		-- Focus events are the reliable record (an app's focused window can still name the
		-- previous one right after it opens a new window), but when the workspace's app is
		-- frontmost, only a recorded window of that app counts; otherwise use its focused
		-- window. Never refocus a window that is not in the group.
		local isFrontmost = workspaceOf[frontmostID] == workspace
		local inGroup = {}
		for _, win in ipairs(windows) do
			inGroup[win:id()] = true
		end
		local focusID = lastFocused[workspace]
		if not inGroup[focusID] or (isFrontmost and pidOf[focusID] ~= frontmost:pid()) then
			local current = isFrontmost and frontmost:focusedWindow()
			focusID = current and current:id()
		end
		local focus
		for index, win in ipairs(windows) do
			if win:id() == focusID then
				focus = index
			end
			place(win, accordion and accordionFrame(screen, index, count) or cellFrame(screen, index, count))
		end
		if accordion and count > 1 then
			raiseAccordion(workspace, windows, focus or 1, isFrontmost and focus ~= nil, pidOf)
		else
			cancelRestack(workspace)
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

local function recordFocus(bundleID, win)
	local workspace = workspaceOf[bundleID]
	if workspace and win and win.id then
		lastFocused[workspace] = win:id()
	end
end

local function watchApp(app)
	local bundleID, pid = app:bundleID(), app:pid()
	if appWatchers[pid] then
		return
	end
	local watcher = app:newWatcher(function(element, event)
		if event == hs.uielement.watcher.focusedWindowChanged then
			-- The restack's own focus changes; it records the outcome when it settles.
			if restacking[workspaceOf[bundleID]] then
				return
			end
			recordFocus(bundleID, element)
		end
		scheduleTile()
	end)
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
		local bundleID = app:bundleID()
		local workspace = workspaceOf[bundleID]
		if not workspace then
			return
		end
		if restacking[workspace] and (event == hs.application.watcher.activated or event == hs.application.watcher.deactivated) then
			return
		end
		if event == hs.application.watcher.launched then
			watchApp(app)
		elseif event == hs.application.watcher.activated then
			-- Switching between apps of one workspace does not change either app's own
			-- focused window, so record it here.
			recordFocus(bundleID, app:focusedWindow())
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
