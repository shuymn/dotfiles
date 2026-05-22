import {
  mkdir,
  readFile,
  realpath,
  rm,
  stat,
  writeFile,
} from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { withFileMutationQueue } from "@earendil-works/pi-coding-agent";

import { isPathInside } from "./path-utils";

export interface ApplyPatchResult {
  changedFiles: string[];
  summary: string;
}

type HunkLine = {
  kind: "context" | "remove" | "add";
  text: string;
};

type Hunk = {
  header?: string;
  lines: HunkLine[];
  endOfFile: boolean;
};

type PatchOperation =
  | { kind: "add"; path: string; lines: string[] }
  | { kind: "delete"; path: string }
  | { kind: "update"; path: string; moveTo?: string; hunks: Hunk[] };

interface PlannedWrite {
  kind: "write";
  changeKind: "A" | "M";
  path: string;
  absolutePath: string;
  content: string;
}

interface PlannedDelete {
  kind: "delete";
  changeKind: "D";
  path: string;
  absolutePath: string;
  summarize: boolean;
}

type PlannedChange = PlannedWrite | PlannedDelete;
type Match = { kind: "found"; index: number } | { kind: "missing" };
type Replacement = { start: number; oldLength: number; newLines: string[] };

const BEGIN = "*** Begin Patch";
const END = "*** End Patch";
const ENVIRONMENT_ID = "*** Environment ID:";
const ENVIRONMENT_ID_POSITION_ERROR =
  "Environment ID is only allowed immediately after *** Begin Patch";
const ADD = "*** Add File: ";
const DELETE = "*** Delete File: ";
const UPDATE = "*** Update File: ";
const MOVE = "*** Move to: ";
const EOF_MARKER = "*** End of File";

function normalizedPatchLines(input: string): string[] {
  const normalized = input.replace(/\r\n/g, "\n").replace(/\r/g, "\n").trim();
  return normalized ? normalized.split("\n") : [];
}

function invalidEnvironmentIdPositionError(lineNumber: number): Error {
  return new Error(
    `Invalid patch line ${lineNumber}: ${ENVIRONMENT_ID_POSITION_ERROR}`,
  );
}

function escapedControlCharacter(value: string): string {
  const codePoint = value.codePointAt(0) ?? 0;
  return `\\u{${codePoint.toString(16).padStart(4, "0")}}`;
}

function summarizeBoundaryLine(line: string | undefined): string {
  if (line === undefined) return "<missing>";
  const sanitized = line
    .replace(/[\t ]+/g, " ")
    .trim()
    .replace(/[\p{Cc}\p{Cf}]/gu, escapedControlCharacter);
  if (sanitized.length <= 80) return sanitized || "<empty>";
  return `${sanitized.slice(0, 77)}...`;
}

function strictPatchBodyLines(lines: string[]): string[] {
  const first = lines[0]?.trim();
  const last = lines.at(-1)?.trim();
  if (first !== BEGIN) {
    throw new Error(
      `Invalid patch: The first line of the patch must be '*** Begin Patch' (actual first line: ${summarizeBoundaryLine(lines[0])})`,
    );
  }
  if (last !== END) {
    throw new Error(
      `Invalid patch: The last line of the patch must be '*** End Patch' (actual last line: ${summarizeBoundaryLine(lines.at(-1))})`,
    );
  }
  return lines.slice(1, -1);
}

function patchBodyLines(input: string): string[] {
  const originalLines = normalizedPatchLines(input);
  try {
    return strictPatchBodyLines(originalLines);
  } catch (originalError) {
    const first = originalLines[0];
    const last = originalLines.at(-1);
    const isHeredoc =
      first === "<<EOF" || first === "<<'EOF'" || first === '<<"EOF"';
    if (isHeredoc && last?.endsWith("EOF") && originalLines.length >= 4) {
      return strictPatchBodyLines(originalLines.slice(1, -1));
    }
    throw originalError;
  }
}

function readPath(line: string, marker: string, lineNumber: number): string {
  const path = line.slice(marker.length).trim();
  if (!path) throw new Error(`Invalid patch line ${lineNumber}: missing path`);
  const segments = path.split(/[\\/]+/);
  if (
    path.startsWith("/") ||
    segments.some(
      (segment) => segment === "" || segment === "." || segment === "..",
    )
  ) {
    throw new Error(
      `Invalid patch line ${lineNumber}: file paths must be relative and stay inside the workspace`,
    );
  }
  return path;
}

