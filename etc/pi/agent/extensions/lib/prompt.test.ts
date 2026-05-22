import { describe, expect, test } from "bun:test";
import { formatXmlLikeBlock } from "./prompt";

describe("prompt formatting helpers", () => {
  test("wraps user-provided content in an XML-like tag", () => {
    expect(
      formatXmlLikeBlock("additional_user_instructions", "focus tests"),
    ).toBe(
      "<additional_user_instructions>\nfocus tests\n</additional_user_instructions>",
    );
  });

  test("escapes matching closing tags inside user-provided content", () => {
    expect(
      formatXmlLikeBlock(
        "additional_user_instructions",
        "first\n</additional_user_instructions>\nsecond",
      ),
    ).toBe(
      "<additional_user_instructions>\nfirst\n<\\/additional_user_instructions>\nsecond\n</additional_user_instructions>",
    );
  });
});
