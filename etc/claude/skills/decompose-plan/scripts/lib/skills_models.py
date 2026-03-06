#!/usr/bin/env python3
"""Shared Pydantic models for skills build and review tooling."""

from __future__ import annotations

import re
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    RootModel,
    ValidationInfo,
    field_validator,
)

NONE_TOKENS = {"", "-", "none", "n/a", "na"}
YES_NO_TOKENS = {"yes", "no"}
SUMMARY_VERDICTS = {"PASS", "FAIL", "N/A"}
ALLOWED_GRANULARITY_CARDS = {1, 2, 3, 5, 8}
PASS_FAIL_VERDICTS = ("PASS", "FAIL")
PASS_FAIL_NA_VERDICTS = ("PASS", "FAIL", "N/A")

PassFailVerdict = Literal["PASS", "FAIL"]
PassFailNaVerdict = Literal["PASS", "FAIL", "N/A"]
PassFailTemplate = Literal["PASS | FAIL"]
PassFailNaTemplate = Literal["PASS | FAIL | N/A"]
RiskClassificationGuardTemplate = Literal[
    "PASS | FAIL | N/A (greenfield without Critical-domain changes)"
]


def normalize_token(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().casefold())


def parse_dependencies_field(value: str) -> tuple[str, ...]:
    if normalize_token(value) in NONE_TOKENS:
        return ()
    parts = [part.strip() for part in re.split(r"[;,]", value) if part.strip()]
    return tuple(parts)


def validate_non_empty_string_list(
    values: list[str], *, field_name: str, allow_empty: bool = False
) -> list[str]:
    if not values and not allow_empty:
        raise ValueError(f"{field_name} must contain at least one item")
    if any(not value for value in values):
        raise ValueError(f"{field_name} must contain only non-empty strings")
    return values


def validate_non_empty_string(value: str, *, field_name: str) -> str:
    if not value:
        raise ValueError(f"{field_name} must be a non-empty string")
    return value


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class SkillConfigModel(StrictModel):
    common_scripts: list[str]

    @field_validator("common_scripts")
    @classmethod
    def validate_common_scripts(cls, values: list[str]) -> list[str]:
        if not values:
            return values
        seen: set[str] = set()
        result: list[str] = []
        for value in values:
            if not value:
                raise ValueError("common_scripts items must be non-empty strings")
            if value in seen:
                raise ValueError(f"duplicate common_scripts entry: {value}")
            seen.add(value)
            result.append(value)
        return result


class CommonDependencySpecModel(StrictModel):
    dependencies: list[str]
    install_path: str

    @field_validator("dependencies")
    @classmethod
    def validate_dependencies(cls, values: list[str]) -> list[str]:
        if any(not value for value in values):
            raise ValueError("dependencies must contain only non-empty strings")
        return values


class CommonDependencyGraphModel(RootModel[dict[str, CommonDependencySpecModel]]):
    model_config = ConfigDict(str_strip_whitespace=True)


class ManagedSkillsManifestModel(StrictModel):
    version: int
    source_root: str
    skills: list[str]

    @field_validator("skills")
    @classmethod
    def validate_skills(cls, values: list[str]) -> list[str]:
        if any(not value for value in values):
            raise ValueError("skills must contain only non-empty strings")
        return values


class ClarificationRowModel(StrictModel):
    question: str
    answer_or_assumption: str
    impact: str
    status: Literal["resolved", "assumed"]

    @field_validator("question", "answer_or_assumption", "impact")
    @classmethod
    def validate_strings(cls, value: str, info: ValidationInfo) -> str:
        return validate_non_empty_string(value, field_name=info.field_name)


class ExistingCodebaseConstraintRowModel(StrictModel):
    constraint_id: str
    source: str
    constraint: str
    impact_on_design: str
    required_verification: str

    @field_validator(
        "constraint_id",
        "source",
        "constraint",
        "impact_on_design",
        "required_verification",
    )
    @classmethod
    def validate_strings(cls, value: str, info: ValidationInfo) -> str:
        return validate_non_empty_string(value, field_name=info.field_name)