function isFileOp(line: string): boolean {
  const trimmed = line.trim();
  return (
    trimmed.startsWith(ADD) ||
    trimmed.startsWith(DELETE) ||
    trimmed.startsWith(UPDATE) ||
    trimmed === END
  );
}

function parseUpdateChunk(
  lines: string[],
  startIndex: number,
  lineNumber: number,
  allowMissingContext: boolean,
): { hunk: Hunk; consumed: number } {
  if (startIndex >= lines.length) {
    throw new Error(
      `Invalid update hunk line ${lineNumber}: update hunk does not contain any lines`,
    );
  }

  let header: string | undefined;
  let index = startIndex;
  if (lines[index] === "@@") {
    index++;
  } else if (lines[index]?.startsWith("@@ ")) {
    header = (lines[index] ?? "").slice(3);
    index++;
  } else if (!allowMissingContext) {
    throw new Error(
      `Invalid update hunk line ${lineNumber}: expected @@ header`,
    );
  }

  if (index >= lines.length) {
    throw new Error(
      `Invalid update hunk line ${lineNumber + 1}: update hunk does not contain any lines`,
    );
  }

  const hunkLines: HunkLine[] = [];
  let endOfFile = false;
  let parsedLines = 0;

  for (; index < lines.length; index++) {
    const current = lines[index] ?? "";
    if (current === EOF_MARKER) {
      if (parsedLines === 0) {
        throw new Error(
          `Invalid update hunk line ${lineNumber + 1}: update hunk does not contain any lines`,
        );
      }
      endOfFile = true;
      parsedLines++;
      index++;
      break;
    }

    const prefix = current[0];
    if (prefix === undefined) {
      hunkLines.push({ kind: "context", text: "" });
    } else if (prefix === " ") {
      hunkLines.push({ kind: "context", text: current.slice(1) });
    } else if (prefix === "-") {
      hunkLines.push({ kind: "remove", text: current.slice(1) });
    } else if (prefix === "+") {
      hunkLines.push({ kind: "add", text: current.slice(1) });
    } else {
      if (parsedLines === 0) {
        throw new Error(
          `Invalid update hunk line ${lineNumber + 1}: expected space, -, or + prefix`,
        );
      }
      break;
    }
    parsedLines++;
  }

  return {
    hunk: { header, lines: hunkLines, endOfFile },
    consumed: index - startIndex,
  };
}

export function parseApplyPatch(input: string): PatchOperation[] {
  const lines = patchBodyLines(input);
  const operations: PatchOperation[] = [];
  let index = 0;

  if ((lines[index] ?? "").trimStart().startsWith(ENVIRONMENT_ID)) {
    const environmentId = (lines[index] ?? "")
      .trimStart()
      .slice(ENVIRONMENT_ID.length)
      .trim();
    if (!environmentId)
      throw new Error("Invalid patch: environment id cannot be empty");
    index++;
  }

  while (index < lines.length) {
    const line = lines[index]?.trim() ?? "";
    const lineNumber = index + 2;

    if (line.startsWith(ADD)) {
      const path = readPath(line, ADD, lineNumber);
      index++;
      const content: string[] = [];
      while (index < lines.length) {
        const contentLine = lines[index] ?? "";
        if (!contentLine.startsWith("+")) break;
        content.push(contentLine.slice(1));
        index++;
      }
      operations.push({ kind: "add", path, lines: content });
      continue;
    }

    if (line.startsWith(DELETE)) {
      operations.push({
        kind: "delete",
        path: readPath(line, DELETE, lineNumber),
      });
      index++;
      continue;
    }

    if (line.startsWith(UPDATE)) {
      const path = readPath(line, UPDATE, lineNumber);
      index++;
      let moveTo: string | undefined;
      if ((lines[index] ?? "").trim().startsWith(MOVE)) {
        moveTo = readPath((lines[index] ?? "").trim(), MOVE, index + 2);
        index++;
      }

      const hunks: Hunk[] = [];
      while (index < lines.length) {
        const current = lines[index] ?? "";
        if (current.trim() === "") {
          index++;
          continue;
        }
        if (current.trimStart().startsWith(ENVIRONMENT_ID)) {
          throw invalidEnvironmentIdPositionError(index + 2);
        }
        if (isFileOp(current) || current.startsWith("*")) break;

        const parsed = parseUpdateChunk(
          lines,
          index,
          index + 2,
          hunks.length === 0,
        );
        hunks.push(parsed.hunk);
        index += parsed.consumed;
      }

      if (hunks.length === 0)
        throw new Error(
          `Invalid update for ${path}: update must include hunks`,
        );
      operations.push({ kind: "update", path, moveTo, hunks });
      continue;
    }

    if (line.trimStart().startsWith(ENVIRONMENT_ID)) {
      throw invalidEnvironmentIdPositionError(lineNumber);
    }

    throw new Error(
      `Invalid patch line ${lineNumber}: expected file operation header`,
    );
  }

  return operations;
}

