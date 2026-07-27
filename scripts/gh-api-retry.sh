#!/bin/sh
# Retry idempotent `gh api` GET requests after transient GitHub API failures.
# Primary rate-limit waits use GET /rate_limit, which does not consume the
# primary limit. Other rate limits, HTTP 429/5xx, and common network errors use
# bounded backoff. Ordinary client and permission errors fail immediately.
set -eu

max_attempts=6
max_total_wait=600
rate_limit_max_wait=300

if [ "$#" -eq 0 ]; then
  echo "usage: gh-api-retry.sh <REST endpoint> [gh api GET options]" >&2
  exit 2
fi
case "$1" in
  ''|-*)
    echo "gh-api-retry requires the REST endpoint as its first argument" >&2
    exit 2
    ;;
esac

for arg in "$@"; do
  case "$arg" in
    -X*|-f*|-F*|--method|--raw-field|--field|--input|\
      --method=*|--raw-field=*|--field=*|--input=*|graphql)
      echo "gh-api-retry only accepts idempotent REST GET requests" >&2
      exit 2
      ;;
  esac
done

out_file=
err_file=
cleanup() {
  [ -z "$out_file" ] || rm -f "$out_file"
  [ -z "$err_file" ] || rm -f "$err_file"
}
trap cleanup 0
trap 'exit 1' 1 2 15
out_file=$(mktemp)
err_file=$(mktemp)

attempt=1
total_wait=0
while :; do
  gh api "$@" >"$out_file" 2>"$err_file" && rc=0 || rc=$?
  if [ "$rc" -eq 0 ]; then
    cat "$err_file" >&2 || true
    cat "$out_file"
    exit 0
  fi

  err=$(cat "$err_file" 2>/dev/null || true)
  err_lc=$(printf '%s' "$err" | tr '[:upper:]' '[:lower:]')
  printf '%s\n' "$err" >&2

  retry_kind=
  case "$err_lc" in
    *'rate limit'*|*'(http 429)'*|*'gh: http 429'*) retry_kind=rate_limit ;;
    *'(http 5'[0-9][0-9]')'*|*'gh: http 5'[0-9][0-9]*) retry_kind=transient ;;
    *'connection closed'*|*'connection refused'*|*'connection reset'*) retry_kind=transient ;;
    *'connection timed out'*|*'context deadline exceeded'*|*'dial tcp'*) retry_kind=transient ;;
    *'error connecting to api.github.com'*|*'i/o timeout'*|*'network error'*) retry_kind=transient ;;
    *'network is unreachable'*|*'no such host'*|*'proxyconnect tcp'*) retry_kind=transient ;;
    *'server misbehaving'*|*'temporary failure in name resolution'*) retry_kind=transient ;;
    *'tls handshake timeout'*|*'unexpected eof'*|*' eof'*|eof) retry_kind=transient ;;
    *'client.timeout exceeded'*|*'broken pipe'*) retry_kind=transient ;;
  esac

  if [ -z "$retry_kind" ] || [ "$attempt" -ge "$max_attempts" ]; then
    exit "$rc"
  fi

  remaining_wait=$((max_total_wait - total_wait))
  if [ "$remaining_wait" -le 0 ]; then
    exit "$rc"
  fi

  delay=$((5 * attempt))
  if [ "$retry_kind" = rate_limit ]; then
    delay=$((60 * attempt))
    reset=$(gh api rate_limit --jq '.resources.core | select(.remaining == 0) | .reset // empty' 2>/dev/null || true)
    now=$(date +%s 2>/dev/null || true)
    case "$reset" in
      ''|*[!0-9]*) reset='' ;;
    esac
    case "$now" in
      ''|*[!0-9]*) now='' ;;
    esac
    if [ -n "$reset" ] && [ -n "$now" ]; then
      wait_for=$((reset - now + 2))
      if [ "$wait_for" -gt "$delay" ]; then
        delay=$wait_for
      fi
    fi
    if [ "$delay" -gt "$rate_limit_max_wait" ]; then
      delay=$rate_limit_max_wait
    fi
  fi

  if [ "$delay" -gt "$remaining_wait" ]; then
    delay=$remaining_wait
  fi

  echo "gh-api-retry: attempt ${attempt}/${max_attempts} failed (retryable); retrying in ${delay}s" >&2
  sleep "$delay"
  total_wait=$((total_wait + delay))
  attempt=$((attempt + 1))
done
