import { describe, expect, test } from "bun:test";
import { terminatingTextResult } from "./structured-tool";

describe("structured-tool", () => {
  test("terminatingTextResult returns concise text content, preserves details, and terminates", () => {
    const details = {
      ok: true,
      warnings: [{ code: "notice", message: "kept" }],
    };

    const result = terminatingTextResult("Recorded.", details);

    expect(result).toEqual({
      content: [{ type: "text", text: "Recorded." }],
      details,
      terminate: true,
    });
    expect(result.details).toBe(details);
  });
});
