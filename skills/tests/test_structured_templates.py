import importlib.util
import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
COMMON_LIB_DIR = PROJECT_ROOT / "src" / "common" / "scripts" / "lib"
SCRIPTS_DIR = PROJECT_ROOT / "scripts"

for candidate in (COMMON_LIB_DIR, SCRIPTS_DIR):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

import structured_templates  # noqa: E402
from skills_models import (  # noqa: E402
    AcceptanceCriteriaRowModel,
    BoundaryInventoryRowModel,
    SubDocIndexRowModel,
)


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def load_json(relative_path: str) -> dict[str, object]:
    return json.loads((PROJECT_ROOT / relative_path).read_text(encoding="utf-8"))


SPLIT_CHECK = load_module(
    "skills_test_split_check",
    PROJECT_ROOT / "src" / "common" / "scripts" / "split_check.py",
)


def parse_boundary_inventory(markdown: str) -> list[BoundaryInventoryRowModel]:
    _headers, rows = SPLIT_CHECK.parse_markdown_table(markdown)
    return [
        BoundaryInventoryRowModel.model_validate(
            {
                "boundary": row["Boundary"],
                "owns_requirements_ac": row["Owns Requirements/AC"],
                "primary_verification_surface": row["Primary Verification Surface"],
                "temp_lifecycle_group": row["TEMP Lifecycle Group"],
                "parallel_stream": row["Parallel Stream"],
                "depends_on": row["Depends On"],
            }
        )
        for row in rows
    ]


def parse_sub_doc_index(markdown: str) -> list[SubDocIndexRowModel]:
    _headers, rows = SPLIT_CHECK.parse_markdown_table(markdown)
    return [
        SubDocIndexRowModel.model_validate(
            {
                "sub_id": row["Sub ID"],
                "file": row["File"],
                "owned_boundary": row["Owned Boundary"],
                "owns_requirements_ac": row["Owns Requirements/AC"],
            }
        )
        for row in rows
    ]


def parse_acceptance_criteria(markdown: str) -> list[AcceptanceCriteriaRowModel]:
    _headers, rows = SPLIT_CHECK.parse_markdown_table(markdown)
    return [
        AcceptanceCriteriaRowModel.model_validate(
            {
                "ac_id": row["AC ID"],
                "ears_type": row["EARS Type"],
                "contract_type": row["Contract Type"],
                "requirement_sentence": row["Requirement Sentence"],
                "verification_intent": row["Verification Intent"],
                "verification_command": row["Verification Command"],
            }
        )
        for row in rows
    ]


def test_design_fragments_round_trip_to_shared_review_models() -> None:
    template_path = (
        PROJECT_ROOT / "src" / "design-doc" / "references" / "design-templates.md.j2"
    )
    fragments = structured_templates.load_fragments(template_path)
    renderers = structured_templates.TEMPLATE_SPECS[template_path.name].renderers

    rendered_boundary_inventory = renderers["boundary_inventory"](
        fragments.boundary_inventory
    )
    rendered_sub_doc_index = renderers["sub_doc_index"](fragments.sub_doc_index)
    rendered_acceptance_criteria = renderers["acceptance_criteria"](
        fragments.acceptance_criteria
    )

    assert [
        row.model_dump()
        for row in parse_boundary_inventory(rendered_boundary_inventory)
    ] == [row.model_dump() for row in fragments.boundary_inventory]
    assert [
        row.model_dump() for row in parse_sub_doc_index(rendered_sub_doc_index)
    ] == [row.model_dump() for row in fragments.sub_doc_index]
    assert [
        row.model_dump()
        for row in parse_acceptance_criteria(rendered_acceptance_criteria)
    ] == [row.model_dump() for row in fragments.acceptance_criteria]


def test_checkpoint_summary_template_renders_semantic_verdict_placeholders() -> None:
    template_path = (
        PROJECT_ROOT / "src" / "decompose-plan" / "references" / "plan-templates.md.j2"
    )
    fragments = structured_templates.load_fragments(template_path)
    renderers = structured_templates.TEMPLATE_SPECS[template_path.name].renderers

    rendered_summary = renderers["checkpoint_summary"](fragments.checkpoint_summary)
    assert "- Alignment Verdict: PASS | FAIL" in rendered_summary
    assert "- Integration Coverage Guard: PASS | FAIL | N/A" in rendered_summary
    assert (
        "- Risk Classification Guard: PASS | FAIL | N/A "
        "(greenfield without Critical-domain changes)"
    ) in rendered_summary
    assert "- Trace Pack: `docs/plans/<topic>/plan.trace.md`" in rendered_summary
    assert "- Compose Pack: `docs/plans/<topic>/plan.compose.md`" in rendered_summary
    assert "- Updated At: `YYYY-MM-DD`" in rendered_summary
    assert "``docs/plans/<topic>/plan.trace.md``" not in rendered_summary


def test_trace_template_render_is_deterministic_plain_markdown() -> None:
    template_path = (
        PROJECT_ROOT / "src" / "decompose-plan" / "references" / "trace-templates.md.j2"
    )

    rendered_once = structured_templates.render_structured_template(template_path)
    rendered_twice = structured_templates.render_structured_template(template_path)

    assert rendered_once == rendered_twice
    assert "{{ render_fragment" not in rendered_once
    assert "Coverage ratio (`REQ+AC covered / total REQ+AC`): `X / Y`" in rendered_once
    assert "Required fixes: [if FAIL]" in rendered_once
    assert "retirement_trigger=[objective condition]" in rendered_once
    assert "retirement_verification=[verification command/test]" in rendered_once
    assert "removal_scope=[what is deleted/disabled]" in rendered_once
    assert "[[objective condition]]" not in rendered_once


def test_load_fragments_rejects_invalid_semantic_fragment_payload(
    tmp_path: Path,
) -> None:
    payload = load_json("src/design-doc/references/design-templates.fragments.json")
    payload["acceptance_criteria"][0]["ac_id"] = ""

    template_source = (
        PROJECT_ROOT / "src" / "design-doc" / "references" / "design-templates.md.j2"
    )
    template_path = tmp_path / template_source.name
    template_path.write_text(template_source.read_text(encoding="utf-8"), encoding="utf-8")
    template_path.with_name("design-templates.fragments.json").write_text(
        json.dumps(payload, indent=2) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(structured_templates.TemplateRenderError, match="invalid fragments"):
        structured_templates.load_fragments(template_path)
