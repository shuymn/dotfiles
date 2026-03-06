#!/usr/bin/env python3
"""Build-time helpers for semantic structured markdown templates."""

from __future__ import annotations

import json
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jinja2 import Environment, StrictUndefined
from pydantic import BaseModel, ValidationError

COMMON_LIB_DIR = (
    Path(__file__).resolve().parents[1] / "src" / "common" / "scripts" / "lib"
)
if str(COMMON_LIB_DIR) not in sys.path:
    sys.path.insert(0, str(COMMON_LIB_DIR))

from skills_models import (  # noqa: E402
    AcceptanceCriteriaRowModel,
    AcOwnershipMapRowModel,
    BehavioralLockGuardSectionModel,
    BehavioralLockMapRowModel,
    CheckpointSummaryTemplateModel,
    ClarificationRowModel,
    ComposeAlignmentVerdictSectionModel,
    ComposeReconstructedDesignSummarySectionModel,
    ComposeScopeDiffSectionModel,
    DecisionLogRowModel,
    DecisionTraceRowModel,
    DesignTemplateSourceModel,
    DodSemanticsGuardSectionModel,
    ExistingCodebaseConstraintRowModel,
    ForwardFidelitySectionModel,
    NonGoalGuardSectionModel,
    PlanTemplateSourceModel,
    QualityGateGuardSectionModel,
    QualityGateRowModel,
    ReverseFidelitySectionModel,
    RiskClassificationRowModel,
    RootCoverageRowModel,
    SubDocIndexRowModel,
    SunsetClosureChecklistRowModel,
    TaskComposeRowModel,
    TaskTraceRowModel,
    TemporalCompletenessGuardSectionModel,
    TemporaryMechanismIndexRowModel,
    TemporaryMechanismTraceRowModel,
    TraceTemplateSourceModel,
)

SectionRenderer = Callable[[Any], str]


class TemplateRenderError(RuntimeError):
    """Raised when a structured template cannot be rendered."""


@dataclass(frozen=True)
class TemplateSpec:
    model_type: type[BaseModel]
    renderers: dict[str, SectionRenderer]


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


def render_bullets(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items)


def render_inline_list(items: list[str]) -> str:
    return ", ".join(items) if items else "none"


def render_acceptance_criteria_rows(
    rows: list[AcceptanceCriteriaRowModel],
) -> str:
    return render_markdown_table(
        [
            "AC ID",
            "EARS Type",
            "Contract Type",
            "Requirement Sentence",
            "Verification Intent",
            "Verification Command",
        ],
        [
            [
                row.ac_id,
                row.ears_type,
                row.contract_type,
                row.requirement_sentence,
                row.verification_intent,
                row.verification_command,
            ]
            for row in rows
        ],
    )


def render_clarifications(rows: list[ClarificationRowModel]) -> str:
    return render_markdown_table(
        ["Question", "Answer / Assumption", "Impact", "Status"],
        [
            [row.question, row.answer_or_assumption, row.impact, row.status]
            for row in rows
        ],
    )


def render_existing_codebase_constraints(
    rows: list[ExistingCodebaseConstraintRowModel],
) -> str:
    return render_markdown_table(
        [
            "Constraint ID",
            "Source (file/test)",
            "Constraint",
            "Impact on Design",
            "Required Verification",
        ],
        [
            [
                row.constraint_id,
                row.source,
                row.constraint,
                row.impact_on_design,
                row.required_verification,
            ]
            for row in rows
        ],
    )


def render_risk_classification(rows: list[RiskClassificationRowModel]) -> str:
    return render_markdown_table(
        ["Area", "Risk Tier", "Change Rationale"],
        [[row.area, row.risk_tier, row.change_rationale] for row in rows],
    )


def render_boundary_inventory(rows: list[Any]) -> str:
    return render_markdown_table(
        [
            "Boundary",
            "Owns Requirements/AC",
            "Primary Verification Surface",
            "TEMP Lifecycle Group",
            "Parallel Stream",
            "Depends On",
        ],
        [
            [
                row.boundary,
                row.owns_requirements_ac,
                row.primary_verification_surface,
                row.temp_lifecycle_group,
                row.parallel_stream,
                row.depends_on_display,
            ]
            for row in rows
        ],
    )


