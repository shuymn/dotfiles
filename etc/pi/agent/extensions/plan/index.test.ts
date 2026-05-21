import { describe, expect, mock, test } from "bun:test";

mock.module("@earendil-works/pi-coding-agent", () => ({}));

type CommandDefinition = {
  description?: string;
  handler: (args: string, ctx: FakeCommandContext) => Promise<void> | void;
};

type FakeCommandContext = {
  isIdle: () => boolean;
  ui: {
    notify: (message: string, level: "info" | "warning" | "error") => void;
  };
};

function createFakePi() {
  const commands = new Map<string, CommandDefinition>();
  const sentMessages: string[] = [];

  return {
    commands,
    sentMessages,
    registerCommand(name: string, definition: CommandDefinition) {
      commands.set(name, definition);
    },
    sendUserMessage(message: string) {
      sentMessages.push(message);
    },
  };
}

function createCommandContext(options: { idle?: boolean } = {}) {
  const notifications: Array<{
    message: string;
    level: "info" | "warning" | "error";
  }> = [];
  return {
    ctx: {
      isIdle: () => options.idle ?? true,
      ui: {
        notify(message: string, level: "info" | "warning" | "error") {
          notifications.push({ message, level });
        },
      },
    },
    notifications,
  };
}

async function loadExtension() {
  return (await import("./index")).default;
}

describe("plan extension", () => {
  test("registers /plan and /impl commands", async () => {
    const extension = await loadExtension();
    const pi = createFakePi();

    extension(pi as never);

    expect([...pi.commands.keys()].sort()).toEqual(["impl", "plan"]);
    expect(pi.commands.get("plan")?.description).toContain("PLAN.md");
    expect(pi.commands.get("impl")?.description).toContain("PLAN.md");
  });

  test("/plan asks the agent to create PLAN.md without implementation or checkbox tasks", async () => {
    const extension = await loadExtension();
    const pi = createFakePi();
    extension(pi as never);

    const { ctx } = createCommandContext();
    await pi.commands.get("plan")!.handler("", ctx);

    expect(pi.sentMessages).toHaveLength(1);
    const prompt = pi.sentMessages[0]!;
    expect(prompt).toContain("PLAN.md");
    expect(prompt).toContain("まだ実装は開始しない");
    expect(prompt).toContain("implementation task section");
    expect(prompt).toContain("Markdown checkbox");
    expect(prompt).toContain("- [ ]");
    expect(prompt).toContain("PLAN.md itself is not the progress tracker");
  });

  test("/impl asks the agent to convert PLAN.md tasks into the pi todo tool and keep Japanese notes", async () => {
    const extension = await loadExtension();
    const pi = createFakePi();
    extension(pi as never);

    const { ctx } = createCommandContext();
    await pi.commands.get("impl")!.handler("", ctx);

    expect(pi.sentMessages).toHaveLength(1);
    const prompt = pi.sentMessages[0]!;
    expect(prompt).toContain("Read PLAN.md and implement it");
    expect(prompt).toContain("pi todo tool");
    expect(prompt).toContain("implementation-notes.md");
    expect(prompt).toContain("Japanese");
    expect(prompt).toContain("not by checking off items in PLAN.md");
    expect(prompt).toContain(
      "Update PLAN.md only when the actual plan/design/assumptions change",
    );
  });

  test("commands do not start a new agent turn while the agent is busy", async () => {
    const extension = await loadExtension();
    const pi = createFakePi();
    extension(pi as never);

    const { ctx, notifications } = createCommandContext({ idle: false });
    await pi.commands.get("plan")!.handler("", ctx);
    await pi.commands.get("impl")!.handler("", ctx);

    expect(pi.sentMessages).toEqual([]);
    expect(notifications).toEqual([
      {
        message: "エージェントが処理中です。完了後に再実行してください。",
        level: "warning",
      },
      {
        message: "エージェントが処理中です。完了後に再実行してください。",
        level: "warning",
      },
    ]);
  });
});
