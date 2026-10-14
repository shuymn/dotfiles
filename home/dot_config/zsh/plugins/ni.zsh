# Alternative ni written in ShellScript
# SPDX-License-Identifier: MIT
# Author: @azu
# Repository: https://github.com/azu/ni.zsh
# Original: https://github.com/antfu/ni
#
# Socket Firewall Integration
# ----------------------------
# This script supports Socket Firewall (https://github.com/SocketDev/sfw-free)
# for proactive protection against malicious packages.
#
# Setup:
#   1. Install Socket Firewall: npm i -g sfw
#   2. Enable in ni.zsh: export NI_USE_SOCKET_FIREWALL=1
#   3. Specify sfw path: export NI_SOCKET_FIREWALL_BIN=/path/to/sfw
#      If not set, uses 'sfw' command from PATH
#
# When enabled, all package install/add commands and npx/bunx executions
# will be automatically protected by Socket Firewall.

# Get Socket Firewall command path
function ni-getSocketFirewallBin() {
  # Use custom path if specified, otherwise use 'sfw' command
  echo "${NI_SOCKET_FIREWALL_BIN:-sfw}"
}

# Check if Socket Firewall (sfw) should be used
# Enabled by setting NI_USE_SOCKET_FIREWALL=1
# Requires: sfw command (npm i -g sfw) or NI_SOCKET_FIREWALL_BIN set
function ni-shouldUseSocketFirewall() {
  # Check if Socket Firewall is enabled via environment variable
  if [ -z "$NI_USE_SOCKET_FIREWALL" ]; then
    return 1
  fi

  local sfwBin
  sfwBin=$(ni-getSocketFirewallBin)

  # Check if sfw command/path is available
  if ! command -v "$sfwBin" >/dev/null 2>&1; then
    return 1
  fi
  return 0
}

function ni-echoRun() {
  emulate -L zsh
  local cmd="$1" sfwBin=""
  shift

  if ni-shouldUseSocketFirewall; then
    case $cmd in
      npm|yarn|pnpm|bun|deno)
        case "$1" in
          install|add|i) sfwBin=$(ni-getSocketFirewallBin) ;;
        esac
        ;;
      npx|bunx)
        sfwBin=$(ni-getSocketFirewallBin)
        ;;
    esac
  fi

  if [[ -n "$sfwBin" ]]; then
    print -r -- "\$ ${(q)sfwBin} ${(q)cmd} ${(j: :)${(q)@}}"
    command "$sfwBin" "$cmd" "$@"
  else
    print -r -- "\$ ${(q)cmd} ${(j: :)${(q)@}}"
    command "$cmd" "$@"
  fi
}

# Support package manager
# - npm
# - yarn - v1
# - yarn-berry - v2+
# - pnpm
# - bun
# - deno - v2+
function ni-getPackageManager() {
  # cwd is argument 1, if not set, use current directory
  local cwd=${1:-$(pwd)}
  # detect package manager via package.json
  if [ -f "${cwd}/package.json" ]; then
    local packageManager
    packageManager=$(jq -r '.packageManager // empty' "${cwd}/package.json") || return
    if [[ -n "$packageManager" ]]; then
      # parse packageManager name from "<pkg>@<version>"
      local packageManagerName=${packageManager%%@*}
      local packageManagerMajorVersion=${${packageManager#*@}%%.*}
      # supported package manager
      if [ "$packageManagerName" = "npm" ] || [ "$packageManagerName" = "pnpm" ] || [ "$packageManagerName" = "yarn" ] || [ "$packageManagerName" = "bun" ]; then
        # yarn and version >= 2, then  yarn-berry
        if [[ "$packageManagerName" == yarn && "$packageManagerMajorVersion" == <-> ]] && (( packageManagerMajorVersion >= 2 )); then
          echo "yarn-berry"
          return
        fi
        echo "$packageManagerName"
        return
      fi
    fi
  fi

  # detect package manager via lock file or config file
  if [ -f "${cwd}/deno.lock" ] || [ -f "${cwd}/deno.json" ]; then
    echo "deno"
  elif [ -f "${cwd}/pnpm-lock.yaml" ]; then
    echo "pnpm"
  elif [ -f "${cwd}/bun.lock" ] || [ -f "${cwd}/bun.lockb" ]; then
    # choose bun if both bun.lockb and yarn.lock exist
    # bun generate yarn.lock and bun.lockb when print=yarn is set
    # https://bun.sh/docs/install/lockfile
    echo "bun"
  elif [ -f "${cwd}/yarn.lock" ]; then
    echo "yarn"
  elif [ -f "${cwd}/package-lock.json" ]; then
    echo "npm"
  # if current directory does not contain any lock file, then check git root directory
  # Note: if current is in workspace, then use workspace package manager which is defined in root directory
  else
    local rootDir
    rootDir=$(git rev-parse --show-toplevel 2>/dev/null)
    if [ -z "$rootDir" ]; then
      # default to npm
      echo "npm"
      return
    fi
    local parentDir
    parentDir=$(dirname "$cwd")
    # if parentDir is not under of rootDir, then default to npm
    # it is out of workspace
    if [[ "$parentDir" != "$rootDir"* ]]; then
      echo "npm"
      return
    fi
    # recursive call to getPackageManager
    local ret
    ret=$(ni-getPackageManager "$parentDir") || return
    if [ -n "$ret" ]; then
      echo "$ret"
      return
    fi
  fi
}

# ni - install
## npm install
## yarn install
## pnpm install
## bun install
## deno install
# Note: # ni <subcommand> - run subcommand
function ni() {
  emulate -L zsh
  # with argument - subcommand
  if [ $# -gt 0 ]; then
    case $1 in
      add)
        shift
        ni-add "$@"
        ;;
      run)
        shift
        ni-run "$@"
        ;;
      upgrade)
        shift
        ni-upgrade "$@"
        ;;
      upgrade-interactive)
        shift
        ni-upgrade-interactive "$@"
        ;;
      remove)
        shift
        ni-remove "$@"
        ;;
      # Special ni run <script>
      test)
        shift
        ni-run test "$@"
        ;;
      exec)
        shift
        ni-exec "$@"
        ;;
      dlx)
        shift
        ni-dlx "$@"
        ;;
      *)
        print -u2 -- "Unknown subcommand: $1"
        return 2
        ;;
    esac
    return
  fi
  # without argument - install
  local manager
  manager=$(ni-getPackageManager) || return
  case $manager in
    npm)
      ni-echoRun npm install
      ;;
    yarn*)
      ni-echoRun yarn install
      ;;
    pnpm)
      ni-echoRun pnpm install
      ;;
    bun)
      ni-echoRun bun install
      ;;
    deno)
      ni-echoRun deno install
      ;;
  esac
}

