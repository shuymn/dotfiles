import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { stat, realpath } from "node:fs/promises";
import { basename, resolve } from "node:path";
import { homedir } from "node:os";

const STATE_TYPE = "add-dir-state";

type AddedDir = {
  name: string;
  path: string;
};

function expandHome(path: string): string {
  if (path === "~") return homedir();
  if (path.startsWith("~/")) return resolve(homedir(), path.slice(2));
  return path;
}

async function resolveExistingDirectory(input: string, cwd: string): Promise<AddedDir> {
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

function isAddedDir(value: unknown): value is AddedDir {
  return (
    typeof value === "object" &&
    value !== null &&
    typeof (value as AddedDir).name === "string" &&
    typeof (value as AddedDir).path === "string"
  );
}

function formatDirs(dirs: AddedDir[]): string {
  return dirs.map((dir) => `- ${dir.name}: ${dir.path}`).join("\n");
}

export default function (pi: ExtensionAPI) {
  let dirs: AddedDir[] = [];

  function persist() {
    pi.appendEntry(STATE_TYPE, { dirs });
  }

  pi.on("session_start", async (_event, ctx) => {
    dirs = [];

    for (const entry of ctx.sessionManager.getEntries()) {
      if (entry.type !== "custom" || entry.customType !== STATE_TYPE) continue;

      const data = entry.data as { dirs?: unknown } | undefined;
      if (!Array.isArray(data?.dirs)) continue;

      dirs = data.dirs.filter(isAddedDir);
    }
  });

  pi.registerCommand("add-dir", {
    description: "Register an additional directory name for this session",
    handler: async (args, ctx) => {
      const input = args.trim();
      if (!input) {
        ctx.ui.notify("Usage: /add-dir <path>", "error");
        return;
      }

      let dir: AddedDir;
      try {
        dir = await resolveExistingDirectory(input, ctx.cwd);
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        ctx.ui.notify(message, "error");
        return;
      }

      const samePath = dirs.find((existing) => existing.path === dir.path);
      if (samePath) {
        ctx.ui.notify(`Already registered: ${samePath.name}: ${samePath.path}`, "info");
        return;
      }

      const sameName = dirs.find((existing) => existing.name === dir.name);
      if (sameName) {
        ctx.ui.notify(
          `Cannot add ${dir.path}: directory name "${dir.name}" is already registered for ${sameName.path}. Remove it first with /remove-dir ${dir.name}.`,
          "error",
        );
        return;
      }

      dirs = [...dirs, dir];
      persist();
      ctx.ui.notify(`Added directory: ${dir.name}: ${dir.path}`, "info");
    },
  });

  pi.registerCommand("list-dir", {
    description: "List additional directories registered for this session",
    handler: async (_args, ctx) => {
      if (dirs.length === 0) {
        ctx.ui.notify("No additional directories registered.", "info");
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
        ctx.ui.notify("Usage: /remove-dir <directory-name-or-path>", "error");
        return;
      }

      const expanded = expandHome(input);
      const resolved = resolve(ctx.cwd, expanded);
      const before = dirs.length;
      dirs = dirs.filter((dir) => dir.name !== input && dir.path !== input && dir.path !== resolved);

      if (dirs.length === before) {
        ctx.ui.notify(`No registered directory matched: ${input}`, "error");
        return;
      }

      persist();
      ctx.ui.notify(dirs.length === 0 ? "Removed directory. No additional directories remain." : `Removed directory. Remaining:\n${formatDirs(dirs)}`, "info");
    },
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
