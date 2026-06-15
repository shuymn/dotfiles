import os from "node:os";
import path from "node:path";

export function companionSocketPath() {
    return path.join(os.tmpdir(), `pi-companion-${process.getuid?.() ?? "user"}`, "companion.sock");
}

