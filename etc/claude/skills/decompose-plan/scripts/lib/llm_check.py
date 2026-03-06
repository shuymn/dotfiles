#!/usr/bin/env python3
"""Python equivalent of llm-check-output.sh for LLM_CHECK_V2 structured output.

Mirrors the shell helper's function-level API:
  llm_check_resolve_mode   -> resolve_mode
  llm_check_sanitize_value -> sanitize
  llm_check_emit_header    -> emit_header
  llm_check_emit_line      -> emit_line
  llm_check_emit_footer    -> emit_footer
  llm_check_join_by        -> join_by
"""

from __future__ import annotations

import os

OUTPUT_SCHEMA = "LLM_CHECK_V2"


def resolve_mode() -> str:
    mode = os.environ.get("LLM_CHECK_MODE", "compact").strip().casefold()
    return mode if mode in {"compact", "full"} else "compact"


def sanitize(value: str) -> str:
    return value.replace("\r", "").replace("\n", "\\n")


def emit_line(key: str, value: str | int) -> None:
    print(f"{key}={sanitize(str(value))}")


def emit_header(tool: str, mode: str, status: str, code: str, summary: str) -> None:
    print(OUTPUT_SCHEMA)
    emit_line("tool", tool)
    emit_line("mode", mode)
    emit_line("status", status)
    emit_line("code", code)
    emit_line("summary", summary)


def emit_footer() -> None:
    print(f"END_{OUTPUT_SCHEMA}")


def join_by(delimiter: str, items: list[str]) -> str:
    return delimiter.join(items)