def render_sub_doc_index(rows: list[SubDocIndexRowModel]) -> str:
    return render_markdown_table(
        ["Sub ID", "File", "Owned Boundary", "Owns Requirements/AC"],
        [
            [row.sub_id, row.file, row.owned_boundary, row.owns_requirements_ac]
            for row in rows
        ],
    )


def render_root_coverage(rows: list[RootCoverageRowModel]) -> str:
    return render_markdown_table(
        ["Root Requirement/AC", "Covered By (Sub ID or Integration)", "Notes"],
        [[row.root_requirement_ac, row.covered_by, row.notes] for row in rows],
    )


def render_temporary_mechanism_index(
    rows: list[TemporaryMechanismIndexRowModel],
) -> str:
    return render_markdown_table(
        ["ID", "Mechanism", "Lifecycle Record", "Status"],
        [[row.id, row.mechanism, row.lifecycle_record, row.status] for row in rows],
    )


def render_sunset_closure_checklist(
    rows: list[SunsetClosureChecklistRowModel],
) -> str:
    return render_markdown_table(
        [
            "ID",
            "Introduced For",
            "Retirement Trigger",
            "Retirement Verification",
            "Removal Scope",
        ],
        [
            [
                row.id,
                row.introduced_for,
                row.retirement_trigger,
                row.retirement_verification,
                row.removal_scope,
            ]
            for row in rows
        ],
    )


def render_decision_log(rows: list[DecisionLogRowModel]) -> str:
    return render_markdown_table(
        ["ADR", "Decision", "Status"],
        [[row.adr, row.decision, row.status] for row in rows],
    )


def render_quality_gates(rows: list[QualityGateRowModel]) -> str:
    return render_markdown_table(
        ["Category", "Command"],
        [[row.category, row.command] for row in rows],
    )


def render_checkpoint_summary(section: CheckpointSummaryTemplateModel) -> str:
    return render_bullets(
        [
            f"Alignment Verdict: {section.alignment_verdict}",
            f"Forward Fidelity: {section.forward_fidelity}",
            f"Reverse Fidelity: {section.reverse_fidelity}",
            f"Non-Goal Guard: {section.non_goal_guard}",
            f"Behavioral Lock Guard: {section.behavioral_lock_guard}",
            f"Temporal Completeness Guard: {section.temporal_completeness_guard}",
            f"Quality Gate Guard: {section.quality_gate_guard}",
            f"Integration Coverage Guard: {section.integration_coverage_guard}",
            f"Risk Classification Guard: {section.risk_classification_guard}",
            f"TEMP Summary: {section.temp_summary}",
            f"Trace Pack: `{section.trace_pack}`",
            f"Compose Pack: `{section.compose_pack}`",
            f"Updated At: `{section.updated_at}`",
        ]
    )


def render_decision_trace(rows: list[DecisionTraceRowModel]) -> str:
    return render_bullets([f"{row.design_atom} -> {row.target}" for row in rows])


def render_design_task_trace_matrix(rows: list[TaskTraceRowModel]) -> str:
    return render_bullets(
        [f"{row.design_atom}: {', '.join(row.tasks)}" for row in rows]
    )


def render_task_design_compose_matrix(rows: list[TaskComposeRowModel]) -> str:
    return render_bullets([f"{row.task}: {', '.join(row.anchors)}" for row in rows])


def render_temporary_mechanism_trace(
    rows: list[TemporaryMechanismTraceRowModel],
) -> str:
    return render_bullets(
        [
            (
                f"{row.temp_id}: introduced_by=[{', '.join(row.introduced_by)}], "
                f"retired_by=[{', '.join(row.retired_by)}], "
                f"retirement_trigger=[{row.retirement_trigger}], "
                f"retirement_verification=[{row.retirement_verification}], "
                f"removal_scope=[{row.removal_scope}], "
                f"closure_source={row.closure_source}, "
                f"record_source={row.record_source}, status={row.status}"
            )
            for row in rows
        ]
    )


def render_ac_ownership_map(rows: list[AcOwnershipMapRowModel]) -> str:
    return render_markdown_table(
        ["AC ID", "Owner Task", "Contributors", "Has RED for AC"],
        [
            [row.ac_id, row.owner_task, row.contributors, row.has_red_for_ac]
            for row in rows
        ],
    )


