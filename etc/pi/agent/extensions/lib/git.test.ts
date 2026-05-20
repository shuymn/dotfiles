import { describe, expect, test } from "bun:test";
import {
  collectChangedTargets,
  type ExecGit,
  formatJsonTarget,
  formatPlainTarget,
  isExplicitFileMode,
  normalizeFileArg,
  parseNameStatus,
  shellQuote,
  targetPathsForDiff,
  truncate,
  uniqueTargets,
} from "./git";

describe("git helpers", () => {
  test("normalizes agent file mentions", () => {
    expect(normalizeFileArg("@src/app.ts")).toBe("src/app.ts");
    expect(normalizeFileArg("docs/readme.md")).toBe("docs/readme.md");
  });

  test("parses name-status output and can preserve rename old paths", () => {
    const stdout = "M\0src/app.ts\0R100\0old.ts\0new.ts\0";

    expect(parseNameStatus(stdout, "diff", { preserveOldPath: true })).toEqual([
      { path: "src/app.ts", status: "M", source: "diff" },
      { path: "new.ts", oldPath: "old.ts", status: "R100", source: "diff" },
    ]);
    expect(parseNameStatus(stdout, "diff", { preserveOldPath: false })).toEqual(
      [
        { path: "src/app.ts", status: "M", source: "diff" },
        { path: "new.ts", status: "R100", source: "diff" },
      ],
    );
  });

  test("dedupes by current path and detects explicit-file mode", () => {
    const targets = uniqueTargets([
      { path: "src/app.ts", status: "M", source: "diff" },
      { path: "src/app.ts", status: "A", source: "diff" },
      { path: "docs/readme.md", status: "explicit", source: "explicit" },
    ]);

    expect(targets).toEqual([
      { path: "src/app.ts", status: "M", source: "diff" },
      { path: "docs/readme.md", status: "explicit", source: "explicit" },
    ]);
    expect(isExplicitFileMode(targets)).toBe(false);
    expect(
      isExplicitFileMode([
        { path: "src/app.ts", status: "explicit", source: "explicit" },
      ]),
    ).toBe(true);
  });

  test("formats targets for review and simplify prompts", () => {
    expect(
      formatJsonTarget({
        path: "new.ts",
        oldPath: "old.ts",
        status: "R100",
        source: "diff",
      }),
    ).toBe('- "old.ts" -> "new.ts" (R100; diff)');
    expect(
      formatPlainTarget({ path: "new.ts", status: "R100", source: "diff" }),
    ).toBe("- new.ts (R100; diff)");
  });

  test("shell quotes and truncates with existing message", () => {
    expect(shellQuote("a'b.ts")).toBe("'a'\\''b.ts'");
    expect(truncate("abcdef", 3)).toBe(
      "abc\n\n[diff truncated at 3 chars; inspect files directly before editing]",
    );
  });

  test("collects explicit targets without calling git", async () => {
    const calls: string[][] = [];
    const execGit: ExecGit = async (args) => {
      calls.push(args);
      return { code: 0, stdout: "", stderr: "" };
    };

    await expect(
      collectChangedTargets(execGit, {
        files: ["@src/app.ts", "docs/readme.md"],
        staged: true,
      }),
    ).resolves.toEqual([
      { path: "src/app.ts", status: "explicit", source: "explicit" },
      { path: "docs/readme.md", status: "explicit", source: "explicit" },
    ]);
    expect(calls).toEqual([]);
  });

  test("collects staged targets only", async () => {
    const calls: string[][] = [];
    const execGit: ExecGit = async (args) => {
      calls.push(args);
      if (args.join(" ") === "diff --cached --name-status -z") {
        return { code: 0, stdout: "A\0staged.ts\0", stderr: "" };
      }
      return { code: 1, stdout: "", stderr: "unexpected" };
    };

    await expect(
      collectChangedTargets(execGit, { files: [], staged: true }),
    ).resolves.toEqual([{ path: "staged.ts", status: "A", source: "diff" }]);
    expect(calls).toEqual([["diff", "--cached", "--name-status", "-z"]]);
  });

  test("collects unstaged, staged, renamed, and untracked targets", async () => {
    const execGit: ExecGit = async (args) => {
      const key = args.join(" ");
      if (key === "diff --name-status -z") {
        return {
          code: 0,
          stdout: "M\0src/app.ts\0R100\0old.ts\0new.ts\0",
          stderr: "",
        };
      }
      if (key === "diff --cached --name-status -z") {
        return { code: 0, stdout: "A\0src/staged.ts\0", stderr: "" };
      }
      if (key === "ls-files --others --exclude-standard -z") {
        return { code: 0, stdout: "notes.txt\0", stderr: "" };
      }
      return { code: 1, stdout: "", stderr: "unexpected" };
    };

    await expect(
      collectChangedTargets(execGit, {
        files: [],
        staged: false,
        preserveOldPath: true,
      }),
    ).resolves.toEqual([
      { path: "src/app.ts", status: "M", source: "diff" },
      { path: "new.ts", oldPath: "old.ts", status: "R100", source: "diff" },
      { path: "src/staged.ts", status: "A", source: "diff" },
      { path: "notes.txt", status: "untracked", source: "diff" },
    ]);
  });

  test("returns current and old paths for tracked diffs", () => {
    expect(
      targetPathsForDiff([
        { path: "src/app.ts", status: "M", source: "diff" },
        { path: "new.ts", oldPath: "old.ts", status: "R100", source: "diff" },
        { path: "notes.txt", status: "untracked", source: "diff" },
      ]),
    ).toEqual(["src/app.ts", "old.ts", "new.ts"]);
  });
});