# ni add - add package
# $ ni add vite
## npm install vite
## yarn add vite
## pnpm add vite
## bun add vite
## deno add npm:vite
# $ ni @types/node --dev
## npm install @types/node -D
## yarn add @types/node -D
## pnpm add -D @types/node
## bun add -d @types/node

function ni-add() {
  local -a args=()
  local dev=false manager
  while (( $# > 0 )); do
    case "$1" in
      -D|--dev) dev=true ;;
      *) args+=("$1") ;;
    esac
    shift
  done

  manager=$(ni-getPackageManager) || return
  if [[ "$dev" == true ]]; then
    case $manager in
      npm) args+=(--save-dev) ;;
      yarn*|deno) args+=(--dev) ;;
      pnpm) args+=(-D) ;;
      bun) args+=(-d) ;;
    esac
  fi

  case $manager in
    npm) ni-echoRun npm install "${args[@]}" ;;
    yarn*) ni-echoRun yarn add "${args[@]}" ;;
    pnpm) ni-echoRun pnpm add "${args[@]}" ;;
    bun) ni-echoRun bun add "${args[@]}" ;;
    deno) ni-echoRun deno add --npm "${args[@]}" ;;
  esac
}

# ni run - run scripts
# $ ni run dev --port=3000
## npm run dev -- --port=3000
## yarn run dev --port=3000
## pnpm run dev --port=3000
## bun run dev --port=3000
## deno run dev --port=3000
function ni-run() {
  local manager
  manager=$(ni-getPackageManager) || return
  case $manager in
    npm) ni-echoRun npm run -- "$@" ;;
    yarn*) ni-echoRun yarn run "$@" ;;
    pnpm) ni-echoRun pnpm run "$@" ;;
    bun) ni-echoRun bun run "$@" ;;
    deno) ni-echoRun deno run "$@" ;;
  esac
}

# ni upgrade - upgrade package
## npm upgrade
## yarn upgrade (Yarn 1)
## yarn up (Yarn Berry)
## pnpm update
## bun update
## deno outdated --update
function ni-upgrade(){
  local manager
  manager=$(ni-getPackageManager) || return
  case $manager in
    npm)
      ni-echoRun npm upgrade "$@"
      ;;
    yarn)
      ni-echoRun yarn upgrade "$@"
      ;;
    yarn-berry)
      ni-echoRun yarn up "$@"
      ;;
    pnpm)
      ni-echoRun pnpm update "$@"
      ;;
    bun)
      # https://bun.sh/blog/bun-v0.8.0
      ni-echoRun bun update "$@"
      ;;
    deno)
      ni-echoRun deno outdated --update "$@"
      ;;
  esac
}

