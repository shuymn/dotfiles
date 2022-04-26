local wezterm = require("wezterm")

return {
	use_ime = true,
	font = wezterm.font_with_fallback({
		"UDEV Gothic 35NF",
	}),
	font_size = 12.0,
	color_scheme = "OneHalfDark",
	hide_tab_bar_if_only_one_tab = true,
	adjust_window_size_when_changing_font_size = false,
	disable_default_key_bindings = true,
	audible_bell = "Disabled",
	keys = {
		{ key = "v", mods = "SUPER", action = "Paste" },
	},
}
