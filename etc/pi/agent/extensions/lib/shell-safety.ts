export type ShellSafetyDecision = "allow" | "deny" | "unknown";

export type ShellSafetyResult = {
  decision: ShellSafetyDecision;
  rationale: string;
};

const READ_ONLY_COMMANDS = new Set([
  "cat",
  "grep",
  "head",
  "ls",
  "rg",
  "tail",
  "wc",
]);

const MUTATING_COMMANDS = new Set([
  "chmod",
  "chown",
  "cp",
  "curl",
  "install",
  "mkdir",
  "mv",
  "nc",
  "rm",
  "scp",
  "ssh",
  "tee",
  "touch",
  "wget",
  "xattr",
]);

const READ_ONLY_GIT_SUBCOMMANDS = new Set([
  "diff",
  "grep",
  "log",
  "ls-files",
  "rev-parse",
  "show",
  "status",
]);

const MUTATING_GIT_SUBCOMMANDS = new Set([
  "add",
  "apply",
  "checkout",
  "cherry-pick",
  "clean",
  "commit",
  "merge",
  "rebase",
  "reset",
  "stash",
  "switch",
]);

const PACKAGE_MANAGER_COMMANDS = new Set([
  "bun",
  "cargo",
  "go",
  "npm",
  "pnpm",
  "pip",
  "pip3",
  "uv",
  "yarn",
]);

const INTERPRETER_COMMANDS = new Set([
  "bun",
  "deno",
  "node",
  "python",
  "python3",
  "ruby",
]);

const CHAIN_OPERATORS = new Set(["&&", "||"]);
const UNSUPPORTED_SHELL_TOKENS = new Set(["|", ";", "&", "(", ")"]);
const DANGEROUS_FIND_ACTIONS = new Set([
  "-delete",
  "-exec",
  "-execdir",
  "-ok",
  "-okdir",
  "-fprint",
  "-fprint0",
  "-fprintf",
  "-fls",
]);
const DANGEROUS_GIT_OPTIONS = new Set([
  "--ext-diff",
  "--external-diff",
  "--open-files-in-pager",
  "--output",
]);

export function classifyShellCommand(command: unknown): ShellSafetyResult {
  if (typeof command !== "string" || !command.trim()) {
    return deny("shell_command input must include a non-empty command string.");
  }

  if (hasUnsafeShellExpansion(command)) {
    return deny(
      "Shell command substitution or process substitution is not allowed in /review read-only phases.",
    );
  }

  const tokens = tokenizeShellCommand(command);
  if (!tokens.ok) return deny(tokens.reason);

  if (
    tokens.tokens.some(
      (token) => token.kind === "operator" && isRedirect(token.value),
    )
  ) {
    return deny(
      "Shell redirection is not allowed in /review read-only phases.",
    );
  }

  const mutatingWord = tokens.tokens.find(
    (token) =>
      token.kind === "word" && MUTATING_COMMANDS.has(basename(token.value)),
  );
  if (mutatingWord) {
    return deny(
      `${basename(mutatingWord.value)} is not allowed in /review read-only phases.`,
    );
  }

  if (
    tokens.tokens.some(
      (token) =>
        token.kind === "operator" && UNSUPPORTED_SHELL_TOKENS.has(token.value),
    )
  ) {
    return unknown(
      "Command uses shell operators that require reviewer evaluation.",
    );
  }

  const commands = splitCommands(tokens.tokens);
  if (!commands.ok) return deny(commands.reason);

  let sawCommand = false;
  for (const argv of commands.commands) {
    if (argv.length === 0) continue;
    sawCommand = true;
    const result = classifySimpleCommand(argv);
    if (result.decision !== "allow") return result;
  }

  return sawCommand
    ? allow("All command segments match conservative read-only rules.")
    : deny("No executable command was found.");
}

type ShellToken = {
  kind: "word" | "operator";
  value: string;
};

type TokenizeResult =
  | { ok: true; tokens: ShellToken[] }
  | { ok: false; reason: string };