def render_behavioral_lock_map(rows: list[BehavioralLockMapRowModel]) -> str:
    return render_bullets(
        [
            (
                f"{row.lock_id} ({', '.join(f'`{anchor}`' for anchor in row.anchors)}): "
                f'intent="{row.intent}", '
                f"negative_checks=[{', '.join(row.negative_checks)}], "
                f"positive_boundary_checks=[{', '.join(row.positive_boundary_checks)}]"
            )
            for row in rows
        ]
    )


def render_forward_fidelity(section: ForwardFidelitySectionModel) -> str:
    return render_bullets(
        [
            "Coverage ratio (`REQ+AC covered / total REQ+AC`): "
            + f"`{section.requirements_ac_coverage.covered} / {section.requirements_ac_coverage.total}`",
            "Coverage ratio (`DEC covered / total DEC`): "
            + f"`{section.decision_coverage.covered} / {section.decision_coverage.total}`",
            "Invalid DEC-to-ADR mappings: "
            + render_inline_list(section.invalid_dec_to_adr_mappings),
            f"Missing design atoms: {render_inline_list(section.missing_design_atoms)}",
        ]
    )


def render_reverse_fidelity(section: ReverseFidelitySectionModel) -> str:
    return render_bullets(
        [
            f"Orphan tasks (no valid anchors): {render_inline_list(section.orphan_tasks)}",
            "Tasks missing `REQxx/ACxx` in `Satisfied Requirements`: "
            + render_inline_list(section.tasks_missing_satisfied_requirements),
            f"Alignment verdict: {section.alignment_verdict}",
            f"Gaps and actions: {render_inline_list(section.gaps_and_actions)}",
        ]
    )


def render_non_goal_guard(section: NonGoalGuardSectionModel) -> str:
    return render_bullets(
        [
            "Violations against `NONGOALxx`: "
            + render_inline_list(section.violations_against_non_goals)
        ]
    )


def render_dod_semantics_guard(section: DodSemanticsGuardSectionModel) -> str:
    return render_bullets(
        [
            "Tasks with OR-like DoD wording: "
            + render_inline_list(section.tasks_with_or_like_dod_wording),
            "DoD items missing independent verification: "
            + render_inline_list(section.dod_items_missing_independent_verification),
        ]
    )


def render_behavioral_lock_guard(
    section: BehavioralLockGuardSectionModel,
) -> str:
    return render_bullets(
        [
            "Lock atoms missing negative executable checks: "
            + render_inline_list(section.lock_atoms_missing_negative_executable_checks),
            "Runtime-boundary lock atoms missing boundary-level verification: "
            + render_inline_list(
                section.runtime_boundary_lock_atoms_missing_boundary_level_verification
            ),
            f"Verdict: {section.verdict}",
        ]
    )


def render_temporal_completeness_guard(
    section: TemporalCompletenessGuardSectionModel,
) -> str:
    return render_bullets(
        [
            "TEMP entries missing introducing tasks: "
            + render_inline_list(section.temp_entries_missing_introducing_tasks),
            "TEMP entries missing retiring tasks: "
            + render_inline_list(section.temp_entries_missing_retiring_tasks),
            "Retire tasks missing negative fallback-removal verification: "
            + render_inline_list(
                section.retire_tasks_missing_negative_fallback_removal_verification
            ),
            "TEMP entries missing in-doc closure summary (checklist/ledger row): "
            + render_inline_list(section.temp_entries_missing_in_doc_closure_summary),
            "TEMP entries missing closure tuple fields (trigger/verification/removal_scope): "
            + render_inline_list(section.temp_entries_missing_closure_tuple_fields),
            "Open TEMP entries without waiver metadata (`reason`, `deadline`, `owner?`): "
            + render_inline_list(section.open_temp_entries_without_waiver_metadata),
        ]
    )


def render_quality_gate_guard(section: QualityGateGuardSectionModel) -> str:
    return render_bullets(
        [
            f"Quality gates detected in Step 1.7: {section.quality_gates_detected_in_step_1_7}",
            f"`## Quality Gates` present in plan.md: {section.quality_gates_present_in_plan}",
            "Tasks missing quality gate DoD line: "
            + render_inline_list(section.tasks_missing_quality_gate_dod_line),
        ]
    )


def render_compose_reconstructed_design_summary(
    section: ComposeReconstructedDesignSummarySectionModel,
) -> str:
    return render_bullets(section.bullets)


