import { realpath } from "node:fs/promises";
import { resolve } from "node:path";
import {
  createBashToolDefinition,
  defineTool,
  type ExtensionAPI,
  type ExtensionContext,
  type ToolRenderResultOptions,
} from "@earendil-works/pi-coding-agent";
import { Type } from "typebox";

import { applyPatch, parseApplyPatch } from "./apply-patch";
import { isPathInside } from "./path-utils";

const MANAGED_TOOLS = new Set([
  "shell_command",
  "apply_patch",
  "read",
  "bash",
  "edit",
  "write",
  "grep",
  "find",
  "ls",
]);

const SHELL_COMMAND_DESCRIPTION = `Runs a shell command and returns its output.
- Always set the \`workdir\` param when using the shell_command function. Do not use \`cd\` unless absolutely necessary.
- Prefer shell_command for command-line inspection, tests, builds, and local scripts.`;

const APPLY_PATCH_DESCRIPTION = `Apply Codex-style file patches without invoking a shell.

Patch envelope:
*** Begin Patch
[ one or more file sections ]
*** End Patch

Each file operation starts with one of:
*** Add File: <path>
*** Delete File: <path>
*** Update File: <path>

For updates, include one or more hunks. Each hunk starts with @@ and uses space-prefixed context lines, - removed lines, and + added lines. Paths must be relative to the workspace.`;

type ShellCommandInput = {
  command?: string;
  workdir?: string;
  cwd?: string;
  timeout_ms?: number;
  timeout?: number;
};

type BashToolDefinition = ReturnType<typeof createBashToolDefinition>;
type ToolUpdateHandler = Parameters<BashToolDefinition["execute"]>[3];
type RenderTheme = Parameters<NonNullable<BashToolDefinition["renderCall"]>>[1];
type RenderContext = {
  args: unknown;
  cwd: string;
  [key: string]: unknown;
};

function shellCommand(input: ShellCommandInput): string {
  return (input.command ?? "").trim();
}

function timeoutSeconds(input: ShellCommandInput): number | undefined {
  if (typeof input.timeout === "number") return input.timeout;
  if (typeof input.timeout_ms === "number") {
    return Math.max(1, Math.ceil(input.timeout_ms / 1000));
  }
  return undefined;
}

function toBashArgs(input: ShellCommandInput): {
  command: string;
  timeout?: number;
} {
  return { command: shellCommand(input), timeout: timeoutSeconds(input) };
}

function withRenderArgs(context: unknown, args: unknown): RenderContext {
  return { ...(context as RenderContext), args };
}

function createShellRenderDefinition(cwd: string): BashToolDefinition {
  return createBashToolDefinition(cwd);
}

function renderShellCall(
  args: ShellCommandInput,
  theme: RenderTheme,
  context: unknown,
) {
  const renderContext = context as RenderContext;
  const renderCall = createShellRenderDefinition(renderContext.cwd).renderCall;
  if (!renderCall) throw new Error("bash renderer is unavailable");
  const bashArgs = toBashArgs(args);
  return renderCall(
    bashArgs,
    theme,
    withRenderArgs(renderContext, bashArgs) as never,
  );
}

function renderShellResult(
  result: unknown,
  options: ToolRenderResultOptions,
  theme: RenderTheme,
  context: unknown,
) {
  const renderContext = context as RenderContext;
  const renderResult = createShellRenderDefinition(
    renderContext.cwd,
  ).renderResult;
  if (!renderResult) throw new Error("bash renderer is unavailable");
  const bashArgs = toBashArgs(renderContext.args as ShellCommandInput);
  return renderResult(
    result as Parameters<NonNullable<BashToolDefinition["renderResult"]>>[0],
    options,
    theme,
    withRenderArgs(renderContext, bashArgs) as never,
  );
}

async function resolveWorkdir(
  ctx: ExtensionContext,
  workdir: string | undefined,
): Promise<string | undefined> {
  if (!workdir) return undefined;
  const cwdRealPath = await realpath(ctx.cwd);
  const absolutePath = resolve(ctx.cwd, workdir);
  const workdirRealPath = await realpath(absolutePath);
  if (isPathInside(cwdRealPath, workdirRealPath)) return workdirRealPath;
  throw new Error(`Working directory escapes workspace: ${workdir}`);
}

