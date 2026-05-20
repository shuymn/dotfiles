import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { truncateToWidth } from "@earendil-works/pi-tui";

const ICON_BRANCH = "";
const SEP = " | ";

function rgb(r: number, g: number, b: number, text: string): string {
  return `\x1b[38;2;${r};${g};${b}m${text}\x1b[0m`;
}

function bold(text: string): string {
  return `\x1b[1m${text}\x1b[0m`;
}

function gradient(pct: number, mid = 50): string {
  const clamped = Math.max(0, Math.min(100, Math.round(pct)));
  if (clamped < mid) {
    const r = Math.round((clamped * 255) / mid);
    return `\x1b[38;2;${r};200;80m`;
  }
  const range = Math.max(1, 100 - mid);
  const g = Math.max(0, Math.round(200 - ((clamped - mid) * 200) / range));
  return `\x1b[38;2;255;${g};60m`;
}

function dot(pct: number, cap = 100, mid = 50): string {
  const rounded = Math.max(0, Math.round(pct));
  const scaled = Math.min(100, (rounded * 100) / cap);
  const scaledMid = (mid * 100) / cap;
  return `${gradient(scaled, scaledMid)}●\x1b[0m ${bold(`${rounded}%`)}`;
}

function basename(path: string): string {
  const trimmed = path.replace(/\/+$/, "");
  return trimmed.split("/").pop() || trimmed || "/";
}

type ModelLike = {
  name?: unknown;
  displayName?: unknown;
  id?: unknown;
  provider?: unknown;
};

function modelBaseName(model: unknown): string {
  if (!model || typeof model !== "object") return "no model";
  const m = model as ModelLike;
  return typeof m.name === "string"
    ? m.name
    : typeof m.displayName === "string"
      ? m.displayName
      : typeof m.id === "string"
        ? m.id
        : "model";
}

function modelName(
  model: unknown,
  ambiguousModelNames: ReadonlySet<string>,
): string {
  const name = modelBaseName(model);
  if (!model || typeof model !== "object" || !ambiguousModelNames.has(name))
    return name;

  const provider = (model as ModelLike).provider;
  return typeof provider === "string" ? `${provider}/${name}` : name;
}

function contextWindow(model: unknown): number | undefined {
  if (!model || typeof model !== "object") return undefined;
  const value = (model as { contextWindow?: unknown }).contextWindow;
  return typeof value === "number" && Number.isFinite(value) && value > 0
    ? value
    : undefined;
}

function formatTime(date: Date): string {
  return date.toLocaleTimeString("ja-JP", { hour12: false });
}

export default function (pi: ExtensionAPI) {
  let projectName = "";
  let lastReadyTime = formatTime(new Date());
  let requestFooterRender: (() => void) | undefined;
  let ambiguousModelNames = new Set<string>();

  pi.on("session_start", async (_event, ctx) => {
    if (!ctx.hasUI) return;

    const root = await pi
      .exec("git", ["rev-parse", "--show-toplevel"], { timeout: 1000 })
      .catch(() => undefined);
    const rootPath = root?.code === 0 ? root.stdout.trim() : "";
    projectName = basename(rootPath || ctx.cwd);

    const modelNameCounts = new Map<string, number>();
    for (const model of ctx.modelRegistry.getAvailable()) {
      const name = modelBaseName(model);
      modelNameCounts.set(name, (modelNameCounts.get(name) ?? 0) + 1);
    }
    ambiguousModelNames = new Set(
      [...modelNameCounts]
        .filter(([, count]) => count > 1)
        .map(([name]) => name),
    );

    ctx.ui.setFooter((tui, _theme, footerData) => {
      requestFooterRender = () => tui.requestRender();
      const disposeBranchListener = footerData.onBranchChange(() =>
        tui.requestRender(),
      );

      return {
        invalidate() {},
        render(width: number): string[] {
          const parts: string[] = [
            rgb(255, 200, 60, lastReadyTime),
            rgb(80, 220, 255, projectName),
          ];

          const branch = footerData.getGitBranch();
          if (branch) {
            parts[parts.length - 1] +=
              ` on ${rgb(220, 120, 255, `${ICON_BRANCH} ${branch}`)}`;
          }

          const effort = pi.getThinkingLevel();
          parts[parts.length - 1] +=
            ` via ${rgb(255, 80, 80, `${modelName(ctx.model, ambiguousModelNames)} • ${effort}`)}`;

          const usage = ctx.getContextUsage();
          const window = contextWindow(ctx.model);
          if (usage && window && typeof usage.tokens === "number") {
            parts.push(`ctx ${dot((usage.tokens / window) * 100, 80, 30)}`);
          }

          return [truncateToWidth(parts.join(SEP), width, "")];
        },
        dispose() {
          requestFooterRender = undefined;
          disposeBranchListener();
        },
      };
    });
  });

  pi.on("agent_end", async () => {
    lastReadyTime = formatTime(new Date());
    requestFooterRender?.();
  });

  pi.on("model_select", async () => {
    requestFooterRender?.();
  });

  pi.on("thinking_level_select", async () => {
    requestFooterRender?.();
  });
}
