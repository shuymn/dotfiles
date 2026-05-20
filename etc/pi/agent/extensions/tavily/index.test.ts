import { describe, expect, mock, test } from "bun:test";

mock.module("@earendil-works/pi-ai", () => ({
  StringEnum: (values: readonly string[], options = {}) => ({
    enum: values,
    ...options,
  }),
}));

mock.module("typebox", () => {
  const Type = {
    Object: (properties: Record<string, unknown>, options = {}) => ({
      type: "object",
      properties,
      ...options,
    }),
    String: (options = {}) => ({ type: "string", ...options }),
    Boolean: (options = {}) => ({ type: "boolean", ...options }),
    Integer: (options = {}) => ({ type: "integer", ...options }),
    Array: (items: unknown, options = {}) => ({
      type: "array",
      items,
      ...options,
    }),
    Optional: (schema: Record<string, unknown>) => ({
      ...schema,
      optional: true,
    }),
  };
  return { Type };
});

type ExecCall = {
  command: string;
  args: string[];
  options: Record<string, unknown>;
};
type ExecResult = { code: number; stdout: string; stderr: string };
type ToolDefinition = {
  name: string;
  label: string;
  description: string;
  promptSnippet?: string;
  promptGuidelines?: string[];
  parameters: unknown;
  execute: (
    toolCallId: string,
    params: any,
    signal: AbortSignal | undefined,
    onUpdate:
      | ((update: { content: Array<{ type: "text"; text: string }> }) => void)
      | undefined,
  ) => Promise<{
    content: Array<{ type: "text"; text: string }>;
    details: any;
  }>;
};

function createFakePi(
  execHandler: (
    call: ExecCall,
  ) => ExecResult | Promise<ExecResult> = defaultExec,
) {
  const tools = new Map<string, ToolDefinition>();
  const execCalls: ExecCall[] = [];
  return {
    tools,
    execCalls,
    registerTool(definition: ToolDefinition) {
      tools.set(definition.name, definition);
    },
    async exec(
      command: string,
      args: string[],
      options: Record<string, unknown>,
    ) {
      const call = { command, args, options };
      execCalls.push(call);
      return execHandler(call);
    },
  };
}

function defaultExec(call: ExecCall): ExecResult {
  return {
    code: 0,
    stdout: JSON.stringify({
      ok: true,
      command: call.args[0],
      args: call.args,
    }),
    stderr: "",
  };
}

async function loadExtension() {
  return (await import("./index")).default;
}

async function loadTools(
  execHandler?: (call: ExecCall) => ExecResult | Promise<ExecResult>,
) {
  const extension = await loadExtension();
  const pi = createFakePi(execHandler);
  extension(pi as never);
  return { pi, tools: pi.tools };
}

