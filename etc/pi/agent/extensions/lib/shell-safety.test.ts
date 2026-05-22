import { describe, expect, test } from "bun:test";

import { classifyShellCommand } from "./shell-safety";

describe("classifyShellCommand", () => {
  test.each([
    "sed -n '1,120p' review/index.ts",
    "git status --short -- review/index.ts",
    "git diff -- review/index.ts",
    "git show HEAD:review/index.ts",
    "git log --oneline -- review/index.ts",
    "git rev-parse --show-toplevel",
    "git ls-files -- review/index.ts",
    "git grep classifyShellCommand",
    "cat review/index.ts",
    "head -40 review/index.ts",
    "tail -20 review/index.ts",
    "wc -l review/index.ts",
    "ls -la review",
    "find review -maxdepth 1 -type f",
    "grep -R shell_command review",
    "rg shell_command review",
    "git status --short -- review/index.ts && git diff -- review/index.ts",
  ])("allows statically read-only command: %s", (command) => {
    expect(classifyShellCommand(command)).toMatchObject({
      decision: "allow",
    });
  });

  test.each([
    "sed -i 's/a/b/' review/index.ts",
    "rm -rf review",
    "mv a b",
    "cp a b",
    "install src dest",
    "mkdir tmp",
    "touch file",
    "chmod 600 file",
    "chown user file",
    "xattr -d attr file",
    "git checkout -- review/index.ts",
    "git switch main",
    "git reset --hard",
    "git clean -fd",
    "git add review/index.ts",
    "git commit -m change",
    "git stash",
    "git rebase main",
    "git merge feature",
    "git cherry-pick abc123",
    "git apply patch.diff",
    "npm install",
    "bun install",
    "pip install package",
    "python script.py",
    "node script.js",
    "bun run build",
    "cat review/index.ts > out.txt",
    "cat review/index.ts >> out.txt",
    "cat review/index.ts | tee out.txt",
    "cat $(touch out.txt)",
    'cat "$(touch out.txt)"',
    "cat `touch out.txt`",
    "find review -delete",
    "find review -exec rm -f {} ;",
    "find review -execdir sh -c 'rm -f \"$1\"' sh {} +",
    "find review -fprint out.txt",
    "find review -fprintf out.txt '%p\\n'",
    "find review -fls out.txt",
    "git diff --output=out.patch",
    "git diff --ext-diff",
    "git show --output out.txt HEAD",
    "git log --ext-diff -p",
    "git grep --open-files-in-pager='sh -c touch out' pattern",
    "sed -n '1w out.txt' file",
    "sed -n '1e touch out.txt' file",
    "sed -n 's/foo/bar/w out.txt' file",
    "sed -n -f script.sed file",
    "curl https://example.com",
    "wget https://example.com",
    "ssh host",
    "scp a host:b",
    "nc -l 1234",
  ])("denies statically unsafe command: %s", (command) => {
    expect(classifyShellCommand(command).decision).toBe("deny");
  });

  test.each([
    "awk '{print $1}' file",
    "sed '1,3p' file",
    "git branch",
    "cat file | grep x",
    "unknown-tool --flag",
  ])("returns unknown when static rules are inconclusive: %s", (command) => {
    expect(classifyShellCommand(command).decision).toBe("unknown");
  });

  test("denies empty and malformed commands", () => {
    expect(classifyShellCommand("").decision).toBe("deny");
    expect(classifyShellCommand("sed -n '1,3p file").decision).toBe("deny");
  });
});
