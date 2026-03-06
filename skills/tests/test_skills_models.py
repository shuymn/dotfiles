import json
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

COMMON_LIB_DIR = (
    Path(__file__).resolve().parents[1] / "src" / "common" / "scripts" / "lib"
)
if str(COMMON_LIB_DIR) not in sys.path:
    sys.path.insert(0, str(COMMON_LIB_DIR))

from skills_models import (  # noqa: E402
    BoundaryInventoryRowModel,
    DesignTemplateSourceModel,
    GranularityCardValuesModel,
    ManagedSkillsManifestModel,
    PlanTemplateSourceModel,
    TraceTemplateSourceModel,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def load_json(relative_path: str) -> dict[str, object]:
    return json.loads((PROJECT_ROOT / relative_path).read_text(encoding="utf-8"))


def test_design_template_source_accepts_semantic_fragments() -> None:
    model = DesignTemplateSourceModel.model_validate(
        load_json("src/design-doc/references/design-templates.fragments.json")
    )

    assert model.boundary_inventory[0].depends_on == ("[Boundary names]",)
    assert model.acceptance_criteria[0].ac_id == "AC01"


def test_design_template_source_rejects_blank_required_table_cell() -> None:
    payload = load_json("src/design-doc/references/design-templates.fragments.json")
    payload["acceptance_criteria"][0]["ac_id"] = ""

    with pytest.raises(ValidationError):
        DesignTemplateSourceModel.model_validate(payload)


def test_plan_template_source_rejects_legacy_generic_fragment_shape() -> None:
    with pytest.raises(ValidationError):
        PlanTemplateSourceModel.model_validate(
            {
                "quality_gates": {
                    "kind": "table",
                    "headers": ["Category", "Command"],
                    "rows": [["test", "`uv run pytest`"]],
                },
                "checkpoint_summary": {
                    "alignment_verdict": "PASS | FAIL",
                    "forward_fidelity": "PASS | FAIL",
                    "reverse_fidelity": "PASS | FAIL",
                    "non_goal_guard": "PASS | FAIL",
                    "behavioral_lock_guard": "PASS | FAIL",
                    "temporal_completeness_guard": "PASS | FAIL",
                    "quality_gate_guard": "PASS | FAIL",
                    "integration_coverage_guard": "PASS | FAIL | N/A",
                    "risk_classification_guard": "PASS | FAIL | N/A (greenfield without Critical-domain changes)",
                    "temp_summary": "introduced=0, retired=0, open=0, waived=0",
                    "trace_pack": "`docs/plans/topic/plan.trace.md`",
                    "compose_pack": "`docs/plans/topic/plan.compose.md`",
                    "updated_at": "`2026-03-06`",
                },
            }
        )


def test_plan_template_source_rejects_blank_required_table_cell() -> None:
    payload = load_json("src/decompose-plan/references/plan-templates.fragments.json")
    payload["quality_gates"][0]["category"] = ""

    with pytest.raises(ValidationError):
        PlanTemplateSourceModel.model_validate(payload)


def test_plan_template_source_keeps_checkpoint_pack_values_semantic() -> None:
    model = PlanTemplateSourceModel.model_validate(
        load_json("src/decompose-plan/references/plan-templates.fragments.json")
    )

    assert model.checkpoint_summary.trace_pack == "docs/plans/<topic>/plan.trace.md"
    assert model.checkpoint_summary.compose_pack == "docs/plans/<topic>/plan.compose.md"
    assert model.checkpoint_summary.updated_at == "YYYY-MM-DD"


def test_trace_template_source_accepts_semantic_fragments() -> None:
    model = TraceTemplateSourceModel.model_validate(
        load_json("src/decompose-plan/references/trace-templates.fragments.json")
    )

    assert model.forward_fidelity.requirements_ac_coverage.covered == "X"
    assert model.compose_alignment_verdict.required_fixes == ["[if FAIL]"]
    assert (
        model.temporary_mechanism_trace[0].retirement_trigger == "objective condition"
    )


def test_trace_template_source_rejects_blank_required_table_cell() -> None:
    payload = load_json("src/decompose-plan/references/trace-templates.fragments.json")
    payload["ac_ownership_map"][0]["owner_task"] = ""

    with pytest.raises(ValidationError):
        TraceTemplateSourceModel.model_validate(payload)


@pytest.mark.parametrize(
    "section_name",
    [
        "decision_trace",
        "design_task_trace_matrix",
        "task_design_compose_matrix",
        "temporary_mechanism_trace",
        "behavioral_lock_map",
    ],
)
def test_trace_template_source_rejects_empty_required_bullet_sections(
    section_name: str,
) -> None:
    payload = load_json("src/decompose-plan/references/trace-templates.fragments.json")
    payload[section_name] = []

    with pytest.raises(ValidationError):
        TraceTemplateSourceModel.model_validate(payload)


def test_manifest_rejects_empty_skill_name() -> None:
    with pytest.raises(ValidationError):
        ManagedSkillsManifestModel.model_validate(
            {
                "version": 1,
                "source_root": ".",
                "skills": ["valid-skill", ""],
            }
        )


def test_boundary_inventory_requires_yes_or_no_parallel_stream() -> None:
    with pytest.raises(ValidationError):
        BoundaryInventoryRowModel.model_validate(
            {
                "boundary": "API",
                "owns_requirements_ac": "AC01",
                "primary_verification_surface": "pytest",
                "temp_lifecycle_group": "none",
                "parallel_stream": "maybe",
                "depends_on": "none",
            }
        )


def test_granularity_cards_reject_invalid_card() -> None:
    with pytest.raises(ValidationError):
        GranularityCardValuesModel.model_validate(
            {
                "objective": 4,
                "surface": 1,
                "verification": 1,
                "rollback": 1,
            }
        )
