# Glimpse companion hook for Claude Code

This chezmoi-managed hook forwards Claude Code hook events to an already-running Glimpse companion daemon.

Target after `chezmoi apply`:

```text
~/.claude/hooks/glimpse-companion.mjs
~/.claude/hooks/glimpse-companion-socket-path.mjs
```

The hook is intentionally scoped to forwarding only:

- it does not start the daemon;
- it does not stop or toggle the daemon;
- it exits successfully and stays quiet when no daemon is listening.

## Prerequisite

Start a compatible Glimpse companion daemon separately. The daemon must listen on the same socket path used by `glimpse-companion-socket-path.mjs` and accept one JSON message per line. This helper is aligned with the companion extension in `pi-extensions/extensions/companion/socket-path.ts`.

## Claude Code settings

Merge this into `~/.claude/settings.json` if you want the hook enabled:

```json
{
  "hooks": {
    "UserPromptSubmit": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "node ~/.claude/hooks/glimpse-companion.mjs"
          }
        ]
      }
    ],
    "PreToolUse": [
      {
        "matcher": ".*",
        "hooks": [
          {
            "type": "command",
            "command": "node ~/.claude/hooks/glimpse-companion.mjs"
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": ".*",
        "hooks": [
          {
            "type": "command",
            "command": "node ~/.claude/hooks/glimpse-companion.mjs"
          }
        ]
      }
    ],
    "PostToolUseFailure": [
      {
        "matcher": ".*",
        "hooks": [
          {
            "type": "command",
            "command": "node ~/.claude/hooks/glimpse-companion.mjs"
          }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "node ~/.claude/hooks/glimpse-companion.mjs"
          }
        ]
      }
    ],
    "StopFailure": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "node ~/.claude/hooks/glimpse-companion.mjs"
          }
        ]
      }
    ]
  }
}
```

## Messages

The script sends messages compatible with the companion protocol:

```json
{ "id": "session-id", "project": "project", "status": "thinking", "detail": "optional" }
```

Remove messages are not sent by this scoped hook. `Stop` sends `status: "done"`; stale-row cleanup is left to the daemon/UI.
