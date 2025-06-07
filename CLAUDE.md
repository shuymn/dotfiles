# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

This is a dotfiles repository for a macOS development environment. It manages configurations for shell, terminal, development tools, and system customization utilities through symlinks.

## Key Commands

### Installation & Setup
```bash
# Install dotfiles (creates symlinks)
make link

# Show all dotfiles that will be linked
make list

# Remove all symlinks and repository
make clean

# Install Homebrew packages
brew bundle --file=.Brewfile

# Install Cargo tools
awk '/^[a-z]/ {print $1}' ./etc/cargo/cargo-installed.txt | xargs cargo install --locked
```

### Development Commands
```bash
# Start bash language server (for VSCode)
make start-bash-lsp
```

## Repository Structure

The repository follows XDG Base Directory specification with configurations organized in `.config/`:

- **`.config/zsh/`**: Modular Zsh configuration with numbered config files in `config/` and custom plugins in `plugins/`
- **`.config/nvim/`**: Neovim configuration using NvChad framework with Lua-based modular structure
- **`.config/git/`**: Git configuration including aliases and settings
- **`.config/kitty/`**: Kitty terminal emulator configuration
- **`etc/`**: Non-configuration resources (package lists, IME settings)

## Architecture Notes

1. **Symlink Management**: The Makefile creates symlinks from the repository to the home directory, excluding files like `.git`, `.DS_Store`, `.Brewfile`, etc.

2. **Modular Configuration**: Zsh configuration is split into numbered files that load in order, allowing easy management of different aspects (aliases, environment variables, plugins).

3. **Tool Integration**: The setup includes comprehensive development tools:
   - Shell: Zsh with starship prompt
   - Editor: Neovim with NvChad
   - Terminal: Kitty, tmux
   - Version managers: anyenv, asdf
   - macOS tools: Karabiner, Hammerspoon, Raycast

4. **Package Management**: Uses Homebrew (`.Brewfile`) for macOS packages and maintains a list of Cargo tools in `etc/cargo/`.