#!/bin/sh
# Check that every Renovate-managed mise tool resolves to a datasource that
# provides releaseTimestamp. Datasources such as java-version, git-tags, and
# git-refs have no timestamps, so with minimumReleaseAge +
# internalChecksFilter=strict every release stays "pending" forever and no
# update PR is created. See docs/renovate-mise-release-age.md.
set -eu

script_dir=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
repo=$(CDPATH='' cd -- "$script_dir/.." && pwd)
checker="$script_dir/check-mise-renovate-age.py"

config=${1:-"$repo/home/dot_config/mise/config.toml"}
renovate_config=${RENOVATE_CONFIG:-"$repo/.github/renovate-self-hosted.json"}
renovate_workflow=${RENOVATE_WORKFLOW:-"$repo/.github/workflows/renovate.yml"}
renovate_ref=${RENOVATE_REF:-}

if [ -z "$renovate_ref" ]; then
  renovate_ref=$(awk -F: '/renovate-version:/ { gsub(/^[[:space:]]+|[[:space:]]+$/, "", $2); print $2; exit }' "$renovate_workflow" 2>/dev/null || true)
  renovate_ref=${renovate_ref:-main}
fi
base="https://raw.githubusercontent.com/renovatebot/renovate/$renovate_ref"

if [ ! -f "$config" ]; then
  echo "usage: $0 [mise-config.toml]" >&2
  exit 2
fi

find_python() {
  if [ -n "${PYTHON:-}" ]; then
    printf '%s\n' "$PYTHON"
  elif command -v python3 >/dev/null 2>&1; then
    command -v python3
  elif command -v python >/dev/null 2>&1; then
    command -v python
  fi
}

python_bin=$(find_python || true)
if [ -z "$python_bin" ]; then
  echo "python3 is required to parse mise TOML" >&2
  exit 2
fi

if [ -f "$renovate_config" ]; then
  "$python_bin" "$checker" check-renovate-config "$renovate_config"
fi

tmpdir=$(mktemp -d "${TMPDIR:-/tmp}/dotfiles-mise-renovate.XXXXXX")
trap 'rm -rf "$tmpdir"' EXIT INT TERM

curl -fsS "$base/lib/modules/manager/mise/upgradeable-tooling.ts" -o "$tmpdir/mise-tooling.ts" &
mise_tooling_pid=$!
curl -fsS "$base/lib/modules/manager/asdf/upgradeable-tooling.ts" -o "$tmpdir/asdf-tooling.ts" &
asdf_tooling_pid=$!
curl -fsS "$base/lib/data/mise-registry.json" -o "$tmpdir/mise-registry.json" &
mise_registry_pid=$!

wait "$mise_tooling_pid"
wait "$asdf_tooling_pid"
wait "$mise_registry_pid"

tab=$(printf '\t')

# Emit the same tool surfaces Renovate's mise manager reads: top-level tools and
# tasks.*.tools. Values are reduced like Renovate's parseVersion(): string,
# first string from an array, or a table's version string.
tools_file=$tmpdir/tools.tsv
"$python_bin" "$checker" emit-mise-tools "$config" >"$tools_file"

if [ ! -s "$tools_file" ]; then
  echo "no Renovate-managed mise tools found in $config" >&2
  exit 2
fi

registry_tools=$tmpdir/registry-tools.tsv
"$python_bin" "$checker" emit-registry-tools "$tmpdir/mise-registry.json" >"$registry_tools"

regex_tracked=$tmpdir/regex-tracked.txt
disabled_mise=$tmpdir/disabled-mise.txt
: >"$regex_tracked"
: >"$disabled_mise"
if [ -f "$renovate_config" ]; then
  "$python_bin" "$checker" emit-renovate-overrides "$renovate_config" "$regex_tracked" "$disabled_mise"
fi

is_listed() {
  grep -qxF "$2" "$1"
}

registry_lookup() {
  awk -F "$tab" -v tool="$1" '$1 == tool { print $2 "\t" $3; exit }' "$registry_tools"
}

clean_datasource_line() {
  sed -e 's/.*datasource: //' -e 's/Datasource[.]id.*//' -e 's/[ '\'',"]//g'
}

static_datasource() {
  direct=$(awk -v tool="$2" '
    /^  / {
      line = $0
      sub(/^  /, "", line)
      if (line ~ /: \{$/) {
        key = line
        sub(/: \{$/, "", key)
        gsub(/\047/, "", key)
        if (key == tool) in_block = 1
      }
    }
    in_block && /datasource:/ { print; exit }
    in_block && /^  \},$/ { exit }
  ' "$1" | clean_datasource_line)
  if [ -n "$direct" ]; then
    printf '%s\n' "$direct"
    return
  fi

  alias=$(awk -v tool="$2" '
    /^  / {
      line = $0
      sub(/^  /, "", line)
      if (line ~ /: [A-Za-z_][A-Za-z0-9_]*,$/) {
        key = line
        sub(/:.*/, "", key)
        gsub(/\047/, "", key)
        if (key == tool) {
          sub(/^[^:]*: /, "", line)
          sub(/,$/, "", line)
          print line
          exit
        }
      }
    }
  ' "$1")
  [ -n "$alias" ] || return 0

  awk -v alias="$alias" '
    $0 ~ "^const " alias "[^=]*= \\{$" { in_block = 1; next }
    in_block && /datasource:/ { print; exit }
    in_block && /^};$/ { exit }
  ' "$1" | clean_datasource_line
}

static_datasource_any() {
  ds=$(static_datasource "$tmpdir/mise-tooling.ts" "$1")
  if [ -n "$ds" ]; then
    printf '%s\n' "$ds"
    return
  fi

  static_datasource "$tmpdir/asdf-tooling.ts" "$1"
}

verdict_for_datasource() {
  case $1 in
  java-version | JavaVersion) echo "NG no releaseTimestamp ($2)" ;;
  git-tags | GitTags | git-refs | GitRefs) echo "NG no releaseTimestamp ($2)" ;;
  github-tags | GithubTags | github-releases | GithubReleases | npm | Npm | \
    pypi | Pypi | crate | Crate | rubygems | Rubygems | go | Go | \
    nuget | Nuget | NodeVersion | node-version | RubyVersion | ruby-version | \
    HexpmBob | hexpm-bob) echo "OK $2" ;;
  *) echo "WARN unknown datasource ($2)" ;;
  esac
}

