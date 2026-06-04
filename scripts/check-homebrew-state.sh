#!/bin/sh
set -eu

if [ "$#" -ne 1 ]; then
  echo "usage: $0 <brewfile>" >&2
  exit 2
fi

brewfile=$1
brew_cmd=${BREW:-brew}
tmpdir=${TMPDIR:-/tmp}
expected_formulae=$(mktemp "$tmpdir/dotfiles-brew-formulae.XXXXXX")
actual_formulae=$(mktemp "$tmpdir/dotfiles-brew-leaves.XXXXXX")
expected_casks=$(mktemp "$tmpdir/dotfiles-brew-casks.XXXXXX")
actual_casks=$(mktemp "$tmpdir/dotfiles-brew-installed-casks.XXXXXX")
trap 'rm -f "$expected_formulae" "$actual_formulae" "$expected_casks" "$actual_casks"' EXIT INT TERM

"$brew_cmd" bundle list --file="$brewfile" --formula | sort > "$expected_formulae"
"$brew_cmd" leaves | sort > "$actual_formulae"
"$brew_cmd" bundle list --file="$brewfile" --cask | sort > "$expected_casks"
"$brew_cmd" list --cask | sort > "$actual_casks"

fail=0
if ! diff -u "$expected_formulae" "$actual_formulae" >&2; then
  echo "Homebrew formula leaves must match nix/darwin.nix brews." >&2
  fail=1
fi

if ! diff -u "$expected_casks" "$actual_casks" >&2; then
  echo "Homebrew casks must match nix/darwin.nix casks." >&2
  fail=1
fi

exit "$fail"