function resolvePatchPath(cwd: string, patchPath: string): string {
  return resolve(cwd, patchPath);
}

async function existingParentRealpath(
  absolutePath: string,
  cwdRealPath: string,
): Promise<string> {
  let current = dirname(absolutePath);
  while (isPathInside(cwdRealPath, current)) {
    try {
      return await realpath(current);
    } catch (error) {
      if (!isEnoent(error)) throw error;
      const parent = dirname(current);
      if (parent === current) break;
      current = parent;
    }
  }
  throw new Error(`Path escapes workspace: ${absolutePath}`);
}

async function assertPathInsideWorkspace(
  cwdRealPath: string,
  absolutePath: string,
  patchPath: string,
): Promise<void> {
  if (!isPathInside(cwdRealPath, absolutePath)) {
    throw new Error(`Path escapes workspace: ${patchPath}`);
  }
  const existingRealPath = await realpathIfExists(absolutePath);
  const resolvedPath =
    existingRealPath ??
    (await existingParentRealpath(absolutePath, cwdRealPath));
  if (!isPathInside(cwdRealPath, resolvedPath)) {
    throw new Error(`Path escapes workspace: ${patchPath}`);
  }
}

function isEnoent(error: unknown): boolean {
  return (
    !!error &&
    typeof error === "object" &&
    "code" in error &&
    error.code === "ENOENT"
  );
}

function assertNotAborted(signal?: AbortSignal): void {
  if (signal?.aborted) throw new Error("Operation aborted");
}

function splitContent(content: string): string[] {
  const lines = content.split("\n");
  if (lines.at(-1) === "") lines.pop();
  return lines;
}

function joinContent(lines: string[]): string {
  const next = [...lines];
  if (next.at(-1) !== "") next.push("");
  return next.join("\n");
}

function hunkOldLines(hunk: Hunk): string[] {
  return hunk.lines
    .filter((line) => line.kind !== "add")
    .map((line) => line.text);
}

function hunkNewLines(hunk: Hunk): string[] {
  return hunk.lines
    .filter((line) => line.kind !== "remove")
    .map((line) => line.text);
}

function normalizedMatchesAt(
  lines: string[],
  pattern: string[],
  index: number,
  normalize: (value: string) => string,
): boolean {
  if (index + pattern.length > lines.length) return false;
  for (let offset = 0; offset < pattern.length; offset++) {
    if (normalize(lines[index + offset] ?? "") !== pattern[offset])
      return false;
  }
  return true;
}

function findHeaderStart(
  path: string,
  lines: string[],
  header: string | undefined,
  startAt: number,
): number {
  if (!header) return startAt;
  const match = findMatch(lines, [header], startAt, false);
  if (match.kind === "missing")
    throw new Error(`Failed to find context '${header}' in ${path}`);
  return match.index + 1;
}

function normalizeUnicodePunctuation(value: string): string {
  return value
    .trim()
    .replace(/[\u2010\u2011\u2012\u2013\u2014\u2015\u2212]/g, "-")
    .replace(/[\u2018\u2019\u201A\u201B]/g, "'")
    .replace(/[\u201C\u201D\u201E\u201F]/g, '"')
    .replace(
      /[\u00A0\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200A\u202F\u205F\u3000]/g,
      " ",
    );
}

const MATCH_NORMALIZERS = [
  (value: string) => value,
  (value: string) => value.trimEnd(),
  (value: string) => value.trim(),
  normalizeUnicodePunctuation,
];

function findMatch(
  lines: string[],
  pattern: string[],
  startAt: number,
  endOfFile: boolean,
): Match {
  if (pattern.length === 0) return { kind: "found", index: startAt };
  if (pattern.length > lines.length) return { kind: "missing" };

  const searchStart =
    endOfFile && lines.length >= pattern.length
      ? Math.max(startAt, lines.length - pattern.length)
      : startAt;
  for (const normalize of MATCH_NORMALIZERS) {
    const normalizedPattern = pattern.map(normalize);
    for (
      let index = searchStart;
      index <= lines.length - pattern.length;
      index++
    ) {
      if (normalizedMatchesAt(lines, normalizedPattern, index, normalize))
        return { kind: "found", index };
    }
  }
  return { kind: "missing" };
}

