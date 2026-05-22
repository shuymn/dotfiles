import { describe, expect, test } from "bun:test";

import { addOption, addOptions, cliTimeoutMs } from "./tavily-cli";

describe("Tavily CLI helpers", () => {
  test("addOption omits undefined, false, empty strings, and empty string arrays", () => {
    const args: string[] = [];

    addOption(args, "--undefined", undefined);
    addOption(args, "--false", false);
    addOption(args, "--empty-string", "");
    addOption(args, "--empty-array", [""]);

    expect(args).toEqual([]);
  });

  test("addOption renders booleans, strings, numbers, and string arrays", () => {
    const args: string[] = [];

    addOption(args, "--enabled", true);
    addOption(args, "--name", "value");
    addOption(args, "--count", 3);
    addOption(args, "--max-results", 0);
    addOption(args, "--domains", ["example.com", "", "docs.example"]);

    expect(args).toEqual([
      "--enabled",
      "--name",
      "value",
      "--count",
      "3",
      "--max-results",
      "0",
      "--domains",
      "example.com,docs.example",
    ]);
  });

  test("addOptions applies options in order", () => {
    const args = ["search", "query", "--json"];

    addOptions(args, [
      ["--depth", "advanced"],
      ["--include-images", true],
      ["--timeout", undefined],
      ["--include-domains", ["example.com", "docs.example"]],
    ]);

    expect(args).toEqual([
      "search",
      "query",
      "--json",
      "--depth",
      "advanced",
      "--include-images",
      "--include-domains",
      "example.com,docs.example",
    ]);
  });

  test("cliTimeoutMs uses explicit or default seconds plus grace", () => {
    expect(cliTimeoutMs(30, 60)).toBe(40_000);
    expect(cliTimeoutMs(undefined, 60)).toBe(70_000);
  });
});