def render_compose_scope_diff(section: ComposeScopeDiffSectionModel) -> str:
    return render_bullets(
        [
            f"Missing from tasks: {render_inline_list(section.missing_from_tasks)}",
            f"Extra in tasks: {render_inline_list(section.extra_in_tasks)}",
            f"Ambiguous mappings: {render_inline_list(section.ambiguous_mappings)}",
            "Open temporary mechanisms (`TEMPxx`): "
            + render_inline_list(section.open_temporary_mechanisms),
        ]
    )


def render_compose_alignment_verdict(
    section: ComposeAlignmentVerdictSectionModel,
) -> str:
    return render_bullets(
        [
            section.verdict,
            f"Required fixes: {render_inline_list(section.required_fixes)}",
        ]
    )


TEMPLATE_SPECS = {
    "design-templates.md.j2": TemplateSpec(
        model_type=DesignTemplateSourceModel,
        renderers={
            "clarifications": render_clarifications,
            "existing_codebase_constraints": render_existing_codebase_constraints,
            "risk_classification": render_risk_classification,
            "boundary_inventory": render_boundary_inventory,
            "sub_doc_index": render_sub_doc_index,
            "root_coverage": render_root_coverage,
            "temporary_mechanism_index": render_temporary_mechanism_index,
            "sunset_closure_checklist": render_sunset_closure_checklist,
            "decision_log": render_decision_log,
            "acceptance_criteria": render_acceptance_criteria_rows,
            "sub_local_acceptance_criteria": render_acceptance_criteria_rows,
        },
    ),
    "plan-templates.md.j2": TemplateSpec(
        model_type=PlanTemplateSourceModel,
        renderers={
            "quality_gates": render_quality_gates,
            "checkpoint_summary": render_checkpoint_summary,
        },
    ),
    "trace-templates.md.j2": TemplateSpec(
        model_type=TraceTemplateSourceModel,
        renderers={
            "decision_trace": render_decision_trace,
            "design_task_trace_matrix": render_design_task_trace_matrix,
            "task_design_compose_matrix": render_task_design_compose_matrix,
            "temporary_mechanism_trace": render_temporary_mechanism_trace,
            "ac_ownership_map": render_ac_ownership_map,
            "behavioral_lock_map": render_behavioral_lock_map,
            "forward_fidelity": render_forward_fidelity,
            "reverse_fidelity": render_reverse_fidelity,
            "non_goal_guard": render_non_goal_guard,
            "dod_semantics_guard": render_dod_semantics_guard,
            "behavioral_lock_guard": render_behavioral_lock_guard,
            "temporal_completeness_guard": render_temporal_completeness_guard,
            "quality_gate_guard": render_quality_gate_guard,
            "compose_reconstructed_design_summary": render_compose_reconstructed_design_summary,
            "compose_scope_diff": render_compose_scope_diff,
            "compose_alignment_verdict": render_compose_alignment_verdict,
        },
    ),
}


def fragments_path_for_template(template_path: Path) -> Path:
    if not template_path.name.endswith(".md.j2"):
        raise TemplateRenderError(f"expected .md.j2 template: {template_path}")
    return template_path.with_name(
        template_path.name.removesuffix(".md.j2") + ".fragments.json"
    )


def load_fragments(template_path: Path) -> BaseModel:
    fragments_path = fragments_path_for_template(template_path)
    if not fragments_path.is_file():
        raise TemplateRenderError(
            f"missing fragments file for {template_path.name}: {fragments_path}"
        )

    spec = TEMPLATE_SPECS.get(template_path.name)
    if spec is None:
        raise TemplateRenderError(f"unsupported template: {template_path.name}")

    try:
        payload = json.loads(fragments_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise TemplateRenderError(
            f"invalid JSON in {fragments_path}: {exc.msg} (line {exc.lineno}, column {exc.colno})"
        ) from exc

    try:
        return spec.model_type.model_validate(payload)
    except ValidationError as exc:
        raise TemplateRenderError(
            f"invalid fragments for {template_path.name}: {exc}"
        ) from exc


def render_structured_template(template_path: Path) -> str:
    spec = TEMPLATE_SPECS.get(template_path.name)
    if spec is None:
        raise TemplateRenderError(f"unsupported template: {template_path.name}")

    fragments = load_fragments(template_path)
    rendered_fragments = {
        slug: renderer(getattr(fragments, slug))
        for slug, renderer in spec.renderers.items()
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
