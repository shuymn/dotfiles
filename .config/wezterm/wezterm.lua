local wezterm = require("wezterm")
local act = wezterm.action

local config = {}

if wezterm.config_builder then
	config = wezterm.config_builder()
end

config.use_ime = true
config.font = wezterm.font("UDEV Gothic 35NF")
config.font_size = 12.0
config.line_height = 1.2
config.color_scheme = "OneHalfDark"
config.window_background_opacity = 0.9
config.macos_window_background_blur = 5
config.enable_tab_bar = false
config.hide_tab_bar_if_only_one_tab = true
config.adjust_window_size_when_changing_font_size = false
config.disable_default_key_bindings = true
config.selection_word_boundary = " \t\n{}[]()\"'`,;:"
config.audible_bell = "Disabled"
config.window_decorations = "RESIZE"
config.window_close_confirmation = "NeverPrompt"
config.window_padding = {
	left = 0,
	right = 0,
	top = 0,
	bottom = 0,
}
config.keys = {
	{ key = "q", mods = "SUPER", action = act.QuitApplication },
	{ key = "w", mods = "SUPER", action = act({ CloseCurrentTab = { confirm = false } }) },
	{ key = "v", mods = "SUPER", action = act({ PasteFrom = "Clipboard" }) },
	{ key = "=", mods = "SUPER", action = act.IncreaseFontSize },
	{ key = "-", mods = "SUPER", action = act.DecreaseFontSize },
	{ key = "0", mods = "SUPER", action = act.ResetFontSize },
	{ key = "r", mods = "SUPER", action = act.ReloadConfiguration },
}
config.mouse_bindings = {
	{
		event = { Up = { streak = 1, button = "Left" } },
		mods = "SUPER",
		action = act.OpenLinkAtMouseCursor,
	},
}

return config
