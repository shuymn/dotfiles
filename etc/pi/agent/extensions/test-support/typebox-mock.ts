import { mock } from "bun:test";

export function installTypeboxMock() {
  mock.module("typebox", () => {
    const Type = {
      Object: (properties: Record<string, unknown>, options = {}) => ({
        type: "object",
        properties,
        ...options,
      }),
      String: (options = {}) => ({ type: "string", ...options }),
      Boolean: (options = {}) => ({ type: "boolean", ...options }),
      Number: (options = {}) => ({ type: "number", ...options }),
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
}