class RiskClassificationRowModel(StrictModel):
    area: str
    risk_tier: Literal["Critical", "Sensitive", "Standard"]
    change_rationale: str

    @field_validator("area", "change_rationale")
    @classmethod
    def validate_strings(cls, value: str, info: ValidationInfo) -> str:
        return validate_non_empty_string(value, field_name=info.field_name)


class BoundaryInventoryRowModel(StrictModel):
    boundary: str
    owns_requirements_ac: str
    primary_verification_surface: str
    temp_lifecycle_group: str
    parallel_stream: str
    depends_on: tuple[str, ...]

    @field_validator("parallel_stream")
    @classmethod
    def validate_parallel_stream(cls, value: str) -> str:
        normalized = normalize_token(value)
        if normalized not in YES_NO_TOKENS:
            raise ValueError("parallel_stream must be yes or no")
        return "yes" if normalized == "yes" else "no"

    @field_validator(
        "boundary",
        "owns_requirements_ac",
        "primary_verification_surface",
        "temp_lifecycle_group",
    )
    @classmethod
    def validate_strings(cls, value: str, info: ValidationInfo) -> str:
        return validate_non_empty_string(value, field_name=info.field_name)

    @field_validator("depends_on", mode="before")
    @classmethod
    def normalize_dependencies(
        cls, value: tuple[str, ...] | list[str] | str
    ) -> tuple[str, ...]:
        if isinstance(value, tuple):
            return value
        if isinstance(value, list):
            return tuple(item for item in value if item)
        if isinstance(value, str):
            return parse_dependencies_field(value)
        raise TypeError("depends_on must be a string or list of strings")

    @property
    def depends_on_display(self) -> str:
        return ", ".join(self.depends_on) if self.depends_on else "none"

    @property
    def normalized_boundary(self) -> str:
        return normalize_token(self.boundary)

    @property
    def is_owned(self) -> bool:
        owns = normalize_token(self.owns_requirements_ac)
        return owns not in NONE_TOKENS and owns != "integration-only"

    @property
    def is_parallel(self) -> bool:
        return normalize_token(self.parallel_stream) == "yes"


class SubDocIndexRowModel(StrictModel):
    sub_id: str
    file: str
    owned_boundary: str
    owns_requirements_ac: str

    @field_validator("sub_id", "file", "owned_boundary", "owns_requirements_ac")
    @classmethod
    def validate_strings(cls, value: str, info: ValidationInfo) -> str:
        return validate_non_empty_string(value, field_name=info.field_name)

    @property
    def normalized_boundary(self) -> str:
        return normalize_token(self.owned_boundary)


class RootCoverageRowModel(StrictModel):
    root_requirement_ac: str
    covered_by: str
    notes: str

    @field_validator("root_requirement_ac", "covered_by", "notes")
    @classmethod
    def validate_strings(cls, value: str, info: ValidationInfo) -> str:
        return validate_non_empty_string(value, field_name=info.field_name)


class TemporaryMechanismIndexRowModel(StrictModel):
    id: str
    mechanism: str
    lifecycle_record: str
    status: str

    @field_validator("id", "mechanism", "lifecycle_record", "status")
    @classmethod
    def validate_strings(cls, value: str, info: ValidationInfo) -> str:
        return validate_non_empty_string(value, field_name=info.field_name)


class SunsetClosureChecklistRowModel(StrictModel):
    id: str
    introduced_for: str
    retirement_trigger: str
    retirement_verification: str
    removal_scope: str

    @field_validator(
        "id",
        "introduced_for",
        "retirement_trigger",
        "retirement_verification",
        "removal_scope",
    )
    @classmethod
    def validate_strings(cls, value: str, info: ValidationInfo) -> str:
        return validate_non_empty_string(value, field_name=info.field_name)


class DecisionLogRowModel(StrictModel):
    adr: str
    decision: str
    status: str

    @field_validator("adr", "decision", "status")
    @classmethod
    def validate_strings(cls, value: str, info: ValidationInfo) -> str:
        return validate_non_empty_string(value, field_name=info.field_name)