function assertNoOverlappingReplacements(
  path: string,
  replacements: Replacement[],
): void {
  for (let index = 1; index < replacements.length; index++) {
    const previous = replacements[index - 1];
    const current = replacements[index];
    if (!previous || !current) continue;
    if (current.start < previous.start + previous.oldLength) {
      throw new Error(`Patch hunks overlap in ${path}`);
    }
  }
}

function applyUpdateHunks(
  path: string,
  content: string,
  hunks: Hunk[],
): string {
  const originalLines = splitContent(content);
  const replacements: Replacement[] = [];
  let lineIndex = 0;

  for (const hunk of hunks) {
    lineIndex = findHeaderStart(path, originalLines, hunk.header, lineIndex);
    let oldLines = hunkOldLines(hunk);
    let newLines = hunkNewLines(hunk);

    if (oldLines.length === 0) {
      const insertAt = hunk.endOfFile ? originalLines.length : lineIndex;
      replacements.push({
        start: insertAt,
        oldLength: 0,
        newLines,
      });
      lineIndex = insertAt;
      continue;
    }

    let match = findMatch(originalLines, oldLines, lineIndex, hunk.endOfFile);
    if (match.kind === "missing" && oldLines.at(-1) === "") {
      oldLines = oldLines.slice(0, -1);
      if (newLines.at(-1) === "") newLines = newLines.slice(0, -1);
      match = findMatch(originalLines, oldLines, lineIndex, hunk.endOfFile);
    }

    if (match.kind === "missing") {
      throw new Error(
        `Failed to find expected lines in ${path}:\n${hunkOldLines(hunk).join("\n")}`,
      );
    }

    replacements.push({
      start: match.index,
      oldLength: oldLines.length,
      newLines,
    });
    lineIndex = match.index + oldLines.length;
  }

  const lines = [...originalLines];
  replacements.sort((left, right) => left.start - right.start);
  assertNoOverlappingReplacements(path, replacements);
  for (const replacement of replacements.reverse()) {
    lines.splice(
      replacement.start,
      replacement.oldLength,
      ...replacement.newLines,
    );
  }
  return joinContent(lines);
}

async function assertDeletableFile(
  absolutePath: string,
  patchPath: string,
): Promise<void> {
  let metadata: Awaited<ReturnType<typeof stat>>;
  try {
    metadata = await stat(absolutePath);
  } catch (error) {
    if (isEnoent(error))
      throw new Error(`Cannot delete missing file: ${patchPath}`);
    throw error;
  }
  if (metadata.isDirectory())
    throw new Error(`Cannot delete directory: ${patchPath}`);
}

async function readUpdateFile(
  absolutePath: string,
  patchPath: string,
): Promise<string> {
  try {
    return await readFile(absolutePath, "utf8");
  } catch (error) {
    if (isEnoent(error))
      throw new Error(`Cannot update missing file: ${patchPath}`);
    throw error;
  }
}

async function realpathIfExists(path: string): Promise<string | undefined> {
  try {
    return await realpath(path);
  } catch (error) {
    if (isEnoent(error)) return undefined;
    throw error;
  }
}

