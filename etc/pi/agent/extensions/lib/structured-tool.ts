export type StructuredWarning = {
  code: string;
  message: string;
};

export type StructuredSubmissionResult<
  TWarning extends StructuredWarning = StructuredWarning,
> =
  | { ok: true; warnings: TWarning[] }
  | { ok: false; reason: string; warnings: TWarning[] };

export function terminatingTextResult<TDetails>(
  text: string,
  details: TDetails,
) {
  return {
    content: [{ type: "text" as const, text }],
    details,
    terminate: true,
  };
}