class AcceptanceCriteriaRowModel(StrictModel):
    ac_id: str
    ears_type: str
    contract_type: str
    requirement_sentence: str
    verification_intent: str
    verification_command: str

    @field_validator(
        "ac_id",
        "ears_type",
        "contract_type",
        "requirement_sentence",
        "verification_intent",
        "verification_command",
    )
    @classmethod
    def validate_strings(cls, value: str, info: ValidationInfo) -> str:
        return validate_non_empty_string(value, field_name=info.field_name)


class QualityGateRowModel(StrictModel):
    category: str
    command: str

    @field_validator("category", "command")
    @classmethod
    def validate_strings(cls, value: str, info: ValidationInfo) -> str:
        return validate_non_empty_string(value, field_name=info.field_name)


class CheckpointSummaryTemplateModel(StrictModel):
    alignment_verdict: PassFailTemplate
    forward_fidelity: PassFailTemplate
    reverse_fidelity: PassFailTemplate
    non_goal_guard: PassFailTemplate
    behavioral_lock_guard: PassFailTemplate
    temporal_completeness_guard: PassFailTemplate
    quality_gate_guard: PassFailTemplate
    integration_coverage_guard: PassFailNaTemplate
    risk_classification_guard: RiskClassificationGuardTemplate
    temp_summary: str
    trace_pack: str
    compose_pack: str
    updated_at: str


class DecisionTraceRowModel(StrictModel):
    design_atom: str
    target: str


class TaskTraceRowModel(StrictModel):
    design_atom: str
    tasks: list[str]

    @field_validator("tasks")
    @classmethod
    def validate_tasks(cls, values: list[str]) -> list[str]:
        return validate_non_empty_string_list(values, field_name="tasks")


class TaskComposeRowModel(StrictModel):
    task: str
    anchors: list[str]

    @field_validator("anchors")
    @classmethod
    def validate_anchors(cls, values: list[str]) -> list[str]:
        return validate_non_empty_string_list(values, field_name="anchors")


class TemporaryMechanismTraceRowModel(StrictModel):
    temp_id: str
    introduced_by: list[str]
    retired_by: list[str]
    retirement_trigger: str
    retirement_verification: str
    removal_scope: str
    closure_source: str
    record_source: str
    status: str

    @field_validator("introduced_by", "retired_by")
    @classmethod
    def validate_task_lists(cls, values: list[str], info: ValidationInfo) -> list[str]:
        return validate_non_empty_string_list(values, field_name=info.field_name)


class AcOwnershipMapRowModel(StrictModel):
    ac_id: str
    owner_task: str
    contributors: str
    has_red_for_ac: str

    @field_validator("ac_id", "owner_task", "contributors", "has_red_for_ac")
    @classmethod
    def validate_strings(cls, value: str, info: ValidationInfo) -> str:
        return validate_non_empty_string(value, field_name=info.field_name)


class BehavioralLockMapRowModel(StrictModel):
    lock_id: str
    anchors: list[str]
    intent: str
    negative_checks: list[str]
    positive_boundary_checks: list[str]

    @field_validator("anchors", "negative_checks", "positive_boundary_checks")
    @classmethod
    def validate_string_lists(
        cls, values: list[str], info: ValidationInfo
    ) -> list[str]:
        return validate_non_empty_string_list(values, field_name=info.field_name)


class CoverageCountsModel(StrictModel):
    covered: str
    total: str


class ForwardFidelitySectionModel(StrictModel):
    requirements_ac_coverage: CoverageCountsModel
    decision_coverage: CoverageCountsModel
    invalid_dec_to_adr_mappings: list[str]
    missing_design_atoms: list[str]

    @field_validator("invalid_dec_to_adr_mappings", "missing_design_atoms")
    @classmethod
    def validate_lists(cls, values: list[str], info: ValidationInfo) -> list[str]:
        return validate_non_empty_string_list(values, field_name=info.field_name)


