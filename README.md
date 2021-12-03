# dotfiles

I am the bone of my dotfiles.

# Installation

```bash
curl -fsSL http://dot.shuymn.me | bash
```

## Install commands via Cargo

```bash
awk '/^[a-z]/ {print $1}' cargo-installed.txt | xargs cargo install --locked
```

# License

MIT