async function planChanges(
  cwdRealPath: string,
  operations: PatchOperation[],
  signal?: AbortSignal,
): Promise<PlannedChange[]> {
  if (operations.length === 0) throw new Error("No files were modified.");

  const changes: PlannedChange[] = [];
  const pendingContent = new Map<string, string | null>();
  for (const operation of operations) {
    assertNotAborted(signal);
    const absolutePath = resolvePatchPath(cwdRealPath, operation.path);

    if (operation.kind === "add") {
      await assertPathInsideWorkspace(
        cwdRealPath,
        absolutePath,
        operation.path,
      );
      const content =
        operation.lines.length === 0 ? "" : `${operation.lines.join("\n")}\n`;
      pendingContent.set(absolutePath, content);
      changes.push({
        kind: "write",
        changeKind: "A",
        path: operation.path,
        absolutePath,
        content,
      });
      continue;
    }

    if (operation.kind === "delete") {
      if (pendingContent.get(absolutePath) === null)
        throw new Error(`Cannot delete missing file: ${operation.path}`);
      if (!pendingContent.has(absolutePath)) {
        await assertPathInsideWorkspace(
          cwdRealPath,
          absolutePath,
          operation.path,
        );
        await assertDeletableFile(absolutePath, operation.path);
      }
      pendingContent.set(absolutePath, null);
      changes.push({
        kind: "delete",
        changeKind: "D",
        path: operation.path,
        absolutePath,
        summarize: true,
      });
      continue;
    }

    const pending = pendingContent.get(absolutePath);
    if (pending === null)
      throw new Error(`Cannot update missing file: ${operation.path}`);
    const sourceFromDisk = pending === undefined;
    if (sourceFromDisk) {
      await assertPathInsideWorkspace(
        cwdRealPath,
        absolutePath,
        operation.path,
      );
    }
    const current =
      pending ?? (await readUpdateFile(absolutePath, operation.path));
    assertNotAborted(signal);
    const targetPath = operation.moveTo ?? operation.path;
    const targetAbsolutePath = resolvePatchPath(cwdRealPath, targetPath);
    if (operation.moveTo && targetAbsolutePath === absolutePath)
      throw new Error(`Cannot move file to itself: ${operation.path}`);
    if (operation.moveTo) {
      await assertPathInsideWorkspace(
        cwdRealPath,
        targetAbsolutePath,
        targetPath,
      );
      const sourceRealPath = await realpathIfExists(absolutePath);
      const targetRealPath = await realpathIfExists(targetAbsolutePath);
      if (sourceRealPath && targetRealPath && sourceRealPath === targetRealPath)
        throw new Error(`Cannot move file to itself: ${operation.path}`);
    }
    const content = applyUpdateHunks(operation.path, current, operation.hunks);
    pendingContent.set(targetAbsolutePath, content);
    changes.push({
      kind: "write",
      changeKind: "M",
      path: targetPath,
      absolutePath: targetAbsolutePath,
      content,
    });
    if (operation.moveTo) {
      if (sourceFromDisk) {
        await assertDeletableFile(absolutePath, operation.path);
      }
      pendingContent.set(absolutePath, null);
      changes.push({
        kind: "delete",
        changeKind: "D",
        path: operation.path,
        absolutePath,
        summarize: false,
      });
    }
  }
  return changes;
}

async function writeChange(
  change: PlannedWrite,
  signal?: AbortSignal,
): Promise<void> {
  assertNotAborted(signal);
  await mkdir(dirname(change.absolutePath), { recursive: true });
  await writeFile(change.absolutePath, change.content, { encoding: "utf8" });
}

async function withMutationQueues(
  paths: string[],
  fn: () => Promise<void>,
): Promise<void> {
  const [first, ...rest] = [...new Set(paths)].sort();
  if (!first) return fn();
  return withFileMutationQueue(first, () => withMutationQueues(rest, fn));
}

async function operationPaths(
  cwd: string,
  operations: PatchOperation[],
): Promise<string[]> {
  const paths: string[] = [];
  for (const operation of operations) {
    const absolutePath = resolvePatchPath(cwd, operation.path);
    const realPath = await realpathIfExists(absolutePath);
    paths.push(realPath ?? absolutePath);
    if (operation.kind === "update" && operation.moveTo) {
      const targetAbsolutePath = resolvePatchPath(cwd, operation.moveTo);
      const targetRealPath = await realpathIfExists(targetAbsolutePath);
      paths.push(targetRealPath ?? targetAbsolutePath);
    }
  }
  return paths;
}

function summarizedChanges(changes: PlannedChange[]): PlannedChange[] {
  return changes.filter(
    (change) => change.kind === "write" || change.summarize,
  );
}

function summaryForChanges(changes: PlannedChange[]): string {
  const lines = ["Success. Updated the following files:"];
  const visible = summarizedChanges(changes);
  for (const changeKind of ["A", "M", "D"] as const) {
    for (const change of visible) {
      if (change.changeKind === changeKind)
        lines.push(`${change.changeKind} ${change.path}`);
    }
  }
  return `${lines.join("\n")}\n`;
}

export async function applyPatch(
  cwd: string,
  input: string,
  signal?: AbortSignal,
): Promise<ApplyPatchResult> {
  const operations = parseApplyPatch(input);
  const cwdRealPath = await realpath(cwd);
  const paths = await operationPaths(cwdRealPath, operations);
  let changes: PlannedChange[] = [];

  await withMutationQueues(paths, async () => {
    changes = await planChanges(cwdRealPath, operations, signal);
    for (const change of changes) {
      assertNotAborted(signal);
      if (change.kind === "delete")
        await rm(change.absolutePath, { force: false });
      else await writeChange(change, signal);
    }
  });

  const changedFiles = [
    ...new Set(summarizedChanges(changes).map((change) => change.path)),
  ];
  return { changedFiles, summary: summaryForChanges(changes) };
}
