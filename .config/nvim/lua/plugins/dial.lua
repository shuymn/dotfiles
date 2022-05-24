local augend = require("dial.augend")
require("dial.config").augends:register_group({
	-- default augends used when no group name is specified
	default = {
		augend.integer.alias.decimal, -- decimal natural number
		augend.integer.alias.hex, -- hex natural number
		augend.integer.alias.octal, -- octal natural number
		augend.integer.alias.binary, -- binary natural number
		augend.date.alias["%Y/%m/%d"], -- date in the specific format (0 padding)
		augend.date.alias["%Y-%m-%d"],
		augend.date.alias["%m/%d"],
		augend.date.alias["%H:%M"],
		augend.constant.alias.ja_weekday,
		augend.constant.alias.ja_weekday_full,
		augend.constant.alias.bool, -- boolean value (true <-> false)
	},
})
