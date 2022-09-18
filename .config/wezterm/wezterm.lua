local wezterm = require("wezterm")

return {
	use_ime = true,
	font = wezterm.font("UDEV Gothic 35NF"),
	font_size = 12.0,
	line_height = 1.2,
	color_scheme = "OneHalfDark",
	enable_tab_bar = false,
	hide_tab_bar_if_only_one_tab = true,
	adjust_window_size_when_changing_font_size = false,
	disable_default_key_bindings = true,
	selection_word_boundary = " \t\n{}[]()\"'`,;:",
	audible_bell = "Disabled",
	window_decorations = "RESIZE",
	window_close_confirmation = "NeverPrompt",
	window_padding = {
		left = 0,
		right = 0,
		top = 0,
		bottom = 0,
	},
	keys = {
		{ key = "q", mods = "SUPER", action = "QuitApplication" },
		{ key = "w", mods = "SUPER", action = wezterm.action({ CloseCurrentTab = { confirm = false } }) },
		{ key = "v", mods = "SUPER", action = wezterm.action({ PasteFrom = "Clipboard" }) },
		{ key = "=", mods = "SUPER", action = "IncreaseFontSize" },
		{ key = "-", mods = "SUPER", action = "DecreaseFontSize" },
		{ key = "r", mods = "SUPER", action = "ReloadConfiguration" },
	},
	mouse_bindings = {
		{
			event = { Up = { streak = 1, button = "Left" } },
			mods = "SUPER",
			action = "OpenLinkAtMouseCursor",
		},
	},
}
