#!/usr/bin/env python3
"""Build-time helpers for structured markdown templates."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from jinja2 import Environment, StrictUndefined
from pydantic import ValidationError

COMMON_LIB_DIR = (
    Path(__file__).resolve().parents[1] / "src" / "common" / "scripts" / "lib"
)
if str(COMMON_LIB_DIR) not in sys.path:
    sys.path.insert(0, str(COMMON_LIB_DIR))

from skills_models import (  # noqa: E402
    BulletsFragmentModel,
    TableFragmentModel,
    TemplateFragmentsFileModel,
)


class TemplateRenderError(RuntimeError):
    """Raised when a structured template cannot be rendered."""


def render_markdown_table(headers: list[str], rows: list[list[str]]) -> str:
    widths = [len(header) for header in headers]
    for row in rows:
        for index, value in enumerate(row):
            widths[index] = max(widths[index], len(value))

    header_line = (
        "| "
        + " | ".join(
            header.ljust(widths[index]) for index, header in enumerate(headers)
        )
        + " |"
    )
    separator_line = (
        "|-" + "-|-".join("-" * widths[index] for index in range(len(headers))) + "-|"
    )
    body_lines = [
        "| "
        + " | ".join(value.ljust(widths[index]) for index, value in enumerate(row))
        + " |"
        for row in rows
    ]
    return "\n".join([header_line, separator_line, *body_lines])


def render_fragment_markdown(
    fragment: TableFragmentModel | BulletsFragmentModel,
) -> str:
    if isinstance(fragment, TableFragmentModel):
        return render_markdown_table(fragment.headers, fragment.rows)
    return "\n".join(f"- {item}" for item in fragment.items)


def fragments_path_for_template(template_path: Path) -> Path:
    if not template_path.name.endswith(".md.j2"):
        raise TemplateRenderError(f"expected .md.j2 template: {template_path}")
    return template_path.with_name(
        template_path.name.removesuffix(".md.j2") + ".fragments.json"
    )


def load_fragments(template_path: Path) -> TemplateFragmentsFileModel:
    fragments_path = fragments_path_for_template(template_path)
    if not fragments_path.is_file():
        raise TemplateRenderError(
            f"missing fragments file for {template_path.name}: {fragments_path}"
        )

    try:
        payload = json.loads(fragments_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise TemplateRenderError(
            f"invalid JSON in {fragments_path}: {exc.msg} (line {exc.lineno}, column {exc.colno})"
        ) from exc

    try:
        return TemplateFragmentsFileModel.model_validate(payload)
    except ValidationError as exc:
        raise TemplateRenderError(
            f"invalid fragments for {template_path.name}: {exc}"
        ) from exc


def render_structured_template(template_path: Path) -> str:
    fragments = load_fragments(template_path)
    rendered_fragments = {
        slug: render_fragment_markdown(fragment)
        for slug, fragment in fragments.root.items()
    }
    env = Environment(
        autoescape=False,
        keep_trailing_newline=True,
        undefined=StrictUndefined,
    )
    template = env.from_string(template_path.read_text(encoding="utf-8"))
    rendered = template.render(
        render_fragment=lambda slug: rendered_fragments[slug],
        fragments=rendered_fragments,
    )
    return rendered if rendered.endswith("\n") else rendered + "\n"
