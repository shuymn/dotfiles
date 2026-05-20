import { mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import {
  type ExtensionAPI,
  type ExtensionContext,
  SettingsManager,
} from "@earendil-works/pi-coding-agent";

const PACKAGE_NAME = "@earendil-works/pi-coding-agent";
const REGISTRY_URL = "https://npm.flatt.tech";
const PACKAGE_METADATA_URL = `${REGISTRY_URL}/${PACKAGE_NAME.replace("/", "%2F")}/latest`;
const METADATA_TIMEOUT_MS = 10_000;
const AUDIT_TIMEOUT_MS = 120_000;
const UPDATE_TIMEOUT_MS = 120_000;
const AUDIT_LEVEL = "low";
const UPDATE_FLAG = "update";

type NotifyType = "info" | "error" | "success" | "warning";
type UpdateContext = Pick<ExtensionContext, "hasUI" | "ui" | "shutdown">;

type UpdateStep =
  | "version check"
  | "audit"
  | "install"
  | "post-install version check";

let quietStartupPatched = false;

function hasUpdateFlagArg(): boolean {
  return process.argv.includes(`--${UPDATE_FLAG}`);
}

function silenceStartupListingsForUpdateFlag() {
  if (quietStartupPatched || !hasUpdateFlagArg()) return;

  const originalGetQuietStartup = SettingsManager.prototype.getQuietStartup;
  SettingsManager.prototype.getQuietStartup =
    function getQuietStartupForUpdateFlag() {
      if (hasUpdateFlagArg()) return true;
      return originalGetQuietStartup.call(this);
    };
  quietStartupPatched = true;
}

function notify(
  ctx: Pick<ExtensionContext, "hasUI" | "ui">,
  message: string,
  type: NotifyType = "info",
) {
  if (ctx.hasUI) {
    ctx.ui.notify(message, type === "success" ? "info" : type);
    return;
  }

  const stream = type === "error" ? console.error : console.log;
  stream(message);
}

async function exec(
  pi: ExtensionAPI,
  command: string,
  args: string[],
  timeout = 10_000,
  cwd?: string,
) {
  try {
    return await pi.exec(command, args, { timeout, cwd });
  } catch (error) {
    return {
      stdout: "",
      stderr: error instanceof Error ? error.message : String(error),
      code: 1,
    };
  }
}

async function getPiVersion(pi: ExtensionAPI): Promise<string | undefined> {
  const result = await exec(pi, "pi", ["--version"]);
  if (result.code !== 0) return undefined;

  const output = `${result.stdout}\n${result.stderr}`.trim();
  const match = output.match(/\b\d+\.\d+\.\d+(?:[-+][^\s]+)?\b/);
  return match?.[0] ?? output.split("\n")[0]?.trim();
}

async function getLatestVersion(): Promise<string> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), METADATA_TIMEOUT_MS);

  try {
    const response = await fetch(PACKAGE_METADATA_URL, {
      signal: controller.signal,
    });
    if (!response.ok)
      throw new Error(`npm registry returned ${response.status}`);

    const metadata = (await response.json()) as { version?: unknown };
    if (
      typeof metadata.version !== "string" ||
      metadata.version.trim() === ""
    ) {
      throw new Error("npm registry response did not include a version");
    }

    return metadata.version;
  } catch (error) {
    if (error instanceof Error && error.name === "AbortError") {
      throw new Error(
        `npm registry request to ${PACKAGE_METADATA_URL} timed out after ${METADATA_TIMEOUT_MS}ms`,
      );
    }
    throw error;
  } finally {
    clearTimeout(timeout);
  }
}

function summarize(result: Awaited<ReturnType<typeof exec>>): string {
  return (
    [result.stdout.trim(), result.stderr.trim()].filter(Boolean).join("\n") ||
    `Command exited with code ${result.code}`
  );
}

function formatSuccessSummary(details: {
  beforeVersion?: string;
  afterVersion?: string;
  pinnedPackage: string;
  registryUrl: string;
}): string {
  const versionLine =
    details.beforeVersion && details.afterVersion
      ? `${details.beforeVersion} -> ${details.afterVersion}`
      : (details.afterVersion ?? "unknown");

  return [
    "pi update completed",
    `Package: ${details.pinnedPackage}`,
    `Registry: ${details.registryUrl}`,
    `Audit: passed (bun audit --audit-level=${AUDIT_LEVEL})`,
    `Version: ${versionLine}`,
    "Next: restart pi to use the updated runtime everywhere.",
  ].join("\n");
}