classify_backend() {
  backend=$1
  name=$2
  version=$3
  case $backend in
  core)
    ds=$(static_datasource "$tmpdir/mise-tooling.ts" "$name")
    if [ -n "$ds" ]; then
      verdict_for_datasource "$ds" "core static $name -> $ds"
    else
      echo "WARN core tool is not in Renovate static mappings"
    fi
    ;;
  asdf)
    ds=$(static_datasource "$tmpdir/asdf-tooling.ts" "$name")
    if [ -n "$ds" ]; then
      verdict_for_datasource "$ds" "asdf static $name -> $ds"
    else
      echo "WARN asdf tool is not in Renovate static mappings"
    fi
    ;;
  vfox)
    ds=$(static_datasource_any "$name")
    if [ -n "$ds" ]; then
      verdict_for_datasource "$ds" "vfox static $name -> $ds"
    else
      echo "WARN vfox tool is not in Renovate static mappings"
    fi
    ;;
  aqua)
    ds=$(static_datasource_any "$name")
    if [ -n "$ds" ]; then
      verdict_for_datasource "$ds" "aqua static $name -> $ds"
    else
      echo "OK aqua -> github-tags"
    fi
    ;;
  github | ubi) echo "OK $backend -> github-releases" ;;
  npm) echo "OK npm -> npm" ;;
  pipx)
    case $name in
    git+https://github.com/*.git) echo "OK pipx GitHub git -> github-tags" ;;
    git+*) echo "NG no releaseTimestamp (pipx git -> git-refs)" ;;
    http://* | https://*) echo "WARN pipx URL is unsupported by Renovate" ;;
    */*) echo "OK pipx GitHub shorthand -> github-tags" ;;
    *) echo "OK pipx -> pypi" ;;
    esac
    ;;
  cargo)
    case $name in
    http://* | https://*)
      case $version in
      tag:*) echo "NG no releaseTimestamp (cargo URL tag -> git-tags)" ;;
      branch:* | rev:*) echo "NG no releaseTimestamp (cargo URL ref -> git-refs)" ;;
      *) echo "WARN cargo URL requires tag:/branch:/rev: version" ;;
      esac
      ;;
    *) echo "OK cargo -> crate" ;;
    esac
    ;;
  gem) echo "OK gem -> rubygems" ;;
  go) echo "OK go -> go" ;;
  dotnet) echo "OK dotnet -> nuget" ;;
  spm)
    case $name in
    http://* | https://*)
      case $name in
      https://github.com/*.git) echo "OK spm GitHub URL -> github-releases" ;;
      *) echo "WARN spm non-GitHub URL is unsupported by Renovate" ;;
      esac
      ;;
    *) echo "OK spm -> github-releases" ;;
    esac
    ;;
  *) echo "WARN unknown backend ($backend)" ;;
  esac
}

classify() {
  tool=$1
  version=$2
  case $tool in
  *:*)
    classify_backend "${tool%%:*}" "${tool#*:}" "$version"
    return
    ;;
  esac

  ds=$(static_datasource_any "$tool")
  if [ -n "$ds" ]; then
    verdict_for_datasource "$ds" "static -> $ds"
    return
  fi

  registry=$(registry_lookup "$tool")
  if [ -z "$registry" ]; then
    echo "WARN not known to Renovate (no static mapping, not in mise registry)"
    return
  fi

  IFS="$tab" read -r registry_backend registry_name <<EOF
$registry
EOF
  classify_backend "$registry_backend" "$registry_name" "$version"
}

fail=0
while IFS="$tab" read -r tool version; do
  [ -n "$tool" ] || continue
  if is_listed "$regex_tracked" "$tool" && is_listed "$disabled_mise" "$tool"; then
    printf '%-45s %s\n' "$tool" "OK regex custom manager and disabled mise lookup in $renovate_config"
    continue
  fi
  result=$(classify "$tool" "$version")
  case $result in
  OK*) ;;
  NG* | WARN*)
    if is_listed "$regex_tracked" "$tool"; then
      result="NG regex custom manager exists but mise lookup is not disabled in $renovate_config"
    fi
    fail=1
    ;;
  esac
  printf '%-45s %s\n' "$tool" "$result"
done <"$tools_file"

if [ "$fail" -ne 0 ]; then
  cat >&2 <<'EOF'

Some tools resolve to a datasource without releaseTimestamp, an unsupported
Renovate path, or an unreviewed unknown classification. Fix by switching to a
timestamped datasource/backend, or add a regex custom manager and disable the
mise lookup as described in docs/renovate-mise-release-age.md.
EOF
fi
exit "$fail"
