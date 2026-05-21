import { execFile } from "node:child_process";
import { mkdtemp, realpath, rm, stat } from "node:fs/promises";
import { homedir, tmpdir } from "node:os";
import { basename, join, resolve } from "node:path";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { Type } from "typebox";

const STATE_TYPE = "add-dir-state";
const GITHUB_CLONE_PREFIX = "pi-github-workspace-";
const GITHUB_CLONE_TIMEOUT_MS = 30_000;

const SAFE_GITHUB_PART = /^[A-Za-z0-9_.-]+$/;
const SAFE_REF = /^[A-Za-z0-9._/-]+$/;
const SAFE_DIR_NAME = /^[A-Za-z0-9_.-]+$/;

type AddedDir = {
  name: string;
  path: string;
  temporary?: boolean;
  tempRoot?: string;
};

type ParsedGitHubUrl = {
  owner: string;
  repo: string;
  treeSegments?: string[];
};

type ResolvedGitHubTarget = {
  ref?: string;
  subPathSegments: string[];
};

function expandHome(path: string): string {
  if (path === "~") return homedir();
  if (path.startsWith("~/")) return resolve(homedir(), path.slice(2));
  return path;
}

async function resolveExistingDirectory(
  input: string,
  cwd: string,
): Promise<AddedDir> {
  const expanded = expandHome(input.trim());
  const absolute = resolve(cwd, expanded);
  const canonical = await realpath(absolute);
  const stats = await stat(canonical);

  if (!stats.isDirectory()) {
    throw new Error(`Not a directory: ${canonical}`);
  }

  return {
    name: basename(canonical),
    path: canonical,
  };
}

function isPathInside(parent: string, child: string): boolean {
  const parentWithSeparator = `${parent}/`;
  return child === parent || child.startsWith(parentWithSeparator);
}

function isAddedDir(value: unknown): value is AddedDir {
  return (
    typeof value === "object" &&
    value !== null &&
    typeof (value as AddedDir).name === "string" &&
    typeof (value as AddedDir).path === "string" &&
    ((value as AddedDir).temporary === undefined ||
      typeof (value as AddedDir).temporary === "boolean") &&
    ((value as AddedDir).tempRoot === undefined ||
      typeof (value as AddedDir).tempRoot === "string")
  );
}

function formatDirs(dirs: AddedDir[]): string {
  return dirs.map((dir) => `- ${dir.name}: ${dir.path}`).join("\n");
}

function parseGitHubRepoUrl(input: string): ParsedGitHubUrl {
  let url: URL;
  try {
    url = new URL(input);
  } catch {
    throw new Error(
      "github_clone_workspace only accepts full https://github.com/owner/repo URLs.",
    );
  }

  if (url.protocol !== "https:" || url.hostname !== "github.com") {
    throw new Error(
      "github_clone_workspace only accepts https://github.com URLs.",
    );
  }

  const segments = url.pathname
    .split("/")
    .filter(Boolean)
    .map((segment) => {
      try {
        return decodeURIComponent(segment);
      } catch {
        return segment;
      }
    });

  if (segments.length < 2) {
    throw new Error("GitHub URL must include owner and repository name.");
  }

  const owner = segments[0];
  const repo = segments[1].replace(/\.git$/, "");

  if (!SAFE_GITHUB_PART.test(owner) || !SAFE_GITHUB_PART.test(repo)) {
    throw new Error(
      "GitHub owner and repository name contain unsupported characters.",
    );
  }

  let treeSegments: string[] | undefined;
  const pathAction = segments[2];
  if (pathAction === "blob") {
    throw new Error(
      "GitHub blob URLs point to files and are not supported. Use the repository URL or a /tree/<ref>/<directory> URL instead.",
    );
  }

  if (pathAction === "tree") {
    treeSegments = segments.slice(3);
    if (treeSegments.length === 0) {
      throw new Error("GitHub tree URL must include a ref.");
    }
  } else if (pathAction !== undefined) {
    throw new Error(
      "Only GitHub repository and /tree/<ref>/... URLs are supported.",
    );
  }

  return { owner, repo, treeSegments };
}

