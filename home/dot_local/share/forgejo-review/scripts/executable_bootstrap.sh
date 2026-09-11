#!/bin/sh
set -eu

FORGEJO_URL=${FPR_FORGEJO_URL:-http://127.0.0.1:3000}
AGENT=${FPR_FORGEJO_OWNER:-fpr-agent}
CONFIG_HOME=${XDG_CONFIG_HOME:-"$HOME/.config"}
FPR_CONFIG_DIR=${FPR_CONFIG_DIR:-"$CONFIG_HOME/fpr"}
CONFIG_FILE=$FPR_CONFIG_DIR/config
TOKEN_FILE=$FPR_CONFIG_DIR/token
SSH_KEY=${FPR_FORGEJO_SSH_KEY:-"$HOME/.ssh/id_ed25519_fpr_agent"}
SSH_URL=${FPR_FORGEJO_SSH_URL:-ssh://git@127.0.0.1:2222}
KNOWN_HOSTS_FILE=${FPR_FORGEJO_KNOWN_HOSTS_FILE:-"$FPR_CONFIG_DIR/known_hosts"}

usage() {
  cat << 'EOF'
Usage: bootstrap.sh REVIEWER

Create the non-interactive fpr-agent account and its local credentials after
an administrator has completed Forgejo's first-run setup in the browser.
REVIEWER must name the human Forgejo account whose approvals gate fpr ship.
EOF
}

die() {
  printf 'bootstrap: %s\n' "$*" >&2
  exit 1
}

require() {
  command -v "$1" > /dev/null 2>&1 || die "required command not found: $1"
}

require_regular_or_absent() {
  target=$1
  [ ! -L "$target" ] || die "path must not be a symbolic link: $target"
  [ ! -e "$target" ] || [ -f "$target" ] || die "path is not a regular file: $target"
}

lowercase() {
  printf '%s' "$1" | tr '[:upper:]' '[:lower:]'
}

validate_loopback_url() {
  loopback_value=$1
  loopback_prefix=$2
  loopback_label=$3
  loopback_scheme=$4
  loopback_parts=$5
  loopback_authority=${loopback_value#"$loopback_prefix"}
  [ "$loopback_authority" != "$loopback_value" ] || die "$loopback_label must use $loopback_scheme"
  case $loopback_authority in
    */* | *\?* | *\#* | *@*) die "$loopback_label must contain only $loopback_parts" ;;
  esac
  case $loopback_authority in
    127.0.0.1:* | localhost:*) loopback_port=${loopback_authority#*:} ;;
    *) die "$loopback_label must use 127.0.0.1 or localhost" ;;
  esac
  case $loopback_port in
    '' | *[!0-9]*) die "$loopback_label must contain a numeric port" ;;
  esac
}

[ "$#" -eq 1 ] || {
  usage >&2
  exit 2
}
REVIEWER=$1
case $REVIEWER in
  '' | *[!A-Za-z0-9_.-]*) die "invalid reviewer username: $REVIEWER" ;;
esac
normalized_reviewer=$(lowercase "$REVIEWER")
normalized_agent=$(lowercase "$AGENT")
[ "$normalized_reviewer" != "$normalized_agent" ] || die "reviewer must be different from $AGENT"
validate_loopback_url "$FORGEJO_URL" 'http://' 'Forgejo URL' 'loopback HTTP' 'a loopback host and port'
validate_loopback_url "$SSH_URL" 'ssh://git@' 'Forgejo SSH URL' 'loopback SSH as git' \
  'the git user, loopback host, and port'
ssh_authority=${SSH_URL#ssh://git@}
SSH_HOST=${ssh_authority%%:*}
SSH_PORT=${ssh_authority#*:}
KNOWN_HOST_ID="[$SSH_HOST]:$SSH_PORT"

for command in curl docker jq ssh-keygen; do
  require "$command"
done

tmpdir=$(mktemp -d "${TMPDIR:-/tmp}/fpr-bootstrap.XXXXXX")
trap 'rm -rf "$tmpdir"' EXIT HUP INT TERM
script_dir=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
root=$(CDPATH='' cd -- "$script_dir/.." && pwd)

compose() {
  docker compose --project-directory "$root" -f "$root/compose.yaml" "$@"
}

printf 'Waiting for Forgejo at %s ...\n' "$FORGEJO_URL"
attempt=0
while ! curl --disable --noproxy '*' --silent --show-error --fail --max-time 2 "$FORGEJO_URL/" > /dev/null 2>&1; do
  attempt=$((attempt + 1))
  [ "$attempt" -lt 30 ] || die "Forgejo is unavailable; run 'make up'"
  sleep 1
done
user_list=$tmpdir/users.txt
if ! compose exec -T --user git forgejo forgejo admin user list > "$user_list" 2> "$tmpdir/admin-error"; then
  cat "$tmpdir/admin-error" >&2
  die "Forgejo is not initialized; open $FORGEJO_URL and create the human administrator first"
fi

shallow_update=$(compose exec -T --user git forgejo git config --system --get receive.shallowUpdate | tr -d '\r\n')
[ "$shallow_update" = true ] || die "system Git config does not allow shallow clone pushes in the review-only Forgejo instance"

if ! awk -v user="$AGENT" 'NR > 1 && $2 == user { found = 1 } END { exit !found }' "$user_list"; then
  printf 'Creating local service account %s ...\n' "$AGENT"
  compose exec -T --user git forgejo forgejo admin user create \
    --username "$AGENT" \
    --email "$AGENT@localhost.invalid" \
    --random-password \
    --must-change-password=false > /dev/null
fi

umask 077
mkdir -p "$FPR_CONFIG_DIR" "$(dirname -- "$SSH_KEY")" "$(dirname -- "$KNOWN_HOSTS_FILE")"
chmod 700 "$FPR_CONFIG_DIR" "$(dirname -- "$SSH_KEY")" "$(dirname -- "$KNOWN_HOSTS_FILE")"
require_regular_or_absent "$CONFIG_FILE"
require_regular_or_absent "$TOKEN_FILE"
require_regular_or_absent "$SSH_KEY"
require_regular_or_absent "$SSH_KEY.pub"
require_regular_or_absent "$KNOWN_HOSTS_FILE"
: >> "$KNOWN_HOSTS_FILE"
chmod 600 "$KNOWN_HOSTS_FILE"

server_host_key=$(compose exec -T forgejo cat /data/ssh/ssh_host_ed25519_key.pub | tr -d '\r')
server_key_type=$(printf '%s\n' "$server_host_key" | awk 'NR == 1 { print $1 }')
server_key_blob=$(printf '%s\n' "$server_host_key" | awk 'NR == 1 { print $2 }')
[ "$server_key_type" = ssh-ed25519 ] && [ -n "$server_key_blob" ] ||
  die "cannot read Forgejo's Ed25519 SSH host key from the container"
ssh-keygen -F "$KNOWN_HOST_ID" -f "$KNOWN_HOSTS_FILE" > "$tmpdir/trusted-host-keys" 2> /dev/null || true
if [ -s "$tmpdir/trusted-host-keys" ]; then
  awk -v type="$server_key_type" -v blob="$server_key_blob" \
    '$1 !~ /^#/ && $2 == type && $3 == blob { found = 1 } END { exit !found }' \
    "$tmpdir/trusted-host-keys" ||
    die "Forgejo SSH host key changed; verify the local container and remove only $KNOWN_HOST_ID from $KNOWN_HOSTS_FILE"
else
  printf '%s %s %s\n' "$KNOWN_HOST_ID" "$server_key_type" "$server_key_blob" >> "$KNOWN_HOSTS_FILE"
fi

valid_token=false
if [ -s "$TOKEN_FILE" ]; then
  token=$(tr -d '\r\n' < "$TOKEN_FILE")
  printf 'header = "Authorization: token %s"\n' "$token" > "$tmpdir/curl.conf"
  if curl --disable --noproxy '*' --silent --show-error --fail --config "$tmpdir/curl.conf" \
    "$FORGEJO_URL/api/v1/user" > "$tmpdir/actor.json" 2> /dev/null &&
    jq -e --arg agent "$AGENT" '.login == $agent' "$tmpdir/actor.json" > /dev/null; then
    valid_token=true
  fi
fi

if [ "$valid_token" != true ]; then
  printf 'Generating an API token for %s ...\n' "$AGENT"
  token_name="fpr-$(date -u +%Y%m%dT%H%M%SZ)"
  token=$(compose exec -T --user git forgejo forgejo admin user generate-access-token \
    --username "$AGENT" \
    --token-name "$token_name" \
    --scopes write:repository,write:user \
    --raw | tr -d '\r\n')
  [ -n "$token" ] || die "Forgejo returned an empty access token"
  printf '%s\n' "$token" > "$tmpdir/token"
  chmod 600 "$tmpdir/token"
  mv "$tmpdir/token" "$TOKEN_FILE"
  printf 'header = "Authorization: token %s"\n' "$token" > "$tmpdir/curl.conf"
fi
chmod 600 "$TOKEN_FILE"

if ! curl --disable --noproxy '*' --silent --show-error --fail --config "$tmpdir/curl.conf" \
  "$FORGEJO_URL/api/v1/users/$REVIEWER" > "$tmpdir/reviewer.json"; then
  die "reviewer '$REVIEWER' does not exist or is not visible to $AGENT"
fi
jq -e --arg reviewer "$REVIEWER" '.login | ascii_downcase == ($reviewer | ascii_downcase)' \
  "$tmpdir/reviewer.json" > /dev/null || die "Forgejo returned the wrong reviewer account"

if [ ! -s "$SSH_KEY" ]; then
  printf 'Creating the dedicated Forgejo SSH key %s ...\n' "$SSH_KEY"
  ssh-keygen -q -t ed25519 -N '' -C "$AGENT@forgejo-review" -f "$SSH_KEY"
fi
chmod 600 "$SSH_KEY"
chmod 644 "$SSH_KEY.pub"

key_blob=$(awk 'NR == 1 { print $2 }' "$SSH_KEY.pub")
: > "$tmpdir/keys.ndjson"
key_page=1
while [ "$key_page" -le 100 ]; do
  curl --disable --noproxy '*' --silent --show-error --fail --config "$tmpdir/curl.conf" \
    "$FORGEJO_URL/api/v1/user/keys?limit=100&page=$key_page" > "$tmpdir/keys-page.json"
  key_count=$(jq 'length' "$tmpdir/keys-page.json")
  [ "$key_count" -gt 0 ] || break
  jq -c '.[]' "$tmpdir/keys-page.json" >> "$tmpdir/keys.ndjson"
  key_page=$((key_page + 1))
done
[ "$key_page" -le 100 ] || die "too many SSH keys to evaluate safely"
if ! jq -s -e --arg blob "$key_blob" 'any(.[]; ((.key // "") | split(" ")[1]) == $blob)' \
  "$tmpdir/keys.ndjson" > /dev/null; then
  jq -n --arg title "$AGENT@$(hostname -s)" --rawfile key "$SSH_KEY.pub" \
    '{title: $title, key: ($key | rtrimstr("\n"))}' > "$tmpdir/key.json"
  curl --disable --noproxy '*' --silent --show-error --fail-with-body --config "$tmpdir/curl.conf" \
    --header 'Content-Type: application/json' \
    --request POST --data-binary "@$tmpdir/key.json" \
    "$FORGEJO_URL/api/v1/user/keys" > "$tmpdir/new-key.json"
fi

cat > "$tmpdir/config" << EOF
forgejo_url=$FORGEJO_URL
forgejo_owner=$AGENT
forgejo_reviewer=$REVIEWER
forgejo_ssh_url=$SSH_URL
forgejo_ssh_key=$SSH_KEY
forgejo_known_hosts_file=$KNOWN_HOSTS_FILE
token_file=$TOKEN_FILE
github_remote=origin
EOF
chmod 600 "$tmpdir/config"
mv "$tmpdir/config" "$CONFIG_FILE"

printf '\nBootstrap complete. Local-only files:\n'
printf '  config: %s\n' "$CONFIG_FILE"
printf '  token:  %s\n' "$TOKEN_FILE"
printf '  key:    %s\n' "$SSH_KEY"
printf '  hosts:  %s\n' "$KNOWN_HOSTS_FILE"
printf '\nRun: fpr doctor\n'
