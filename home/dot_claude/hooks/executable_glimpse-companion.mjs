#!/usr/bin/env node
import net from "node:net";
import path from "node:path";
import { companionSocketPath } from "./glimpse-companion-socket-path.mjs";

const CONNECT_TIMEOUT_MS = 150;

function readStdin() {
    return new Promise((resolve) => {
        let input = "";
        process.stdin.setEncoding("utf8");
        process.stdin.on("data", (chunk) => {
            input += chunk;
        });
        process.stdin.on("end", () => resolve(input));
        process.stdin.on("error", () => resolve(""));
    });
}

function parseJson(input) {
    try {
        return JSON.parse(input);
    } catch {
        return null;
    }
}

function basename(value) {
    if (typeof value !== "string" || value.length === 0) {
        return undefined;
    }
    return path.basename(value);
}

function firstString(...values) {
    return values.find((value) => typeof value === "string" && value.length > 0);
}

function stableId(payload) {
    return firstString(payload.session_id, payload.sessionId, payload.transcript_path, payload.transcriptPath) ?? `cwd:${projectCwd(payload)}`;
}

function projectCwd(payload) {
    return firstString(payload.cwd, payload.workspace?.cwd, payload.workspace?.path) ?? process.cwd();
}

function projectName(payload) {
    return basename(projectCwd(payload)) ?? "project";
}

function hookEvent(payload) {
    return firstString(payload.hook_event_name, payload.hookEventName, payload.event, payload.type);
}

function toolName(payload) {
    return firstString(payload.tool_name, payload.toolName, payload.tool?.name);
}

function toolInput(payload) {
    return payload.tool_input ?? payload.toolInput ?? payload.tool?.input ?? {};
}

function truncate(value, maxLength = 80) {
    if (typeof value !== "string") {
        return undefined;
    }
    const compact = value.replace(/\s+/g, " ").trim();
    if (compact.length <= maxLength) {
        return compact || undefined;
    }
    return `${compact.slice(0, maxLength - 1)}…`;
}

function fileDetail(input) {
    return basename(firstString(input.file_path, input.filePath, input.path, input.notebook_path, input.notebookPath));
}

function searchDetail(input) {
    return truncate(firstString(input.pattern, input.path, input.glob, input.query));
}

function toolStatus(name, input) {
    switch (name) {
        case "Read":
            return { status: "reading", detail: fileDetail(input) };
        case "Edit":
        case "Write":
        case "MultiEdit":
        case "NotebookEdit":
            return { status: "editing", detail: fileDetail(input) };
        case "Bash":
            return { status: "running", detail: truncate(input.command) };
        case "Grep":
        case "Glob":
        case "LS":
            return { status: "searching", detail: searchDetail(input) };
        default:
            return { status: "running", detail: name };
    }
}

function messageFor(payload) {
    const event = hookEvent(payload);
    if (!event) {
        return null;
    }

    let status;
    let detail;

    switch (event) {
        case "UserPromptSubmit":
            status = "thinking";
            break;
        case "PreToolUse": {
            const mapped = toolStatus(toolName(payload), toolInput(payload));
            status = mapped.status;
            detail = mapped.detail;
            break;
        }
        case "PostToolUse":
            status = "thinking";
            break;
        case "PostToolUseFailure":
            status = "error";
            detail = toolName(payload);
            break;
        case "Stop":
            status = "done";
            break;
        case "StopFailure":
            status = "error";
            break;
        default:
            return null;
    }

    return {
        id: stableId(payload),
        project: projectName(payload),
        status,
        ...(detail ? { detail } : {}),
    };
}

function sendMessage(message) {
    return new Promise((resolve) => {
        const socket = net.createConnection(companionSocketPath());
        let settled = false;

        const finish = () => {
            if (settled) {
                return;
            }
            settled = true;
            socket.destroy();
            resolve();
        };

        socket.setTimeout(CONNECT_TIMEOUT_MS, finish);
        socket.on("error", finish);
        socket.on("connect", () => {
            socket.end(`${JSON.stringify(message)}\n`, finish);
        });
    });
}

const payload = parseJson(await readStdin());
const message = payload ? messageFor(payload) : null;

if (message) {
    await sendMessage(message);
}

process.exit(0);