function tokenizeShellCommand(command: string): TokenizeResult {
  const tokens: ShellToken[] = [];
  let current = "";
  let quote: "'" | '"' | undefined;

  const pushWord = () => {
    if (!current) return;
    tokens.push({ kind: "word", value: current });
    current = "";
  };

  for (let index = 0; index < command.length; index += 1) {
    const char = command[index];
    const next = command[index + 1];

    if (quote) {
      if (char === quote) {
        quote = undefined;
      } else {
        current += char;
      }
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

    if ((char === "&" && next === "&") || (char === "|" && next === "|")) {
      pushWord();
      tokens.push({ kind: "operator", value: `${char}${next}` });
      index += 1;
      continue;
    }

    if ((char === ">" && next === ">") || (char === "<" && next === "<")) {
      pushWord();
      tokens.push({ kind: "operator", value: `${char}${next}` });
      index += 1;
      continue;
    }

    if ("|;&()<>".includes(char)) {
      pushWord();
      tokens.push({ kind: "operator", value: char });
      continue;
    }

    current += char;
  }

  if (quote) return { ok: false, reason: "Unterminated shell quote." };
  pushWord();
  return { ok: true, tokens };
}

type SplitResult =
  | { ok: true; commands: string[][] }
  | { ok: false; reason: string };

function splitCommands(tokens: ShellToken[]): SplitResult {
  const commands: string[][] = [[]];

  for (const token of tokens) {
    if (token.kind === "operator") {
      if (!CHAIN_OPERATORS.has(token.value)) {
        return {
          ok: false,
          reason: `Unsupported shell operator: ${token.value}`,
        };
      }
      if (commands.at(-1)?.length === 0) {
        return {
          ok: false,
          reason: `Shell operator ${token.value} has no left-hand command.`,
        };
      }
      commands.push([]);
      continue;
    }
    commands.at(-1)?.push(token.value);
  }

  if (commands.at(-1)?.length === 0) {
    return { ok: false, reason: "Shell command ends with an operator." };
  }

  return { ok: true, commands };
}

function classifySimpleCommand(argv: string[]): ShellSafetyResult {
  const executable = basename(argv[0]);

  if (MUTATING_COMMANDS.has(executable)) {
    return deny(`${executable} is not allowed in /review read-only phases.`);
  }

  if (PACKAGE_MANAGER_COMMANDS.has(executable)) {
    return deny(`${executable} is not allowed in /review read-only phases.`);
  }

  if (INTERPRETER_COMMANDS.has(executable)) {
    return deny(
      `${executable} script execution is not allowed in /review read-only phases.`,
    );
  }

  if (executable === "sed") return classifySed(argv);
  if (executable === "git") return classifyGit(argv);
  if (executable === "find") return classifyFind(argv);

  if (READ_ONLY_COMMANDS.has(executable)) {
    return allow(`${executable} is treated as a read-only inspection command.`);
  }

  return unknown(
    `${executable} is not covered by static read-only shell rules.`,
  );
}

function classifySed(argv: string[]): ShellSafetyResult {
  if (argv.some((arg) => arg === "-i" || arg.startsWith("-i"))) {
    return deny(
      "sed in-place editing is not allowed in /review read-only phases.",
    );
  }
  if (
    !argv.some(
      (arg) => arg === "-n" || (arg.startsWith("-") && arg.includes("n")),
    )
  ) {
    return unknown(
      "sed without -n is not covered by static read-only shell rules.",
    );
  }
  if (sedScripts(argv).some((script) => hasUnsafeSedScript(script))) {
    return deny(
      "sed scripts that write files or execute commands are not allowed in /review read-only phases.",
    );
  }
  return allow("sed -n without in-place editing is read-only.");
}

function classifyGit(argv: string[]): ShellSafetyResult {
  const subcommand = argv.find(
    (arg, index) => index > 0 && !arg.startsWith("-"),
  );
  if (!subcommand) return unknown("git command has no subcommand to classify.");

  if (MUTATING_GIT_SUBCOMMANDS.has(subcommand)) {
    return deny(
      `git ${subcommand} is not allowed in /review read-only phases.`,
    );
  }

  if (READ_ONLY_GIT_SUBCOMMANDS.has(subcommand)) {
    const dangerousOption = argv.find((arg) => isDangerousGitOption(arg));
    if (dangerousOption) {
      return deny(
        `git ${subcommand} option ${dangerousOption} is not allowed in /review read-only phases.`,
      );
    }
    return allow(`git ${subcommand} is treated as read-only.`);
  }

  return unknown(
    `git ${subcommand} is not covered by static read-only shell rules.`,
  );
}

function classifyFind(argv: string[]): ShellSafetyResult {
  const dangerousAction = argv.find((arg) => DANGEROUS_FIND_ACTIONS.has(arg));
  if (dangerousAction) {
    return deny(
      `find action ${dangerousAction} is not allowed in /review read-only phases.`,
    );
  }
  return allow("find without mutating actions is treated as read-only.");
}

function hasUnsafeShellExpansion(command: string): boolean {
  return (
    command.includes("$(") ||
    command.includes("`") ||
    command.includes("<(") ||
    command.includes(">(")
  );
}

function isDangerousGitOption(arg: string): boolean {
  return (
    DANGEROUS_GIT_OPTIONS.has(arg) ||
    [...DANGEROUS_GIT_OPTIONS].some((option) => arg.startsWith(`${option}=`))
  );
}

function sedScripts(argv: string[]): string[] {
  const scripts: string[] = [];
  let foundScript = false;

  for (let index = 1; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === "-e" || arg === "--expression") {
      const script = argv[index + 1];
      if (script) scripts.push(script);
      index += 1;
      continue;
    }
    if (arg.startsWith("-e") && arg.length > 2) {
      scripts.push(arg.slice(2));
      continue;
    }
    if (arg === "-f" || arg === "--file" || arg.startsWith("--file=")) {
      scripts.push("f");
      if (arg === "-f" || arg === "--file") index += 1;
      continue;
    }
    if (arg.startsWith("-")) continue;
    if (!foundScript) {
      scripts.push(arg);
      foundScript = true;
    }
  }

  return scripts;
}

function hasUnsafeSedScript(script: string): boolean {
  return (
    script === "f" ||
    /(^|[;\n])\s*(?:[0-9,$]+)?[wWeE](\s|$)/.test(script) ||
    /s(.).*\1[we](\s|$)/.test(script)
  );
}

function basename(command: string): string {
  return command.split("/").filter(Boolean).at(-1) ?? command;
}

function isRedirect(token: string): boolean {
  return token === ">" || token === ">>" || token === "<" || token === "<<";
}

function allow(rationale: string): ShellSafetyResult {
  return { decision: "allow", rationale };
}

function deny(rationale: string): ShellSafetyResult {
  return { decision: "deny", rationale };
}

function unknown(rationale: string): ShellSafetyResult {
  return { decision: "unknown", rationale };
}
