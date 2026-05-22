import { mkdtemp, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import type {
  AgentToolResult,
  ExtensionAPI,
} from "@earendil-works/pi-coding-agent";
import { Type } from "typebox";
import { classifyShellCommand } from "./shell-safety";

export const WORKFLOW_TEMP_FILE_TOOL_NAME = "workflow_write_temp_file";

const BASE_WORKFLOW_ACTIVE_TOOLS = [
  "read",
  "grep",
  "find",
  "ls",
  "bash",
  "shell_command",
  "spawn_subagent",
] as const;

export type ToolPolicyWorkflowName = "commit" | "create-pr";

export type ToolCallGateResult = { block: true; reason: string } | undefined;

type TempFileToolDetails = { ok: boolean; path?: string };

const DESTRUCTIVE_GIT_PATTERNS = [
  /(^|[;&|]\s*)git\s+restore\b/,
  /(^|[;&|]\s*)git\s+reset\b/,
  /(^|[;&|]\s*)git\s+checkout\s+(?:--|-f\b)/,
  /(^|[;&|]\s*)git\s+switch\b[^\n;|&]*\s--discard-changes\b/,
  /(^|[;&|]\s*)git\s+clean\b/,
];

const CREATE_PR_ALLOWED_READ_PATTERNS = [
  /(^|&&|\|\|)\s*gh\s+pr\s+view\b[^;&|<>]*/g,
  /(^|&&|\|\|)\s*git\s+(?:branch|symbolic-ref|rev-list)\b[^;&|<>]*/g,
];

const COMMIT_DENIED_OPTIONS = new Set([
  "--amend",
  "--no-verify",
  "--all",
  "--allow-empty",
  "-a",
]);

const GIT_ADD_DENIED_ARGS = new Set([".", "-A", "--all", "-u", "--update"]);

const GIT_PUSH_DENIED_OPTIONS = new Set([
  "--all",
  "--delete",
  "--force",
  "--force-with-lease",
  "--mirror",
  "--tags",
]);

const GH_PR_CREATE_ALLOWED_OPTIONS = new Set([
  "--base",
  "--body-file",
  "--head",
  "--title",
]);

const GH_PR_EDIT_ALLOWED_OPTIONS = new Set(["--body-file", "--title"]);

export function getWorkflowActiveTools(
  _workflow: ToolPolicyWorkflowName,
): string[] {
  return [...BASE_WORKFLOW_ACTIVE_TOOLS, WORKFLOW_TEMP_FILE_TOOL_NAME];
}

export function applyWorkflowActiveTools(
  pi: ExtensionAPI,
  workflow: ToolPolicyWorkflowName,
): void {
  pi.setActiveTools(getWorkflowActiveTools(workflow));
}

export function registerWorkflowTempFileTool(
  pi: ExtensionAPI,
  workflow: ToolPolicyWorkflowName,
): void {
  pi.registerTool({
    name: WORKFLOW_TEMP_FILE_TOOL_NAME,
    label: "Write temp file",
    description:
      "Write generated workflow helper content to a new file under the OS temp directory. This never writes inside the workspace.",
    promptSnippet: `Use ${WORKFLOW_TEMP_FILE_TOOL_NAME} only during the ${workflow} workflow when a command needs a body file. It writes outside the workspace in a new temp directory.`,
    parameters: Type.Object({
      filename: Type.String({
        description:
          "Basename for the temp file. Directory separators are rejected.",
      }),
      content: Type.String({ description: "Full file content to write." }),
    }),
    async execute(
      _toolCallId,
      params,
    ): Promise<AgentToolResult<TempFileToolDetails>> {
      const filename = params.filename.trim();
      if (!filename || filename.includes("/") || filename.includes("\\")) {
        return {
          content: [
            {
              type: "text" as const,
              text: "Invalid filename: provide a basename without directory separators.",
            },
          ],
          details: { ok: false },
        };
      }

      const directory = await mkdtemp(join(tmpdir(), "pi-workflow-"));
      const path = join(directory, filename);
      await writeFile(path, params.content, "utf8");
      return {
        content: [{ type: "text" as const, text: `Wrote temp file: ${path}` }],
        details: { ok: true, path },
      };
    },
  });
}

export function evaluateWorkflowToolCall(
  workflow: ToolPolicyWorkflowName,
  event: { toolName?: string; input?: unknown },
): ToolCallGateResult {
  const toolName = event.toolName;
  if (!toolName) return block(workflow, "tool name is missing.");

  if (!getWorkflowActiveTools(workflow).includes(toolName)) {
    return block(workflow, `${toolName} is not allowed in this workflow.`);
  }

  if (toolName === "spawn_subagent") {
    if (event.input && typeof event.input === "object") {
      (event.input as { readOnly?: boolean }).readOnly = true;
    }
    return undefined;
  }

  if (toolName !== "bash" && toolName !== "shell_command") return undefined;

  const command = extractShellCommand(event.input);
  if (!command) return block(workflow, "shell command input is missing.");

  for (const pattern of DESTRUCTIVE_GIT_PATTERNS) {
    if (pattern.test(command)) {
      return block(
        workflow,
        "destructive git cleanup/reset commands are not allowed. Ask the user for explicit instructions instead.",
      );
    }
  }

  const readonly = classifyShellCommand(command);
  if (readonly.decision === "allow") return undefined;

  if (isAllowedWorkflowSideEffect(workflow, command)) return undefined;
  if (isAllowedWorkflowReadCommand(workflow, command)) return undefined;

  return block(workflow, `shell command is not allowed: ${readonly.rationale}`);
}

function isAllowedWorkflowReadCommand(
  workflow: ToolPolicyWorkflowName,
  command: string,
): boolean {
  if (workflow !== "create-pr") return false;
  return matchesAllowedSegments(
    command.trim(),
    CREATE_PR_ALLOWED_READ_PATTERNS,
  );
}

function extractShellCommand(input: unknown): string | undefined {
  if (!input || typeof input !== "object") return undefined;
  const record = input as Record<string, unknown>;
  return typeof record.command === "string" ? record.command : undefined;
}

function isAllowedWorkflowSideEffect(
  workflow: ToolPolicyWorkflowName,
  command: string,
): boolean {
  const normalized = command.trim();
  if (!hasOnlySupportedSideEffectShellSyntax(normalized)) return false;

  const segments = normalized
    .split(/&&|\|\|/)
    .map((segment) => segment.trim())
    .filter(Boolean);
  if (segments.length === 0) return false;

  return segments.every((segment) =>
    workflow === "commit"
      ? isAllowedCommitSideEffectSegment(segment)
      : isAllowedCreatePrSideEffectSegment(segment),
  );
}

function hasOnlySupportedSideEffectShellSyntax(command: string): boolean {
  return !/[`$<>;|&]/.test(command.replace(/&&|\|\|/g, ""));
}

function isAllowedCommitSideEffectSegment(segment: string): boolean {
  const argv = splitCommandWords(segment);
  if (argv.length < 2 || argv[0] !== "git") return false;
  const [, subcommand, ...args] = argv;

  if (subcommand === "add") {
    return args.length > 0 && args.every((arg) => !isDeniedGitAddArg(arg));
  }

  if (subcommand === "commit") {
    return args.length > 0 && args.every((arg) => !isDeniedGitCommitArg(arg));
  }

  if (subcommand === "switch") {
    return args[0] === "-c" && args.length >= 2;
  }

  if (subcommand === "apply") {
    return (
      (args.length >= 2 && args[0] === "--cached") ||
      (args.length >= 3 && args[0] === "--check" && args[1] === "--cached")
    );
  }

  return false;
}

function isAllowedCreatePrSideEffectSegment(segment: string): boolean {
  const argv = splitCommandWords(segment);
  if (argv.length < 2) return false;

  if (argv[0] === "git" && argv[1] === "push") {
    const args = argv.slice(2);
    return args.length > 0 && args.every((arg) => !isDeniedGitPushArg(arg));
  }

  if (argv[0] !== "gh" || argv[1] !== "pr") return false;
  if (argv[2] === "create") {
    return hasOnlyAllowedOptions(argv.slice(3), GH_PR_CREATE_ALLOWED_OPTIONS);
  }
  if (argv[2] === "edit") {
    return hasOnlyAllowedOptions(argv.slice(3), GH_PR_EDIT_ALLOWED_OPTIONS, {
      allowLeadingPositional: true,
    });
  }

  return false;
}

function isDeniedGitAddArg(arg: string): boolean {
  return GIT_ADD_DENIED_ARGS.has(arg) || arg.startsWith("--all=");
}

function isDeniedGitCommitArg(arg: string): boolean {
  return (
    COMMIT_DENIED_OPTIONS.has(arg) ||
    arg.startsWith("--all=") ||
    arg.startsWith("--amend=") ||
    arg.startsWith("--allow-empty=") ||
    (arg.startsWith("-a") && arg !== "--")
  );
}

function isDeniedGitPushArg(arg: string): boolean {
  const optionName = arg.includes("=") ? arg.slice(0, arg.indexOf("=")) : arg;
  return (
    GIT_PUSH_DENIED_OPTIONS.has(optionName) ||
    arg.includes(":") ||
    arg.startsWith("+")
  );
}

function hasOnlyAllowedOptions(
  args: string[],
  allowedOptions: Set<string>,
  options: { allowLeadingPositional?: boolean } = {},
): boolean {
  let index = 0;
  if (
    options.allowLeadingPositional &&
    args[index] &&
    !args[index].startsWith("-")
  ) {
    index += 1;
  }

  while (index < args.length) {
    const arg = args[index];
    if (!arg.startsWith("--")) return false;
    const optionName = arg.includes("=") ? arg.slice(0, arg.indexOf("=")) : arg;
    if (!allowedOptions.has(optionName)) return false;
    if (!arg.includes("=")) {
      const value = args[index + 1];
      if (!value || value.startsWith("--")) return false;
      index += 1;
    }
    index += 1;
  }

  return args.length > 0;
}

function splitCommandWords(command: string): string[] {
  const words: string[] = [];
  let current = "";
  let quote: "'" | '"' | undefined;

  const pushWord = () => {
    if (!current) return;
    words.push(current);
    current = "";
  };

  for (let index = 0; index < command.length; index += 1) {
    const char = command[index];
    if (quote) {
      if (char === quote) quote = undefined;
      else current += char;
      continue;
    }
    if (char === "'" || char === '"') {
      quote = char;
      continue;
    }
    if (/\s/.test(char)) {
      pushWord();
      continue;
    }
    current += char;
  }

  if (quote) return [];
  pushWord();
  return words;
}

function matchesAllowedSegments(command: string, patterns: RegExp[]): boolean {
  if (/[`$<>;|&]/.test(command.replace(/&&|\|\|/g, ""))) return false;
  let remaining = command;
  for (const pattern of patterns) {
    remaining = remaining.replace(pattern, " ");
  }
  return remaining
    .split(/&&|\|\|/)
    .every((segment) => segment.trim().length === 0);
}

function block(workflow: ToolPolicyWorkflowName, reason: string) {
  return {
    block: true as const,
    reason: `/${workflow} extension によりブロックしました: ${reason}`,
  };
}
