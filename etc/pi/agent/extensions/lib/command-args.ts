import { normalizeFileArg } from "./git";

export type CommandArgParseOptions<TFlag extends string> = {
  readonly args: string;
  readonly booleanFlags: readonly TFlag[];
};

export type ParsedCommandArgs<TFlag extends string> = {
  readonly files: string[];
  readonly flags: Record<TFlag, boolean>;
  readonly instructions: string;
};

export function parseCommandArgs<TFlag extends string>({
  args,
  booleanFlags,
}: CommandArgParseOptions<TFlag>): ParsedCommandArgs<TFlag> {
  const separatorMatch = /(?:^|\s)--(?:\s|$)/.exec(args);
  const optionText = separatorMatch
    ? args.slice(0, separatorMatch.index).trim()
    : args.trim();
  const instructions = separatorMatch
    ? args.slice(separatorMatch.index + separatorMatch[0].length).trim()
    : "";

  const files: string[] = [];
  const flags = Object.fromEntries(
    booleanFlags.map((flag) => [flag, false]),
  ) as Record<TFlag, boolean>;
  const flagSet = new Set<string>(booleanFlags);

  for (const token of optionText.split(/\s+/).filter(Boolean)) {
    if (flagSet.has(token)) {
      flags[token as TFlag] = true;
    } else {
      files.push(normalizeFileArg(token));
    }
  }

  return { files, flags, instructions };
}