async function runShellCommand(
  id: string,
  input: ShellCommandInput,
  signal: AbortSignal | undefined,
  onUpdate: ToolUpdateHandler,
  ctx: ExtensionContext,
) {
  const command = shellCommand(input);
  if (!command) throw new Error("Missing shell command");

  const workdir = await resolveWorkdir(ctx, input.workdir ?? input.cwd);
  const tool = createBashToolDefinition(
    ctx.cwd,
    workdir
      ? { spawnHook: (spawnContext) => ({ ...spawnContext, cwd: workdir }) }
      : undefined,
  );
  return tool.execute(
    id,
    { command, timeout: timeoutSeconds(input) },
    signal,
    onUpdate,
    ctx,
  );
}

function registerCodexTools(pi: ExtensionAPI): void {
  pi.registerTool(
    defineTool({
      name: "shell_command",
      label: "shell_command",
      description: SHELL_COMMAND_DESCRIPTION,
      promptSnippet: "Run shell commands using Codex's shell_command shape.",
      promptGuidelines: [
        "Use shell_command for command-line inspection, tests, builds, and local scripts.",
        "Always set shell_command workdir when the command should run outside the current working directory; avoid cd unless necessary.",
      ],
      parameters: Type.Object({
        command: Type.String({
          description:
            "The shell script to execute in the user's default shell.",
        }),
        workdir: Type.Optional(
          Type.String({
            description: "Working directory relative to the workspace.",
          }),
        ),
        cwd: Type.Optional(
          Type.String({
            description: "Working directory relative to the workspace.",
          }),
        ),
        timeout_ms: Type.Optional(
          Type.Number({ description: "Timeout in milliseconds." }),
        ),
        timeout: Type.Optional(
          Type.Number({ description: "Timeout in seconds." }),
        ),
      }),
      renderCall: renderShellCall,
      renderResult: renderShellResult,
      async execute(id, params, signal, onUpdate, ctx) {
        return runShellCommand(id, params, signal, onUpdate, ctx);
      },
    }),
  );

  pi.registerTool(
    defineTool({
      name: "apply_patch",
      label: "apply_patch",
      description: APPLY_PATCH_DESCRIPTION,
      promptSnippet:
        "Apply Codex-style file patches directly without shelling out.",
      promptGuidelines: [
        "Use apply_patch for file edits that fit Codex patch grammar.",
        "Keep apply_patch paths relative to the workspace; never use absolute paths or parent-directory traversal.",
      ],
      parameters: Type.Object({
        input: Type.String({
          description:
            "Complete patch text, from Begin Patch through End Patch.",
        }),
      }),
      prepareArguments(args) {
        if (typeof args === "string") return { input: args };
        if (!args || typeof args !== "object") return { input: "" };
        const record = args as Record<string, unknown>;
        const input = record.input ?? record.patch;
        return { input: typeof input === "string" ? input : "" };
      },
      executionMode: "sequential",
      async execute(_id, params, signal, _onUpdate, ctx) {
        const result = await applyPatch(ctx.cwd, params.input, signal);
        return {
          content: [{ type: "text", text: result.summary }],
          details: result,
        };
      },
    }),
  );
}

function sameTools(left: string[], right: string[]): boolean {
  return (
    left.length === right.length &&
    left.every((tool, index) => tool === right[index])
  );
}

function activateCodexTools(pi: ExtensionAPI): void {
  const activeTools = pi.getActiveTools();
  const preservedTools = activeTools.filter((tool) => !MANAGED_TOOLS.has(tool));
  const nextTools = [
    ...new Set([...preservedTools, "shell_command", "apply_patch"]),
  ];
  if (!sameTools(activeTools, nextTools)) pi.setActiveTools(nextTools);
}

export default function codexTools(pi: ExtensionAPI): void {
  registerCodexTools(pi);

  pi.on("session_start", () => {
    activateCodexTools(pi);
  });
}

export { applyPatch, parseApplyPatch };
