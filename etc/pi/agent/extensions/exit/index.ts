import { writeSync } from "node:fs";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

const PI_COMMAND = process.env.PI_RESUME_COMMAND ?? "pi";

function shellQuote(value: string): string {
  return `'${value.replaceAll("'", `'\\''`)}'`;
}

function buildResumeCommand(sessionFile: string): string {
  return `${shellQuote(PI_COMMAND)} --session ${shellQuote(sessionFile)}`;
}

export default function (pi: ExtensionAPI) {
  let resumeCommand: string | undefined;

  const printResumeCommand = () => {
    if (!resumeCommand) return;
    try {
      writeSync(
        process.stdout.fd,
        `Resume this session:\n  ${resumeCommand}\n`,
      );
    } catch {
      // Ignore EPIPE or closed stdout during shutdown.
    }
  };

  process.once("exit", printResumeCommand);

  pi.on("session_shutdown", async (event, ctx) => {
    if (event.reason !== "quit") {
      process.off("exit", printResumeCommand);
      return;
    }

    const sessionFile = ctx.sessionManager.getSessionFile();
    resumeCommand = sessionFile ? buildResumeCommand(sessionFile) : undefined;
  });

  pi.registerCommand("exit", {
    description: "Alias for /quit",
    handler: async (_args, ctx) => {
      ctx.shutdown();
    },
  });
}