# ni upgrade-interactive - upgrade package interactively
# use https://github.com/dylang/npm-check
function ni-upgrade-interactive(){
  local manager
  manager=$(ni-getPackageManager) || return
  case $manager in
    npm)
      ni-echoRun npm-check -u
      ;;
    yarn)
      ni-echoRun yarn upgrade-interactive --latest
      ;;
    yarn-berry)
      ni-echoRun yarn up --interactive '*'
      ;;
    pnpm)
      ni-echoRun pnpm --recursive update -i --latest
      ;;
    bun)
      print -u2 -- "bun does not support upgrade interactive command"
      return 1
      ;;
    deno)
      # https://github.com/denoland/deno/releases/tag/v2.2.0
      ni-echoRun deno outdated --update --interactive --latest
      ;;
  esac
}
# ni remove - remove package
# $ nu remove webpack
## npm uninstall webpack
## yarn remove webpack
## pnpm remove webpack
## bun remove webpack
## deno uninstall npm:webpack
function ni-remove(){
  local manager
  manager=$(ni-getPackageManager) || return
  case $manager in
    npm)
      ni-echoRun npm uninstall "$@"
      ;;
    yarn*)
      ni-echoRun yarn remove "$@"
      ;;
    pnpm)
      ni-echoRun pnpm remove "$@"
      ;;
    bun)
      ni-echoRun bun remove "$@"
      ;;
    deno)
      ni-echoRun deno uninstall "$@"
      ;;
  esac
}

# ni exec - execute command
# $ ni exec envinfo
## npm exec envinfo
## yarn exec envinfo
## pnpm exec envinfo
## bunx envinfo
## [ ] deno 
function ni-exec(){
  local manager
  manager=$(ni-getPackageManager) || return
  case $manager in
    npm)
      # https://docs.npmjs.com/cli/v8/commands/npm-exec
      ni-echoRun npm exec --no -- "$@"
      ;;
    yarn)
      # yarn v1 does not support exec
      ni-echoRun yarn "$@"
      ;;
    yarn-berry)
      ni-echoRun yarn exec "$@"
      ;;
    pnpm)
      ni-echoRun pnpm exec "$@"
      ;;
    bun)
      ni-echoRun bunx "$@"
      ;;
    deno)
      print -u2 -- "deno does not support exec command"
      return 1
      ;;
  esac
}

# ni dlx -- download and execute command
# $ ni dlx envinfo
## npx envinfo
## yarn dlx envinfo
## pnpm dlx envinfo
## bunx envinfo
## [ ] deno
function ni-dlx(){
  local manager
  manager=$(ni-getPackageManager) || return
  case $manager in
    npm)
      ni-echoRun npx "$@"
      ;;
    yarn)
      # yarn v1 does not support dlx
      ni-echoRun npx "$@"
      ;;
    yarn-berry)
      ni-echoRun yarn dlx "$@"
      ;;
    pnpm)
      ni-echoRun pnpm dlx "$@"
      ;;
    bun)
      ni-echoRun bunx "$@"
      ;;
    deno)
      print -u2 -- "deno does not support dlx command"
      return 1
      ;;
  esac
}


# auto completion
function _ni(){
  local context state state_descr line
  typeset -A opt_args

  if ! command -v jq >/dev/null 2>&1; then
    _message -e "jq command is required to use ni.zsh"
    return 1
  fi

  _arguments -C \
    '1: :->cmds' \
    '*:: :->args'

  case "$state" in
    cmds)
      # ni <subcommands>
      local -a subcommands
      subcommands=(
        'add:add package'
        'run:run scripts'
        'test:run test script'
        'upgrade:upgrade package'
        'upgrade-interactive:upgrade package interactively'
        'remove:remove package'
        'exec:execute command'
        'dlx:download package and execute command'
      )
      _describe -t subcommands 'subcommands' subcommands
      ;;
    args)
      case $line[1] in
        add)
          # ni add <package>
          _arguments \
            '--dev[Install as development dependency]' \
            '-D[Install as development dependency]'
          ;;
        remove|upgrade)
          # ni remove <package>
          # ni upgrade <package>
          if [ -f "package.json" ]; then
            local -a packages
            packages=(${(f)"$(cat package.json | jq -r '.dependencies // {} | to_entries | .[] | select(.key != "") | "\(.key):\(.value)"')"})
            packages+=(${(f)"$(cat package.json | jq -r '.devDependencies // {} | to_entries | .[] | select(.key != "") | "\(.key):\(.value)"')"})
            _describe -t packages 'packages' packages
          fi
          ;;
        run)
          # ni run <script>
          if [ -f "package.json" ]; then
            local -a script_entries
            local key value escaped_key
            while IFS=$'\t' read -r key value; do
              escaped_key=${key//:/\\:}
              script_entries+=("$escaped_key:$value")
              done < <(cat package.json | jq -r '.scripts // {} | to_entries | .[] | select(.key != "") | "\(.key)\t\(.value)"')
            _describe -t scripts 'scripts' script_entries
          elif [ -f "deno.json" ]; then
            local -a task_entries
            local key value escaped_key
            while IFS=$'\t' read -r key value; do
              escaped_key=${key//:/\\:}
              task_entries+=("$escaped_key:$value")
            done < <(cat deno.json | jq -r '.tasks // {} | to_entries | .[] | select(.key != "") | "\(.key)\t\(.value)"')
            _describe -t tasks 'tasks' task_entries
          else
            _files
          fi
          ;;
        exec)
          # ni exec <command>
          if [ -d "$PWD/node_modules/.bin" ]; then
            _files -W "$PWD/node_modules/.bin" -g '*(-x)'
          else
            _files
          fi
          ;;
      esac
      ;;
  esac
}

compdef _ni ni