function formatAlreadyCurrentSummary(details: {
  currentVersion: string;
  pinnedPackage: string;
  registryUrl: string;
}): string {
  return [
    "pi is already up to date",
    `Package: ${details.pinnedPackage}`,
    `Registry: ${details.registryUrl}`,
    `Version: ${details.currentVersion}`,
    "Action: skipped audit and install.",
  ].join("\n");
}

function formatFailureSummary(step: UpdateStep, error: unknown): string {
  const message = error instanceof Error ? error.message : String(error);

  return [
    "pi update failed",
    `Step: ${step}`,
    `Registry: ${REGISTRY_URL}`,
    "Details:",
    message,
  ].join("\n");
}

async function auditPinnedPackage(
  pi: ExtensionAPI,
  version: string,
): Promise<void> {
  const auditDir = await mkdtemp(join(tmpdir(), "pi-update-audit-"));

  try {
    await writeFile(
      join(auditDir, "package.json"),
      JSON.stringify(
        {
          private: true,
          dependencies: { [PACKAGE_NAME]: version },
        },
        null,
        2,
      ),
    );

    await writeFile(join(auditDir, ".npmrc"), `registry=${REGISTRY_URL}\n`);

    const lockfile = await exec(
      pi,
      "bun",
      [
        "install",
        "--lockfile-only",
        "--ignore-scripts",
        "--no-progress",
        `--registry=${REGISTRY_URL}`,
      ],
      AUDIT_TIMEOUT_MS,
      auditDir,
    );
    if (lockfile.code !== 0)
      throw new Error(`Audit setup failed:\n${summarize(lockfile)}`);

    const audit = await exec(
      pi,
      "bun",
      ["audit", `--audit-level=${AUDIT_LEVEL}`],
      AUDIT_TIMEOUT_MS,
      auditDir,
    );
    if (audit.code !== 0) throw new Error(`Audit failed:\n${summarize(audit)}`);
  } finally {
    await rm(auditDir, { recursive: true, force: true }).catch(() => undefined);
  }
}

async function updatePi(
  pi: ExtensionAPI,
  ctx: UpdateContext,
  options: { shutdownWhenDone?: boolean } = {},
) {
  let step: UpdateStep = "version check";

  try {
    notify(
      ctx,
      `Checking latest ${PACKAGE_NAME} version from ${REGISTRY_URL}...`,
    );
    const [beforeVersion, latestVersion] = await Promise.all([
      getPiVersion(pi),
      getLatestVersion(),
    ]);
    const pinnedPackage = `${PACKAGE_NAME}@${latestVersion}`;

    if (beforeVersion === latestVersion) {
      notify(
        ctx,
        formatAlreadyCurrentSummary({
          currentVersion: beforeVersion,
          pinnedPackage,
          registryUrl: REGISTRY_URL,
        }),
        "success",
      );
      return;
    }

    step = "audit";
    notify(ctx, `Auditing ${pinnedPackage}...`);
    await auditPinnedPackage(pi, latestVersion);

    step = "install";
    notify(ctx, `Installing ${pinnedPackage} with bun...`);
    const result = await exec(
      pi,
      "bun",
      [
        "install",
        "-g",
        pinnedPackage,
        `--registry=${REGISTRY_URL}`,
        "--ignore-scripts",
      ],
      UPDATE_TIMEOUT_MS,
    );
    if (result.code !== 0) throw new Error(summarize(result));

    step = "post-install version check";
    const afterVersion = await getPiVersion(pi);
    notify(
      ctx,
      formatSuccessSummary({
        beforeVersion,
        afterVersion,
        pinnedPackage,
        registryUrl: REGISTRY_URL,
      }),
      "success",
    );
  } catch (error) {
    notify(ctx, formatFailureSummary(step, error), "error");
  } finally {
    if (options.shutdownWhenDone) ctx.shutdown();
  }
}

export default function updateExtension(pi: ExtensionAPI) {
  let startupUpdateLaunched = false;

  silenceStartupListingsForUpdateFlag();

  pi.registerFlag(UPDATE_FLAG, {
    description: "Update pi with bun and exit",
    type: "boolean",
    default: false,
  });

  pi.on("session_start", async (event, ctx) => {
    if (
      event.reason !== "startup" ||
      startupUpdateLaunched ||
      pi.getFlag(UPDATE_FLAG) !== true
    )
      return;

    startupUpdateLaunched = true;
    await updatePi(pi, ctx, { shutdownWhenDone: true });
  });
}
