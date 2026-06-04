#!/bin/sh
set -eu

script_dir=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
repo=$(CDPATH='' cd -- "$script_dir/.." && pwd)
fail=0

report() {
  printf '%s\n' "$1" >&2
  fail=1
}

if [ "$(cat "$repo/.chezmoiroot")" != "home" ]; then
  report ".chezmoiroot must stay set to 'home' so repo metadata is outside chezmoi source state."
fi

for path in \
  "home/dot_config/age" \
  "home/private_dot_config/age" \
  "home/dot_config/git/config.local" \
  "home/private_dot_config/git/config.local" \
  "home/dot_config/git/allowed_signers" \
  "home/private_dot_config/git/allowed_signers" \
  "home/dot_config/nix/nix.conf" \
  "home/private_dot_config/nix/nix.conf"
do
  if [ -e "$repo/$path" ]; then
    report "$path must stay local-only and outside chezmoi source state."
  fi
done

if [ -e "$repo/home/dot_config/go/env" ]; then
  report "home/dot_config/go/env is not the macOS GOENV target; manage home/Library/Application Support/go/env instead."
fi

if git -C "$repo" ls-files --error-unmatch nix/local.nix >/dev/null 2>&1; then
  report "nix/local.nix is generated from chezmoi data and must not be tracked."
fi

tracked_root_config=$(git -C "$repo" ls-files -- ".config")
if [ -n "$tracked_root_config" ]; then
  printf '%s\n' "$tracked_root_config" >&2
  report "root .config entries must not be tracked; put managed targets under home/**."
fi

symlink_refs=$(find "$repo/home" -type f -name 'symlink_*' -print0 \
  | xargs -0 grep -nE '(\.dotfiles|\.chezmoi\.workingTree|/Users/|/home/)' 2>/dev/null || true)
if [ -n "$symlink_refs" ]; then
  printf '%s\n' "$symlink_refs" >&2
  report "chezmoi-managed symlinks must not point back to repo-root or machine-specific absolute paths."
fi

exit "$fail"