function sanitizeDirectoryName(input: string): string {
  const name = input.trim();
  if (!name) throw new Error("Directory name must not be empty.");
  if (
    name === "." ||
    name === ".." ||
    name.includes("/") ||
    !SAFE_DIR_NAME.test(name)
  ) {
    throw new Error(
      "Directory name may only contain letters, numbers, '.', '_', and '-'.",
    );
  }
  return name;
}

function runGit(
  args: string[],
  signal?: AbortSignal,
  timeout = GITHUB_CLONE_TIMEOUT_MS,
): Promise<string> {
  return new Promise((resolvePromise, reject) => {
    const child = execFile(
      "git",
      args,
      {
        env: { ...process.env, GIT_TERMINAL_PROMPT: "0" },
        timeout,
      },
      (error, stdout, stderr) => {
        if (error) {
          const details = [stderr.trim(), stdout.trim()]
            .filter(Boolean)
            .join("\n");
          reject(new Error(details || error.message));
          return;
        }
        resolvePromise(stdout);
      },
    );

    if (signal) {
      const onAbort = () => child.kill();
      signal.addEventListener("abort", onAbort, { once: true });
      child.on("exit", () => signal.removeEventListener("abort", onAbort));
    }
  });
}

async function resolveGitHubTarget(
  repoUrl: string,
  parsed: ParsedGitHubUrl,
  signal?: AbortSignal,
): Promise<ResolvedGitHubTarget> {
  if (!parsed.treeSegments) return { subPathSegments: [] };

  const segments = parsed.treeSegments;
  const stdout = await runGit(
    ["ls-remote", "--heads", "--tags", repoUrl],
    signal,
  );
  const refs = new Set(
    stdout
      .split("\n")
      .map((line) => line.trim().split(/\s+/)[1])
      .filter((ref): ref is string => Boolean(ref))
      .flatMap((ref) => [
        ref.replace(/^refs\/heads\//, ""),
        ref.replace(/^refs\/tags\//, ""),
      ]),
  );

  for (let length = segments.length; length > 0; length -= 1) {
    const ref = segments.slice(0, length).join("/");
    if (!refs.has(ref)) continue;
    if (!SAFE_REF.test(ref)) {
      throw new Error("GitHub ref contains unsupported characters.");
    }
    return { ref, subPathSegments: segments.slice(length) };
  }

  throw new Error(
    "Could not resolve the GitHub tree URL ref. Use a repository URL or a URL with an existing branch or tag.",
  );
}

function cloneGitHubRepo(
  repoUrl: string,
  targetPath: string,
  ref: string | undefined,
  signal?: AbortSignal,
): Promise<void> {
  const args = [
    "clone",
    "--depth",
    "1",
    "--filter=blob:none",
    "--single-branch",
  ];
  if (ref) args.push("--branch", ref);
  args.push(repoUrl, targetPath);

  return runGit(args, signal).then(() => undefined);
}

function resolveSafeSubPath(root: string, subPathSegments: string[]): string {
  for (const segment of subPathSegments) {
    if (segment === "" || segment === "." || segment === "..") {
      throw new Error("GitHub URL path contains unsupported segments.");
    }
  }

  const path = resolve(root, ...subPathSegments);
  if (!isPathInside(root, path)) {
    throw new Error("GitHub URL path escapes the cloned repository.");
  }
  return path;
}

export default function (pi: ExtensionAPI) {
  let dirs: AddedDir[] = [];
  let tempRoots: string[] = [];

  function persist(nextDirs: AddedDir[]) {
    pi.appendEntry(STATE_TYPE, { dirs: nextDirs });
  }

  async function validateRestoredTemporaryDir(
    dir: AddedDir,
  ): Promise<AddedDir | undefined> {
    if (!dir.tempRoot) return undefined;

    try {
      const canonicalTempRoot = await realpath(dir.tempRoot);
      const canonicalTmpDir = await realpath(tmpdir());
      if (!basename(canonicalTempRoot).startsWith(GITHUB_CLONE_PREFIX)) {
        return undefined;
      }
      if (!isPathInside(canonicalTmpDir, canonicalTempRoot)) return undefined;

      const canonicalDirPath = await realpath(dir.path);
      if (!isPathInside(canonicalTempRoot, canonicalDirPath)) return undefined;

      return {
        ...dir,
        path: canonicalDirPath,
        tempRoot: canonicalTempRoot,
      };
    } catch {
      return undefined;
    }
  }

  async function addDirectory(
    input: string,
    cwd: string,
    metadata: Pick<AddedDir, "temporary" | "tempRoot"> = {},
    containmentRoot?: string,
  ): Promise<{ dir: AddedDir; alreadyAdded: boolean }> {
    const resolvedDir = await resolveExistingDirectory(input, cwd);
    if (containmentRoot && !isPathInside(containmentRoot, resolvedDir.path)) {
      throw new Error(
        `GitHub URL path resolves outside the cloned repository: ${resolvedDir.path}`,
      );
    }
    const dir: AddedDir = { ...resolvedDir, ...metadata };

    const samePath = dirs.find((existing) => existing.path === dir.path);
    if (samePath) {
      return { dir: samePath, alreadyAdded: true };
    }

    const sameName = dirs.find((existing) => existing.name === dir.name);
    if (sameName) {
      throw new Error(
        `Cannot add ${dir.path}: directory name "${dir.name}" is already registered for ${sameName.path}. Remove it first with /remove-dir ${dir.name}.`,
      );
    }

    const nextDirs = [...dirs, dir];
    persist(nextDirs);
    dirs = nextDirs;
    return { dir, alreadyAdded: false };
  }

  pi.on("session_start", async (_event, ctx) => {
    dirs = [];
    tempRoots = [];

    for (const entry of ctx.sessionManager.getEntries()) {
      if (entry.type !== "custom" || entry.customType !== STATE_TYPE) continue;

      const data = entry.data as { dirs?: unknown } | undefined;
      if (!Array.isArray(data?.dirs)) continue;

      dirs = data.dirs.filter(isAddedDir);
    }

    dirs = (
      await Promise.all(
        dirs.map(async (dir) => {
          try {
            const stats = await stat(dir.path);
            if (!stats.isDirectory()) return undefined;
            return dir.temporary ? validateRestoredTemporaryDir(dir) : dir;
          } catch {
            // Drop stale temporary paths from previous sessions.
            return dir.temporary ? undefined : dir;
          }
        }),
      )
    ).filter((dir): dir is AddedDir => dir !== undefined);
    tempRoots = dirs
      .filter((dir) => dir.temporary && dir.tempRoot)
      .map((dir) => dir.tempRoot as string);
  });

  pi.registerCommand("add-dir", {
    description: "Register an additional directory name for this session",
    handler: async (args, ctx) => {
      const input = args.trim();
      if (!input) {
        ctx.ui.notify("使い方: /add-dir <path>", "error");
        return;
      }

      try {
        const { dir, alreadyAdded } = await addDirectory(input, ctx.cwd);
        ctx.ui.notify(
          alreadyAdded
            ? `すでに登録済みです: ${dir.name}: ${dir.path}`
            : `ディレクトリを追加しました: ${dir.name}: ${dir.path}`,
          "info",
        );
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        ctx.ui.notify(message, "error");
      }
    },
  });

  pi.registerCommand("list-dir", {
    description: "List additional directories registered for this session",
    handler: async (_args, ctx) => {
      if (dirs.length === 0) {
        ctx.ui.notify("追加ディレクトリは登録されていません。", "info");
        return;
      }

      ctx.ui.notify(formatDirs(dirs), "info");
    },
  });

  pi.registerCommand("remove-dir", {
    description: "Remove an additional directory from this session",
    handler: async (args, ctx) => {
      const input = args.trim();
      if (!input) {
        ctx.ui.notify("使い方: /remove-dir <directory-name-or-path>", "error");
        return;
      }

      const expanded = expandHome(input);
      const resolved = resolve(ctx.cwd, expanded);
      const before = dirs.length;
      const nextDirs = dirs.filter(
        (dir) =>
          dir.name !== input && dir.path !== input && dir.path !== resolved,
      );

      if (nextDirs.length === before) {
        ctx.ui.notify(
          `一致する登録ディレクトリがありません: ${input}`,
          "error",
        );
        return;
      }

      persist(nextDirs);
      dirs = nextDirs;
      ctx.ui.notify(
        dirs.length === 0
          ? "ディレクトリを削除しました。追加ディレクトリはありません。"
          : `ディレクトリを削除しました。残り:\n${formatDirs(dirs)}`,
        "info",
      );
    },
  });

  pi.registerTool({
    name: "github_clone_workspace",
    label: "GitHub Clone Workspace",
    description:
      "Clone a public GitHub repository URL or GitHub /tree/<ref>/<directory> URL into a temporary directory and register it as an additional named directory for this session. GitHub /blob/ file URLs are not supported. Clones are shallow, blob-filtered, do not fetch submodules, time out after 30 seconds, and are removed when the session shuts down.",
    promptSnippet:
      "Clone a GitHub repository URL into a temporary workspace and register it as an additional directory.",
    promptGuidelines: [
      "Use github_clone_workspace when the user asks about code in a GitHub repository URL and local code inspection would help.",
      "After github_clone_workspace returns, use the returned absolute path with read, grep, find, ls, or bash to inspect the cloned repository.",
    ],
    parameters: Type.Object({
      url: Type.String({
        description:
          "A public https://github.com/owner/repo URL. /tree/<ref>/<directory> URLs are also accepted; the cloned workspace is registered at the referenced subdirectory when a path is present. /blob/ file URLs are not supported.",
      }),
      directoryName: Type.Optional(
        Type.String({
          description:
            "Optional clone directory name. Defaults to the repository name. For /tree/<ref>/<directory> URLs, the registered workspace name is the target directory basename. Must contain only letters, numbers, '.', '_', and '-'.",
        }),
      ),
    }),
    async execute(_toolCallId, params, signal, _onUpdate, ctx) {
      const parsed = parseGitHubRepoUrl(params.url);
      const directoryName = sanitizeDirectoryName(
        params.directoryName ?? parsed.repo,
      );
      const tempRoot = await mkdtemp(join(tmpdir(), GITHUB_CLONE_PREFIX));
      tempRoots = [...tempRoots, tempRoot];

      const displayUrl = `https://github.com/${parsed.owner}/${parsed.repo}`;
      const repoUrl = `${displayUrl}.git`;
      const clonePath = join(tempRoot, directoryName);

      try {
        const target = await resolveGitHubTarget(repoUrl, parsed, signal);
        await cloneGitHubRepo(repoUrl, clonePath, target.ref, signal);
        const canonicalClonePath = await realpath(clonePath);

        const registeredPath = resolveSafeSubPath(
          canonicalClonePath,
          target.subPathSegments,
        );
        const { dir, alreadyAdded } = await addDirectory(
          registeredPath,
          ctx.cwd,
          {
            temporary: true,
            tempRoot,
          },
          canonicalClonePath,
        );

        const lines = [
          alreadyAdded
            ? "GitHub workspace was already registered."
            : "Cloned and registered GitHub workspace.",
          "",
          `name: ${dir.name}`,
          `path: ${dir.path}`,
          `url: ${displayUrl}`,
        ];
        if (target.ref) lines.push(`ref: ${target.ref}`);
        if (target.subPathSegments.length > 0) {
          lines.push(`subPath: ${target.subPathSegments.join("/")}`);
        }
        lines.push(
          "",
          "Use the absolute path above when reading, searching, or running read-only commands in this repository.",
        );

        return {
          content: [{ type: "text", text: lines.join("\n") }],
          details: {
            name: dir.name,
            path: dir.path,
            url: displayUrl,
            ref: target.ref,
            subPath: target.subPathSegments.join("/") || undefined,
            tempRoot,
            alreadyAdded,
          },
        };
      } catch (error) {
        await rm(tempRoot, { recursive: true, force: true }).catch(
          () => undefined,
        );
        tempRoots = tempRoots.filter((path) => path !== tempRoot);
        throw error;
      }
    },
  });

  pi.on("session_shutdown", async (event) => {
    if (event.reason === "reload") return;

    const roots = [...new Set(tempRoots)];
    tempRoots = [];
    await Promise.all(
      roots.map((root) =>
        rm(root, { recursive: true, force: true }).catch(() => undefined),
      ),
    );
  });

  pi.on("before_agent_start", async (event) => {
    if (dirs.length === 0) return;

    const context = [
      "Additional directories registered by the user for this session:",
      formatDirs(dirs),
      "",
      "When the user refers to one of these directory names, interpret it as the corresponding absolute path.",
      "Use absolute paths when reading, searching, or editing files in these directories.",
    ].join("\n");

    return {
      systemPrompt: `${event.systemPrompt}\n\n${context}`,
    };
  });
}
