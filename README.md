# dotfiles

I am the bone of my dotfiles.

# Installation

```bash
curl -fsSL https://raw.githubusercontent.com/shuymn/dotfiles/main/install.sh | bash
```

## Install commands via Cargo

```bash
awk '/^[a-z]/ {print $1}' ./etc/cargo/cargo-installed.txt | xargs cargo install --locked
```

# License

MIT
