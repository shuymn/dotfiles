import { describe, expect, mock, test } from "bun:test";

mock.module("@earendil-works/pi-tui", () => ({
  truncateToWidth: (text: string, width: number, suffix = "") =>
    text.length > width
      ? `${text.slice(0, Math.max(0, width - suffix.length))}${suffix}`
      : text,
}));

type EventHandler = (event: unknown, ctx: FakeContext) => Promise<void> | void;
type FooterFactory = (
  tui: { requestRender: () => void },
  theme: unknown,
  footerData: FooterData,
) => FooterComponent;
type FooterComponent = {
  invalidate: () => void;
  render: (width: number) => string[];
  dispose: () => void;
};
type FooterData = {
  getGitBranch: () => string | undefined;
  onBranchChange: (listener: () => void) => () => void;
};
type FakeContext = ReturnType<typeof createContext>;

type ExecResult = { code: number; stdout: string; stderr: string };

type Model = {
  name?: string;
  displayName?: string;
  id?: string;
  provider?: string;
  contextWindow?: number;
};

function stripAnsi(text: string): string {
  return text.replace(/\x1b\[[0-9;]*m/g, "");
}

function createFakePi(
  execResult: ExecResult | Promise<ExecResult> | undefined = {
    code: 0,
    stdout: "/repo/root\n",
    stderr: "",
  },
) {
  const events = new Map<string, EventHandler[]>();
  const execCalls: Array<{
    command: string;
    args: string[];
    options: unknown;
  }> = [];
  let thinkingLevel = "medium";

  return {
    events,
    execCalls,
    setThinkingLevel(value: string) {
      thinkingLevel = value;
    },
    on(eventName: string, handler: EventHandler) {
      events.set(eventName, [...(events.get(eventName) ?? []), handler]);
    },
    async exec(command: string, args: string[], options: unknown) {
      execCalls.push({ command, args, options });
      if (execResult instanceof Error) throw execResult;
      return execResult;
    },
    getThinkingLevel: () => thinkingLevel,
  };
}

function createContext(
  options: {
    hasUI?: boolean;
    cwd?: string;
    model?: Model | unknown;
    models?: unknown[];
    usage?: { tokens: number } | undefined;
  } = {},
) {
  const footerFactories: FooterFactory[] = [];
  const model = Object.hasOwn(options, "model")
    ? options.model
    : { name: "claude", provider: "anthropic", contextWindow: 100_000 };

  return {
    hasUI: options.hasUI ?? true,
    cwd: options.cwd ?? "/fallback/project",
    model,
    modelRegistry: { getAvailable: () => options.models ?? [model] },
    getContextUsage: () => options.usage,
    footerFactories,
    ui: {
      setFooter(factory: FooterFactory) {
        footerFactories.push(factory);
      },
    },
  };
}

function instantiateFooter(ctx: FakeContext, branch?: string) {
  let renderCount = 0;
  const branchListeners: Array<() => void> = [];
  let disposed = false;
  const footerData: FooterData = {
    getGitBranch: () => branch,
    onBranchChange: (listener) => {
      branchListeners.push(listener);
      return () => {
        disposed = true;
      };
    },
  };
  const component = ctx.footerFactories[0](
    {
      requestRender: () => {
        renderCount += 1;
      },
    },
    {},
    footerData,
  );

  return {
    component,
    branchListeners,
    get renderCount() {
      return renderCount;
    },
    get disposed() {
      return disposed;
    },
    setBranch(value: string | undefined) {
      branch = value;
    },
  };
}

async function loadExtension() {
  return (await import("./index")).default;
}

describe("statusline extension", () => {
  test("registers lifecycle listeners only", async () => {
    const extension = await loadExtension();
    const pi = createFakePi();

    extension(pi as never);

    expect([...pi.events.keys()].sort()).toEqual([
      "agent_end",
      "model_select",
      "session_start",
      "thinking_level_select",
    ]);
  });

  test("does nothing on session_start without UI", async () => {
    const extension = await loadExtension();
    const pi = createFakePi();
    extension(pi as never);
    const ctx = createContext({ hasUI: false });

    await pi.events.get("session_start")![0]({}, ctx);

    expect(pi.execCalls).toEqual([]);
    expect(ctx.footerFactories).toEqual([]);
  });

  test("renders project, branch, model, thinking level, and context usage", async () => {
    const extension = await loadExtension();
    const pi = createFakePi({
      code: 0,
      stdout: "/work/my-project\n",
      stderr: "",
    });
    pi.setThinkingLevel("high");
    extension(pi as never);
    const ctx = createContext({
      model: { name: "sonnet", provider: "anthropic", contextWindow: 100_000 },
      models: [
        { name: "sonnet", provider: "anthropic" },
        { name: "sonnet", provider: "openrouter" },
      ],
      usage: { tokens: 25_000 },
    });

    await pi.events.get("session_start")![0]({}, ctx);
    const footer = instantiateFooter(ctx, "feature/statusline");
    const rendered = stripAnsi(footer.component.render(500)[0]);

    expect(pi.execCalls).toEqual([
      {
        command: "git",
        args: ["rev-parse", "--show-toplevel"],
        options: { timeout: 1000 },
      },
    ]);
    expect(rendered).toContain(
      "my-project on  feature/statusline via anthropic/sonnet • high",
    );
    expect(rendered).toContain("ctx ● 25%");
  });

  test("falls back to cwd basename when git root is unavailable", async () => {
    const extension = await loadExtension();
    const pi = createFakePi({ code: 1, stdout: "", stderr: "not git" });
    extension(pi as never);
    const ctx = createContext({
      cwd: "/Users/me/project/",
      model: { displayName: "Display Model" },
    });

    await pi.events.get("session_start")![0]({}, ctx);
    const footer = instantiateFooter(ctx);
    const rendered = stripAnsi(footer.component.render(300)[0]);

    expect(rendered).toContain("project via Display Model • medium");
    expect(rendered).not.toContain(" on  ");
    expect(rendered).not.toContain("ctx ●");
  });

  test("uses id or fallback model name and omits invalid context windows", async () => {
    const extension = await loadExtension();
    const pi = createFakePi(undefined);
    extension(pi as never);
    const idCtx = createContext({
      model: { id: "model-id", contextWindow: 0 },
      usage: { tokens: 500 },
    });

    await pi.events.get("session_start")![0]({}, idCtx);
    let footer = instantiateFooter(idCtx);
    expect(stripAnsi(footer.component.render(300)[0])).toContain(
      "model-id • medium",
    );
    expect(stripAnsi(footer.component.render(300)[0])).not.toContain("ctx ●");

    const fallbackCtx = createContext({ model: null, models: [null] });
    await pi.events.get("session_start")![0]({}, fallbackCtx);
    footer = instantiateFooter(fallbackCtx);
    expect(stripAnsi(footer.component.render(300)[0])).toContain(
      "no model • medium",
    );
  });

  test("truncates the rendered footer to the available width", async () => {
    const extension = await loadExtension();
    const pi = createFakePi({
      code: 0,
      stdout: "/very/long/project-name\n",
      stderr: "",
    });
    extension(pi as never);
    const ctx = createContext({
      model: { name: "very-long-model-name", contextWindow: 1000 },
      usage: { tokens: 900 },
    });

    await pi.events.get("session_start")![0]({}, ctx);
    const footer = instantiateFooter(ctx, "very-long-branch-name");
    const rendered = footer.component.render(24)[0];

    expect(rendered.length).toBeLessThanOrEqual(24);
  });

  test("agent_end and model/thinking selection request footer rerender", async () => {
    const extension = await loadExtension();
    const pi = createFakePi();
    extension(pi as never);
    const ctx = createContext();

    await pi.events.get("session_start")![0]({}, ctx);
    const footer = instantiateFooter(ctx);

    await pi.events.get("agent_end")![0]({}, ctx);
    await pi.events.get("model_select")![0]({}, ctx);
    await pi.events.get("thinking_level_select")![0]({}, ctx);

    expect(footer.renderCount).toBe(3);
  });

  test("branch changes request rerender and dispose clears listener", async () => {
    const extension = await loadExtension();
    const pi = createFakePi();
    extension(pi as never);
    const ctx = createContext();

    await pi.events.get("session_start")![0]({}, ctx);
    const footer = instantiateFooter(ctx, "main");

    footer.branchListeners[0]();
    expect(footer.renderCount).toBe(1);
    footer.component.dispose();
    expect(footer.disposed).toBe(true);

    await pi.events.get("model_select")![0]({}, ctx);
    expect(footer.renderCount).toBe(1);
  });
});