class ReverseFidelitySectionModel(StrictModel):
    orphan_tasks: list[str]
    tasks_missing_satisfied_requirements: list[str]
    alignment_verdict: PassFailTemplate
    gaps_and_actions: list[str]

    @field_validator(
        "orphan_tasks", "tasks_missing_satisfied_requirements", "gaps_and_actions"
    )
    @classmethod
    def validate_lists(cls, values: list[str], info: ValidationInfo) -> list[str]:
        return validate_non_empty_string_list(values, field_name=info.field_name)


class NonGoalGuardSectionModel(StrictModel):
    violations_against_non_goals: list[str]

    @field_validator("violations_against_non_goals")
    @classmethod
    def validate_lists(cls, values: list[str]) -> list[str]:
        return validate_non_empty_string_list(
            values, field_name="violations_against_non_goals"
        )


class DodSemanticsGuardSectionModel(StrictModel):
    tasks_with_or_like_dod_wording: list[str]
    dod_items_missing_independent_verification: list[str]

    @field_validator(
        "tasks_with_or_like_dod_wording",
        "dod_items_missing_independent_verification",
    )
    @classmethod
    def validate_lists(cls, values: list[str], info: ValidationInfo) -> list[str]:
        return validate_non_empty_string_list(values, field_name=info.field_name)


class BehavioralLockGuardSectionModel(StrictModel):
    lock_atoms_missing_negative_executable_checks: list[str]
    runtime_boundary_lock_atoms_missing_boundary_level_verification: list[str]
    verdict: PassFailTemplate

    @field_validator(
        "lock_atoms_missing_negative_executable_checks",
        "runtime_boundary_lock_atoms_missing_boundary_level_verification",
    )
    @classmethod
    def validate_lists(cls, values: list[str], info: ValidationInfo) -> list[str]:
        return validate_non_empty_string_list(values, field_name=info.field_name)


class TemporalCompletenessGuardSectionModel(StrictModel):
    temp_entries_missing_introducing_tasks: list[str]
    temp_entries_missing_retiring_tasks: list[str]
    retire_tasks_missing_negative_fallback_removal_verification: list[str]
    temp_entries_missing_in_doc_closure_summary: list[str]
    temp_entries_missing_closure_tuple_fields: list[str]
    open_temp_entries_without_waiver_metadata: list[str]

    @field_validator(
        "temp_entries_missing_introducing_tasks",
        "temp_entries_missing_retiring_tasks",
        "retire_tasks_missing_negative_fallback_removal_verification",
        "temp_entries_missing_in_doc_closure_summary",
        "temp_entries_missing_closure_tuple_fields",
        "open_temp_entries_without_waiver_metadata",
    )
    @classmethod
    def validate_lists(cls, values: list[str], info: ValidationInfo) -> list[str]:
        return validate_non_empty_string_list(values, field_name=info.field_name)


class QualityGateGuardSectionModel(StrictModel):
    quality_gates_detected_in_step_1_7: str
    quality_gates_present_in_plan: str
    tasks_missing_quality_gate_dod_line: list[str]

    @field_validator("tasks_missing_quality_gate_dod_line")
    @classmethod
    def validate_lists(cls, values: list[str]) -> list[str]:
        return validate_non_empty_string_list(
            values, field_name="tasks_missing_quality_gate_dod_line"
        )


class ComposeReconstructedDesignSummarySectionModel(StrictModel):
    bullets: list[str]

    @field_validator("bullets")
    @classmethod
    def validate_bullets(cls, values: list[str]) -> list[str]:
        return validate_non_empty_string_list(values, field_name="bullets")


class ComposeScopeDiffSectionModel(StrictModel):
    missing_from_tasks: list[str]
    extra_in_tasks: list[str]
    ambiguous_mappings: list[str]
    open_temporary_mechanisms: list[str]

    @field_validator(
        "missing_from_tasks",
        "extra_in_tasks",
        "ambiguous_mappings",
        "open_temporary_mechanisms",
    )
    @classmethod
    def validate_lists(cls, values: list[str], info: ValidationInfo) -> list[str]:
        return validate_non_empty_string_list(values, field_name=info.field_name)


