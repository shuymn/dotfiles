require("substitute").setup()

vim.api.nvim_set_keymap("n", "U", "<cmd>lua require('substitute').operator()<cr>", { noremap = true })
vim.api.nvim_set_keymap("n", "Uu", "<cmd>lua require('substitute').line()<cr>", { noremap = true })
vim.api.nvim_set_keymap("n", "UU", "<cmd>lua require('substitute').eol()<cr>", { noremap = true })
vim.api.nvim_set_keymap("x", "U", "<cmd>lua require('substitute').visual()<cr>", { noremap = true })
