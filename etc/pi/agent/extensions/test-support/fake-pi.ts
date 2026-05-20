export type ExecCall = {
  command: string;
  args: string[];
  options: Record<string, unknown>;
};

export type ExecResult = {
  code: number;
  stdout: string;
  stderr: string;
};

type ExecHandler = (call: ExecCall) => ExecResult | Promise<ExecResult>;
type EventHandler = (event: unknown, ctx?: unknown) => unknown;
export type FakeToolDefinition = { name: string; [key: string]: unknown };
export type FakeCommandDefinition = {
  description?: string;
  handler: unknown;
  [key: string]: unknown;
};
type FlagDefinition = { name?: string; [key: string]: unknown };
// biome-ignore lint/suspicious/noExplicitAny: extension tests assert arbitrary message payload shapes.
type MessageRecord = { message: any; options: unknown };
// biome-ignore lint/suspicious/noExplicitAny: extension tests assert arbitrary entry payload shapes.
type EntryRecord = { entry: any; options: unknown };

function defaultExec(): ExecResult {
  return { code: 0, stdout: "", stderr: "" };
}

export function createFakePi<
  TTool extends FakeToolDefinition = FakeToolDefinition,
  TCommand extends FakeCommandDefinition = FakeCommandDefinition,
>(
  options: {
    exec?: ExecHandler;
    flags?: Record<string, unknown>;
    thinkingLevel?: string;
  } = {},
) {
  const tools = new Map<string, TTool>();
  const commands = new Map<string, TCommand>();
  const flags = new Map<string, unknown>(Object.entries(options.flags ?? {}));
  const flagDefinitions = new Map<string, FlagDefinition>();
  const events = new Map<string, EventHandler[]>();
  const execCalls: ExecCall[] = [];
  const sentMessages: MessageRecord[] = [];
  const appendedEntries: EntryRecord[] = [];
  const execHandler = options.exec ?? defaultExec;
  const thinkingLevel = options.thinkingLevel ?? "medium";

  return {
    tools,
    commands,
    flags,
    flagDefinitions,
    events,
    execCalls,
    sentMessages,
    appendedEntries,
    registerTool(definition: TTool) {
      tools.set(definition.name, definition);
    },
    registerCommand(name: string, definition: TCommand) {
      commands.set(name, definition);
    },
    registerFlag(name: string, definition: FlagDefinition) {
      flagDefinitions.set(name, definition);
    },
    getFlag(name: string) {
      return flags.get(name);
    },
    on(eventName: string, handler: EventHandler) {
      events.set(eventName, [...(events.get(eventName) ?? []), handler]);
    },
    async exec(
      command: string,
      args: string[],
      options: Record<string, unknown> = {},
    ) {
      const call = { command, args, options };
      execCalls.push(call);
      return execHandler(call);
    },
    // biome-ignore lint/suspicious/noExplicitAny: extension tests assert arbitrary message payload shapes.
    sendMessage(message: any, options: unknown) {
      sentMessages.push({ message, options });
    },
    // biome-ignore lint/suspicious/noExplicitAny: extension tests assert arbitrary entry payload shapes.
    appendEntry(entry: any, options: unknown) {
      appendedEntries.push({ entry, options });
    },
    getThinkingLevel() {
      return thinkingLevel;
    },
    getTool(name: string) {
      return tools.get(name);
    },
    getCommand(name: string) {
      return commands.get(name);
    },
    getEventHandlers(eventName: string) {
      return events.get(eventName) ?? [];
    },
  };
}

export type FakePi = ReturnType<typeof createFakePi>;

export async function shutdownFakePis(pis: FakePi[], ctx?: unknown) {
  for (const pi of pis) {
    for (const handler of pi.getEventHandlers("session_shutdown")) {
      await handler({}, ctx);
    }
  }
  pis.splice(0);
}