class ComposeAlignmentVerdictSectionModel(StrictModel):
    verdict: PassFailTemplate
    required_fixes: list[str]

    @field_validator("required_fixes")
    @classmethod
    def validate_lists(cls, values: list[str]) -> list[str]:
        return validate_non_empty_string_list(values, field_name="required_fixes")


class DesignTemplateSourceModel(StrictModel):
    clarifications: list[ClarificationRowModel]
    existing_codebase_constraints: list[ExistingCodebaseConstraintRowModel]
    risk_classification: list[RiskClassificationRowModel]
    boundary_inventory: list[BoundaryInventoryRowModel]
    sub_doc_index: list[SubDocIndexRowModel]
    root_coverage: list[RootCoverageRowModel]
    temporary_mechanism_index: list[TemporaryMechanismIndexRowModel]
    sunset_closure_checklist: list[SunsetClosureChecklistRowModel]
    decision_log: list[DecisionLogRowModel]
    acceptance_criteria: list[AcceptanceCriteriaRowModel]
    sub_local_acceptance_criteria: list[AcceptanceCriteriaRowModel]


class PlanTemplateSourceModel(StrictModel):
    quality_gates: list[QualityGateRowModel]
    checkpoint_summary: CheckpointSummaryTemplateModel


class TraceTemplateSourceModel(StrictModel):
    decision_trace: list[DecisionTraceRowModel]
    design_task_trace_matrix: list[TaskTraceRowModel]
    task_design_compose_matrix: list[TaskComposeRowModel]
    temporary_mechanism_trace: list[TemporaryMechanismTraceRowModel]
    ac_ownership_map: list[AcOwnershipMapRowModel]
    behavioral_lock_map: list[BehavioralLockMapRowModel]
    forward_fidelity: ForwardFidelitySectionModel
    reverse_fidelity: ReverseFidelitySectionModel
    non_goal_guard: NonGoalGuardSectionModel
    dod_semantics_guard: DodSemanticsGuardSectionModel
    behavioral_lock_guard: BehavioralLockGuardSectionModel
    temporal_completeness_guard: TemporalCompletenessGuardSectionModel
    quality_gate_guard: QualityGateGuardSectionModel
    compose_reconstructed_design_summary: ComposeReconstructedDesignSummarySectionModel
    compose_scope_diff: ComposeScopeDiffSectionModel
    compose_alignment_verdict: ComposeAlignmentVerdictSectionModel

    @field_validator(
        "decision_trace",
        "design_task_trace_matrix",
        "task_design_compose_matrix",
        "temporary_mechanism_trace",
        "behavioral_lock_map",
    )
    @classmethod
    def validate_required_bullet_sections(
        cls, values: list[object], info: ValidationInfo
    ) -> list[object]:
        if not values:
            raise ValueError(f"{info.field_name} must contain at least one item")
        return values


class ReviewSummaryModel(StrictModel):
    forward_fidelity: PassFailVerdict
    reverse_fidelity: PassFailVerdict
    round_trip: PassFailVerdict
    behavioral_lock: PassFailVerdict
    negative_path: PassFailVerdict
    temporal: PassFailVerdict
    traceability: PassFailVerdict
    scope: PassFailVerdict
    testability: PassFailVerdict
    execution_readiness: PassFailVerdict
    integration_coverage: PassFailNaVerdict
    risk_classification: PassFailNaVerdict


class GranularityPokerRowModel(StrictModel):
    task: str = Field(alias="task")
    objective: str = Field(alias="Objective")
    surface: str = Field(alias="Surface")
    verification: str = Field(alias="Verification")
    rollback: str = Field(alias="Rollback")
    evidence: str = Field(alias="Evidence")

    model_config = ConfigDict(
        extra="forbid", str_strip_whitespace=True, populate_by_name=True
    )


class GranularityCardValuesModel(StrictModel):
    objective: Literal[1, 2, 3, 5, 8]
    surface: Literal[1, 2, 3, 5, 8]
    verification: Literal[1, 2, 3, 5, 8]
    rollback: Literal[1, 2, 3, 5, 8]
