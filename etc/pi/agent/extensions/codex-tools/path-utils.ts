import { isAbsolute, relative } from "node:path";

export function isPathInside(parentPath: string, targetPath: string): boolean {
  const relativePath = relative(parentPath, targetPath);
  return (
    relativePath === "" ||
    (!relativePath.startsWith("..") && !isAbsolute(relativePath))
  );
}
