-- Before Rex's ctrl+b prefix, switch from a Japanese input method to the U.S. layout
-- so the key after the prefix reaches Rex as a letter. Karabiner can't do this: the
-- keyboards in use are ignored devices there. The key itself always passes through.

local REX = "com.superlogical.rex"
local LAYOUT = "com.apple.keylayout.US"
local B = hs.keycodes.map.b

local tap = hs.eventtap.new({ hs.eventtap.event.types.keyDown }, function(event)
	if event:getKeyCode() ~= B then
		return false
	end
	local flags = event:getFlags()
	if not flags:containExactly({ "ctrl" }) then
		return false
	end
	local app = hs.application.frontmostApplication()
	if app and app:bundleID() == REX and hs.keycodes.currentMethod() ~= nil then
		hs.keycodes.currentSourceID(LAYOUT)
	end
	return false
end)
tap:start()

return tap