describe("tavily extension", () => {
  test("registers all Tavily tools with schemas and guidance", async () => {
    const { tools } = await loadTools();

    expect([...tools.keys()].sort()).toEqual([
      "tavily_auth_status",
      "tavily_crawl",
      "tavily_extract",
      "tavily_map",
      "tavily_search",
    ]);
    expect(tools.get("tavily_search")!).toMatchObject({
      label: "Tavily Search",
      parameters: {
        type: "object",
        properties: {
          query: { type: "string" },
          depth: {
            enum: ["ultra-fast", "fast", "basic", "advanced"],
            optional: true,
          },
        },
      },
    });
    expect(tools.get("tavily_search")!.promptGuidelines!.join("\n")).toContain(
      "Keep tavily_search queries under 400 characters",
    );
    expect(tools.get("tavily_auth_status")!.parameters).toEqual({
      type: "object",
      properties: {},
    });
  });

  test("search builds tvly search args, emits progress, and returns parsed JSON details", async () => {
    const { pi, tools } = await loadTools();
    const updates: string[] = [];
    const signal = new AbortController().signal;

    const result = await tools.get("tavily_search")!.execute(
      "call",
      {
        query: " latest AI news ",
        depth: "advanced",
        maxResults: 10,
        topic: "news",
        timeRange: "week",
        startDate: "2026-05-01",
        endDate: "2026-05-20",
        includeDomains: ["example.com", "", "news.example"],
        excludeDomains: ["spam.example"],
        country: "japan",
        includeAnswer: "advanced",
        includeRawContent: "markdown",
        includeImages: true,
        includeImageDescriptions: true,
        chunksPerSource: 3,
      },
      signal,
      (update) => updates.push(update.content[0].text),
    );

    expect(updates).toEqual(["Running tvly search latest AI news ..."]);
    expect(pi.execCalls).toEqual([
      {
        command: "tvly",
        args: [
          "search",
          "latest AI news",
          "--json",
          "--depth",
          "advanced",
          "--max-results",
          "10",
          "--topic",
          "news",
          "--time-range",
          "week",
          "--start-date",
          "2026-05-01",
          "--end-date",
          "2026-05-20",
          "--include-domains",
          "example.com,news.example",
          "--exclude-domains",
          "spam.example",
          "--country",
          "japan",
          "--include-answer",
          "advanced",
          "--include-raw-content",
          "markdown",
          "--include-images",
          "--include-image-descriptions",
          "--chunks-per-source",
          "3",
        ],
        options: { signal, timeout: 120_000 },
      },
    ]);
    expect(result.content[0].text).toContain("Tavily result:\n\n{");
    expect(result.details).toMatchObject({
      command: ["tvly", ...pi.execCalls[0].args],
      exitCode: 0,
      json: { ok: true, command: "search" },
    });
  });

  test("search rejects overlong queries before executing tvly", async () => {
    const { pi, tools } = await loadTools();

    await expect(
      tools
        .get("tavily_search")!
        .execute("call", { query: "x".repeat(401) }, undefined, undefined),
    ).rejects.toThrow("tavily_search query must be 400 characters or fewer");
    expect(pi.execCalls).toEqual([]);
  });

  test("extract validates chunksPerSource dependency and computes timeout", async () => {
    const { pi, tools } = await loadTools();
    const updates: string[] = [];

    await expect(
      tools
        .get("tavily_extract")!
        .execute(
          "call",
          { urls: ["https://example.com"], chunksPerSource: 2 },
          undefined,
          undefined,
        ),
    ).rejects.toThrow("tavily_extract chunksPerSource requires a query.");

    await tools.get("tavily_extract")!.execute(
      "call",
      {
        urls: ["https://example.com/a", "https://example.com/b"],
        query: "pricing",
        chunksPerSource: 2,
        extractDepth: "advanced",
        format: "text",
        includeImages: true,
        timeoutSeconds: 5,
      },
      undefined,
      (update) => updates.push(update.content[0].text),
    );

    expect(updates).toEqual(["Extracting 2 URL(s) with Tavily..."]);
    expect(pi.execCalls.at(-1)).toEqual({
      command: "tvly",
      args: [
        "extract",
        "https://example.com/a",
        "https://example.com/b",
        "--json",
        "--query",
        "pricing",
        "--chunks-per-source",
        "2",
        "--extract-depth",
        "advanced",
        "--format",
        "text",
        "--include-images",
        "--timeout",
        "5",
      ],
      options: { signal: undefined, timeout: 15_000 },
    });
  });

  test("map and crawl build site args with default and custom timeouts", async () => {
    const { pi, tools } = await loadTools();

    await tools.get("tavily_map")!.execute(
      "call",
      {
        url: "https://docs.example.com",
        maxDepth: 2,
        maxBreadth: 5,
        limit: 20,
        instructions: "docs only",
        selectPaths: ["/docs"],
        excludePaths: ["/blog"],
        allowExternal: true,
      },
      undefined,
      undefined,
    );
    expect(pi.execCalls.at(-1)).toEqual({
      command: "tvly",
      args: [
        "map",
        "https://docs.example.com",
        "--json",
        "--max-depth",
        "2",
        "--max-breadth",
        "5",
        "--limit",
        "20",
        "--instructions",
        "docs only",
        "--select-paths",
        "/docs",
        "--exclude-paths",
        "/blog",
        "--allow-external",
      ],
      options: { signal: undefined, timeout: 160_000 },
    });

    await expect(
      tools
        .get("tavily_crawl")!
        .execute(
          "call",
          { url: "https://docs.example.com", chunksPerSource: 2 },
          undefined,
          undefined,
        ),
    ).rejects.toThrow("tavily_crawl chunksPerSource requires instructions.");

    await tools.get("tavily_crawl")!.execute(
      "call",
      {
        url: "https://docs.example.com",
        maxDepth: 3,
        maxBreadth: 4,
        limit: 30,
        instructions: "api docs",
        chunksPerSource: 2,
        extractDepth: "basic",
        format: "markdown",
        selectPaths: ["/api", "/guide"],
        excludePaths: ["/old"],
        selectDomains: ["docs.example.com"],
        excludeDomains: ["cdn.example.com"],
        allowExternal: false,
        includeImages: true,
        timeoutSeconds: 20,
      },
      undefined,
      undefined,
    );
    expect(pi.execCalls.at(-1)).toEqual({
      command: "tvly",
      args: [
        "crawl",
        "https://docs.example.com",
        "--json",
        "--max-depth",
        "3",
        "--max-breadth",
        "4",
        "--limit",
        "30",
        "--instructions",
        "api docs",
        "--chunks-per-source",
        "2",
        "--extract-depth",
        "basic",
        "--format",
        "markdown",
        "--select-paths",
        "/api,/guide",
        "--exclude-paths",
        "/old",
        "--select-domains",
        "docs.example.com",
        "--exclude-domains",
        "cdn.example.com",
        "--include-images",
        "--timeout",
        "20",
      ],
      options: { signal: undefined, timeout: 30_000 },
    });
  });

  test("auth status runs tvly auth with auth timeout", async () => {
    const { pi, tools } = await loadTools();

    await tools
      .get("tavily_auth_status")!
      .execute("call", {}, undefined, undefined);

    expect(pi.execCalls).toEqual([
      {
        command: "tvly",
        args: ["auth", "--json"],
        options: { signal: undefined, timeout: 20_000 },
      },
    ]);
  });

  test("non-JSON stdout is returned as text and stderr is included on command failure", async () => {
    const { tools } = await loadTools(() => ({
      code: 2,
      stdout: "plain output",
      stderr: "bad auth",
    }));

    await expect(
      tools
        .get("tavily_auth_status")!
        .execute("call", {}, undefined, undefined),
    ).rejects.toThrow(
      "Failed to execute tvly. Ensure the Tavily CLI is installed and authenticated (tvly auth).\n\nTavily command failed with exit code 2:\n\nplain output\n\nstderr:\nbad auth",
    );
  });

  test("wraps thrown exec errors with installation/authentication guidance", async () => {
    const { tools } = await loadTools(() => {
      throw new Error("ENOENT tvly");
    });

    await expect(
      tools
        .get("tavily_auth_status")!
        .execute("call", {}, undefined, undefined),
    ).rejects.toThrow(
      "Failed to execute tvly. Ensure the Tavily CLI is installed and authenticated (tvly auth).\n\nENOENT tvly",
    );
  });

  test("truncates oversized rendered output", async () => {
    const longText = "x".repeat(60_010);
    const { tools } = await loadTools(() => ({
      code: 0,
      stdout: longText,
      stderr: "",
    }));

    const result = await tools
      .get("tavily_auth_status")!
      .execute("call", {}, undefined, undefined);

    expect(result.content[0].text).toContain(
      "[truncated by tavily extension: 26 chars omitted]",
    );
    expect(result.content[0].text.length).toBeGreaterThan(60_000);
  });
});
