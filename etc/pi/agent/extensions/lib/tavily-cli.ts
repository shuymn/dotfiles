export type OptionValue = string | number | boolean | string[] | undefined;

export const TAVILY_CLI_TIMEOUT_GRACE_MS = 10_000;

export function addOption(args: string[], flag: string, value: OptionValue) {
  if (value === undefined || value === false) return;
  if (value === true) {
    args.push(flag);
    return;
  }
  const rendered = Array.isArray(value)
    ? value.filter(Boolean).join(",")
    : String(value);
  if (rendered.length > 0) args.push(flag, rendered);
}

export function addOptions(
  args: string[],
  options: readonly (readonly [flag: string, value: OptionValue])[],
) {
  for (const [flag, value] of options) addOption(args, flag, value);
}

export function cliTimeoutMs(
  timeoutSeconds: number | undefined,
  defaultSeconds: number,
) {
  return (
    (timeoutSeconds ?? defaultSeconds) * 1000 + TAVILY_CLI_TIMEOUT_GRACE_MS
  );
}
