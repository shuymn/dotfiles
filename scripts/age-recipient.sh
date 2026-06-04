#!/bin/sh
set -eu

if [ "$#" -ne 1 ]; then
  echo "usage: $0 <age-identity>" >&2
  exit 2
fi

identity=$1

if command -v age-keygen >/dev/null 2>&1; then
  exec age-keygen -y "$identity"
fi

for candidate in \
  "$HOME/.nix-profile/bin/age-keygen" \
  "/etc/profiles/per-user/${USER:-}/bin/age-keygen" \
  "/run/current-system/sw/bin/age-keygen" \
  "/nix/var/nix/profiles/default/bin/age-keygen"; do
  if [ -x "$candidate" ]; then
    exec "$candidate" -y "$identity"
  fi
done

nix_bin=""
if command -v nix >/dev/null 2>&1; then
  nix_bin=$(command -v nix)
else
  for candidate in \
    "$HOME/.nix-profile/bin/nix" \
    "/run/current-system/sw/bin/nix" \
    "/nix/var/nix/profiles/default/bin/nix"; do
    if [ -x "$candidate" ]; then
      nix_bin=$candidate
      break
    fi
  done
fi

if [ -n "$nix_bin" ]; then
  exec "$nix_bin" --extra-experimental-features nix-command --extra-experimental-features flakes shell nixpkgs#age -c age-keygen -y "$identity"
fi

echo "age-keygen not found; install Nix or age before generating chezmoi config" >&2
exit 1
