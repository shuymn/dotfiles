export type CliExec = (
  command: string,
  args: string[],
  options: {
    signal?: AbortSignal;
    timeout: number;
    cwd?: string;
  },
) => Promise<{
  code: number;
  stdout: string;
  stderr: string;
}>;

export type CliExecOptions = {
  command: string;
  args: string[];
  timeout: number;
  signal?: AbortSignal;
  cwd?: string;
};

export type CliRawResult = {
  command: string[];
  exitCode: number;
  stdout: string;
  stderr: string;
};

export type CliRunOptions = CliExecOptions & {
  maxOutputChars?: number;
  parseJson?: boolean;
  failureHint?: string;
  successLabel?: string;
  failureLabel?: string;
  truncationLabel?: string;
};

export type CliRunResult = CliRawResult & {
  text: string;
  json?: unknown;
};

export type CliToolResult = {
  content: Array<{ type: "text"; text: string }>;
  details: Record<string, unknown>;
};

export function toCliExec(pi: { exec: CliExec }): CliExec {
  return (command, args, options) => pi.exec(command, args, options);
}

export async function execCli(
  exec: CliExec,
  options: CliExecOptions,
): Promise<CliRawResult> {
  const result = await exec(options.command, options.args, {
    signal: options.signal,
    timeout: options.timeout,
    cwd: options.cwd,
  });

  return {
    command: [options.command, ...options.args],
    exitCode: result.code ?? 0,
    stdout: result.stdout ?? "",
    stderr: result.stderr ?? "",
  };
}

export function parseJson(stdout: string): unknown | undefined {
  try {
    return JSON.parse(stdout);
  } catch {
    return undefined;
  }
}

export function truncateCliOutput(
  text: string,
  maxChars: number | undefined,
  label = "cli output",
): string {
  if (maxChars === undefined || text.length <= maxChars) return text;
  return `${text.slice(0, maxChars)}\n\n[truncated by ${label}: ${text.length - maxChars} chars omitted]`;
}

export function renderCliOutput(options: {
  command: string;
  exitCode: number;
  stdout: string;
  stderr: string;
  json?: unknown;
  maxOutputChars?: number;
  successLabel?: string;
  failureLabel?: string;
  truncationLabel?: string;
}): string {
  const body =
    options.json === undefined
      ? options.stdout.trim()
      : JSON.stringify(options.json, null, 2);
  const prefix =
    options.exitCode === 0
      ? `${options.successLabel ?? `${options.command} result`}:`
      : `${
          options.failureLabel ?? `${options.command} command failed`
        } with exit code ${options.exitCode}:`;
  const diagnostic = options.stderr.trim()
    ? `\n\nstderr:\n${options.stderr.trim()}`
    : "";
  const full = `${prefix}\n\n${body}${diagnostic}`.trim();
  return truncateCliOutput(
    full,
    options.maxOutputChars,
    options.truncationLabel ?? "cli output",
  );
}

export function errorWithHint(
  error: unknown,
  options: {
    failureHint?: string;
    maxOutputChars?: number;
    truncationLabel?: string;
  } = {},
): Error {
  const message = truncateCliOutput(
    error instanceof Error ? error.message : String(error),
    options.maxOutputChars,
    options.truncationLabel ?? "cli output",
  );
  return new Error(
    options.failureHint ? `${options.failureHint}\n\n${message}` : message,
    { cause: error },
  );
}

export async function runCli(
  exec: CliExec,
  options: CliRunOptions,
): Promise<CliRunResult> {
  let result: CliRawResult;
  try {
    result = await execCli(exec, options);
  } catch (error) {
    throw errorWithHint(error, {
      failureHint: options.failureHint,
      maxOutputChars: options.maxOutputChars,
      truncationLabel: options.truncationLabel,
    });
  }

  const json = options.parseJson ? parseJson(result.stdout) : undefined;
  const text = renderCliOutput({
    command: options.command,
    exitCode: result.exitCode,
    stdout: result.stdout,
    stderr: result.stderr,
    json,
    maxOutputChars: options.maxOutputChars,
    successLabel: options.successLabel,
    failureLabel: options.failureLabel,
    truncationLabel: options.truncationLabel,
  });

  if (result.exitCode !== 0) {
    throw errorWithHint(new Error(text), { failureHint: options.failureHint });
  }
  return { ...result, text, json };
}

export function cliResultForTool(result: CliRunResult): CliToolResult {
  const details: Record<string, unknown> = {
    command: result.command,
    exitCode: result.exitCode,
    stdout: result.stdout,
    stderr: result.stderr,
  };
  if (result.json !== undefined) details.json = result.json;

  return {
    content: [{ type: "text", text: result.text }],
    details,
  };
}
