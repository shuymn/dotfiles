export type NotificationRecord = { message: string; level: string };
export type WidgetRecord = {
  key: string;
  lines: string[] | undefined;
  options?: unknown;
};
export type CustomCallRecord = { args: unknown[] };

export function createFakeUi(
  options: {
    selects?: unknown[];
    confirms?: boolean[];
    inputs?: unknown[];
    customs?: unknown[];
    editorText?: string;
  } = {},
) {
  const selects = [...(options.selects ?? [])];
  const confirms = [...(options.confirms ?? [])];
  const inputs = [...(options.inputs ?? [])];
  const customs = [...(options.customs ?? [])];
  const notifications: NotificationRecord[] = [];
  const widgets: WidgetRecord[] = [];
  const customCalls: CustomCallRecord[] = [];

  return {
    notifications,
    widgets,
    customCalls,
    editorText: options.editorText ?? "",
    notify(message: string, level: string) {
      notifications.push({ message, level });
    },
    setWidget(
      key: string,
      lines: string[] | undefined,
      widgetOptions?: unknown,
    ) {
      widgets.push({ key, lines, options: widgetOptions });
    },
    async select() {
      return selects.shift();
    },
    async confirm() {
      return confirms.shift() ?? false;
    },
    async input() {
      return inputs.shift();
    },
    async custom(...args: unknown[]) {
      customCalls.push({ args });
      return customs.shift();
    },
  };
}

export type FakeUi = ReturnType<typeof createFakeUi>;
