# Local Forgejo review gate

This directory runs a private, single-user Forgejo instance as a review viewer and approval gate for GitHub repositories. GitHub remains the source of truth. Do not merge pull requests in Forgejo and do not configure push mirrors or Forgejo Actions.

The files in this directory are rendered from the dotfiles repository by chezmoi. This includes a read-only system Git configuration used inside the container. Runtime data and credentials remain outside the dotfiles source:

| Item | Location | Managed by chezmoi |
| --- | --- | --- |
| Compose and this runbook | `~/.local/share/forgejo-review` | yes |
| `fpr` executable | `~/.local/bin/fpr` | yes |
| SQLite and repositories | Docker volume `forgejo-review-data` | no |
| fpr config, API token, and dedicated SSH host keys | `~/.config/fpr` | no |
| Agent SSH private key | `~/.ssh/id_ed25519_fpr_agent` | no |

Forgejo listens only on `127.0.0.1:3000` (HTTP) and `127.0.0.1:2222` (SSH). Registration, Actions, mirrors, and public repositories are disabled.

## One-time setup

1. Apply the dotfiles source:

   ```sh
   cd ~/.dotfiles
   make apply
   exec zsh
   ```

2. Start Forgejo:

   ```sh
   cd ~/.local/share/forgejo-review
   make up
   make open
   ```

3. Complete the first-run installation in the browser and create the **human reviewer** account. Keep the SQLite settings supplied by the container. Use a username distinct from `fpr-agent`. Registration remains disabled after installation.

4. Create the non-interactive author account and local credentials:

   ```sh
   make bootstrap REVIEWER=<human-forgejo-login>
   fpr doctor
   ```

   The script creates `fpr-agent` with a discarded random password, a scoped API token, a dedicated SSH key, and an isolated `~/.config/fpr/known_hosts` file. It seeds Forgejo's Ed25519 host key directly from the local container; `fpr` verifies the live SSH endpoint against that key before reading or sending the API token. SSH ignores normal user/system configuration and `~/.ssh/known_hosts` for these connections. The Compose-managed system Git configuration enables `receive.shallowUpdate` only inside this private review instance so `fpr` can preserve exact commit SHAs from shallow GitHub clones. It does not change or deepen the source clone. The script verifies this setting and does not print or commit the token. Re-running it reuses valid local credentials.

The account split is intentional: `fpr-agent` owns repositories, pushes review refs, and opens local pull requests; the human account reviews them. Forgejo does not permit an author to approve their own pull request.

## Daily workflow

From a clean, committed feature branch in a GitHub clone:

```sh
fpr open                 # update the local PR and open it in Forgejo
fpr status               # show the reviewed SHA and gate state
fpr ship                 # push exactly the approved SHA and open a GitHub PR
```

`fpr open` fetches the selected GitHub base branch and publishes immutable base-generation refs plus the current feature SHA to the private Forgejo repository. If the GitHub base SHA changes, it uses a new local pull request, so an approval cannot silently carry across a changed diff.

Review the pull request while signed in as the configured human reviewer and submit **Approve**. `fpr ship` refuses to push unless all of the following still hold:

- the worktree is clean and `HEAD` is a non-default branch;
- the Forgejo pull request is open and its head SHA equals local `HEAD`;
- the latest effective review by the configured reviewer for that exact SHA is `APPROVED`;
- the GitHub base branch still equals the SHA used for local review;
- an existing GitHub feature branch is either the same SHA or an ancestor of it.

`fpr ship` never force-pushes a divergent GitHub branch. It creates or displays the GitHub pull request with `gh`; Forgejo is never merged.

Use a non-default target branch explicitly when needed:

```sh
fpr open --base release/next
fpr status --base release/next
fpr ship --base release/next
```

Pass `--no-browser` to `open` or `ship` in non-interactive sessions.

## Operations

```sh
cd ~/.local/share/forgejo-review
make status              # container and API health
make logs                # follow logs
make down                # retain all persistent data
make up
```

Update the pinned image in the dotfiles source, review Forgejo's release notes, apply chezmoi, then run `make up`. Do not use an unpinned `latest` tag.

### Backup

Stop writes first, then archive the named volume to a directory that is already protected by your backup system:

```sh
make down
backup_dir="$HOME/Backups/forgejo-review"
mkdir -p "$backup_dir"
docker run --rm \
  -v forgejo-review-data:/data:ro \
  -v "$backup_dir:/backup" \
  alpine:3.21 \
  tar -C /data -czf "/backup/forgejo-review-$(date +%Y%m%d).tar.gz" .
make up
```

The local review instance is reproducible, but its approval history is not recoverable from GitHub. Back up the volume if that history matters.

### Credential recovery

- If the API token is lost or invalid, remove only `~/.config/fpr/token` and rerun `make bootstrap REVIEWER=<login>`. Old server-side tokens should be revoked in Forgejo's user settings.
- If the dedicated SSH key is lost, remove the stale key from the `fpr-agent` account, remove the local key pair, and rerun bootstrap.
- If Forgejo's SSH host key intentionally changes, verify that the container/volume is the expected local instance, remove only its entries from `~/.config/fpr/known_hosts`, rerun bootstrap, then retry `fpr open`.
- Never add `~/.config/fpr`, the token, either SSH key file, or Docker volume exports to the dotfiles repository.

### Complete removal

`make down` is non-destructive. Deleting `forgejo-review-data`, `~/.config/fpr`, or the dedicated SSH key is destructive and intentionally has no Make target. Remove those manually only after confirming any needed backup.
