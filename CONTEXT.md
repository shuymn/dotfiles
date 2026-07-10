# Dotfiles Automation Context

This context names repository-specific concepts used to keep generated dotfile state safe and reproducible.

## Mise lock automation

**Mise lock policy**:
The repository rules defining which mise configuration changes and derived lock projections are accepted.

**Lock candidate**:
An untrusted proposed `mise.lock` projection produced for a version-only configuration update.
