import { describe, expect, test } from "bun:test";
import { parseCommandArgs } from "./command-args";

const FLAGS = ["--staged", "--cached", "--no-fix"] as const;

function parse(args: string) {
  return parseCommandArgs({ args, booleanFlags: FLAGS });
}

describe("parseCommandArgs", () => {
  test.each([
    {
      name: "empty args",
      args: "",
      files: [],
      flags: { "--staged": false, "--cached": false, "--no-fix": false },
      instructions: "",
    },
    {
      name: "files and flags before separator",
      args: "--no-fix @src/app.ts docs/readme.md",
      files: ["src/app.ts", "docs/readme.md"],
      flags: { "--staged": false, "--cached": false, "--no-fix": true },
      instructions: "",
    },
    {
      name: "separator at start",
      args: "-- focus on security",
      files: [],
      flags: { "--staged": false, "--cached": false, "--no-fix": false },
      instructions: "focus on security",
    },
    {
      name: "separator after file",
      args: "@src/app.ts -- focus on security",
      files: ["src/app.ts"],
      flags: { "--staged": false, "--cached": false, "--no-fix": false },
      instructions: "focus on security",
    },
    {
      name: "separator after mixed flags and files",
      args: "--no-fix @src/app.ts -- focus on security",
      files: ["src/app.ts"],
      flags: { "--staged": false, "--cached": false, "--no-fix": true },
      instructions: "focus on security",
    },
    {
      name: "separator at end",
      args: "@src/app.ts --",
      files: ["src/app.ts"],
      flags: { "--staged": false, "--cached": false, "--no-fix": false },
      instructions: "",
    },
    {
      name: "extra whitespace around instructions",
      args: "@src/app.ts --  focus on security  ",
      files: ["src/app.ts"],
      flags: { "--staged": false, "--cached": false, "--no-fix": false },
      instructions: "focus on security",
    },
    {
      name: "non-separator double dash remains a file",
      args: "@src/app.ts--not-separator",
      files: ["src/app.ts--not-separator"],
      flags: { "--staged": false, "--cached": false, "--no-fix": false },
      instructions: "",
    },
    {
      name: "flags after separator are instructions",
      args: "@src/app.ts -- --no-fix should be text",
      files: ["src/app.ts"],
      flags: { "--staged": false, "--cached": false, "--no-fix": false },
      instructions: "--no-fix should be text",
    },
    {
      name: "unknown dash token before separator is a file",
      args: "--unknown @src/app.ts",
      files: ["--unknown", "src/app.ts"],
      flags: { "--staged": false, "--cached": false, "--no-fix": false },
      instructions: "",
    },
  ])("$name", ({ args, files, flags, instructions }) => {
    const parsed = parse(args);

    expect(parsed.files).toEqual([...files]);
    expect(parsed.flags).toEqual(flags);
    expect(parsed.instructions).toBe(instructions);
  });
});
