#!/usr/bin/env python3
"""Shared Pydantic models for skills build and review tooling."""

from __future__ import annotations

import re
from typing import Annotated, Literal

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
RISK_TIERS = {"Critical", "Sensitive", "Standard"}
SUMMARY_VERDICTS = {"PASS", "FAIL", "N/A"}
ALLOWED_GRANULARITY_CARDS = {1, 2, 3, 5, 8}


def normalize_token(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().casefold())


def parse_dependencies_field(value: str) -> tuple[str, ...]:
    if normalize_token(value) in NONE_TOKENS:
        return ()
    parts = [part.strip() for part in re.split(r"[;,]", value) if part.strip()]
    return tuple(parts)


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


class TableFragmentModel(StrictModel):
    kind: Literal["table"]
    headers: list[str]
    rows: list[list[str]]

    @field_validator("headers")
    @classmethod
    def validate_headers(cls, values: list[str]) -> list[str]:
        if not values:
            raise ValueError("headers must not be empty")
        if any(not value for value in values):
            raise ValueError("headers must contain only non-empty strings")
        return values

    @field_validator("rows")
    @classmethod
    def validate_rows(
        cls, values: list[list[str]], info: ValidationInfo
    ) -> list[list[str]]:
        if any(not row for row in values):
            raise ValueError("rows must not contain empty rows")
        for row in values:
            if any(not value for value in row):
                raise ValueError("rows must contain only non-empty strings")
        return values

    @field_validator("rows")
    @classmethod
    def validate_column_counts(
        cls, values: list[list[str]], info: ValidationInfo
    ) -> list[list[str]]:
        headers = info.data.get("headers", [])
        for row in values:
            if len(row) != len(headers):
                raise ValueError("every row must match the header column count")
        return values


class BulletsFragmentModel(StrictModel):
    kind: Literal["bullets"]
    items: list[str]

    @field_validator("items")
    @classmethod
    def validate_items(cls, values: list[str]) -> list[str]:
        if not values:
            raise ValueError("items must not be empty")
        if any(not value for value in values):
            raise ValueError("items must contain only non-empty strings")
        return values


MarkdownFragmentModel = Annotated[
    TableFragmentModel | BulletsFragmentModel,
    Field(discriminator="kind"),
]


class TemplateFragmentsFileModel(RootModel[dict[str, MarkdownFragmentModel]]):
    model_config = ConfigDict(str_strip_whitespace=True)


class ClarificationRowModel(StrictModel):
    question: str
    answer_or_assumption: str
    impact: str
    status: Literal["resolved", "assumed"]


class ExistingCodebaseConstraintRowModel(StrictModel):
    constraint_id: str
    source: str
    constraint: str
    impact_on_design: str
    required_verification: str


class RiskClassificationRowModel(StrictModel):
    area: str
    risk_tier: Literal["Critical", "Sensitive", "Standard"]
    change_rationale: str


class BoundaryInventoryRowModel(StrictModel):
    boundary: str
    owns_requirements_ac: str
    primary_verification_surface: str
    temp_lifecycle_group: str
    parallel_stream: str
    depends_on: tuple[str, ...] | str

    @field_validator("parallel_stream")
    @classmethod
    def validate_parallel_stream(cls, value: str) -> str:
        normalized = normalize_token(value)
        if normalized not in YES_NO_TOKENS:
            raise ValueError("parallel_stream must be yes or no")
        return "yes" if normalized == "yes" else "no"

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

    @property
    def normalized_boundary(self) -> str:
        return normalize_token(self.owned_boundary)


class RootCoverageRowModel(StrictModel):
    root_requirement_ac: str
    covered_by: str
    notes: str


class TemporaryMechanismIndexRowModel(StrictModel):
    id: str
    mechanism: str
    lifecycle_record: str
    status: str


class SunsetClosureChecklistRowModel(StrictModel):
    id: str
    introduced_for: str
    retirement_trigger: str
    retirement_verification: str
    removal_scope: str


class DecisionLogRowModel(StrictModel):
    adr: str
    decision: str
    status: str


class AcceptanceCriteriaRowModel(StrictModel):
    ac_id: str
    ears_type: str
    contract_type: str
    requirement_sentence: str
    verification_intent: str
    verification_command: str


class QualityGateRowModel(StrictModel):
    category: str
    command: str


class CheckpointSummaryTemplateModel(StrictModel):
    alignment_verdict: str
    forward_fidelity: str
    reverse_fidelity: str
    non_goal_guard: str
    behavioral_lock_guard: str
    temporal_completeness_guard: str
    quality_gate_guard: str
    integration_coverage_guard: str
    risk_classification_guard: str
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
        if not values:
            raise ValueError("tasks must contain at least one task")
        if any(not value for value in values):
            raise ValueError("tasks must contain only non-empty strings")
        return values


class TaskComposeRowModel(StrictModel):
    task: str
    anchors: list[str]

    @field_validator("anchors")
    @classmethod
    def validate_anchors(cls, values: list[str]) -> list[str]:
        if not values:
            raise ValueError("anchors must contain at least one item")
        if any(not value for value in values):
            raise ValueError("anchors must contain only non-empty strings")
        return values


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


class AcOwnershipMapRowModel(StrictModel):
    ac_id: str
    owner_task: str
    contributors: str
    has_red_for_ac: str


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
        if not values:
            raise ValueError(f"{info.field_name} must contain at least one item")
        if any(not value for value in values):
            raise ValueError(f"{info.field_name} must contain only non-empty strings")
        return values


class DesignTemplateFragmentsModel(StrictModel):
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


class PlanTemplateFragmentsModel(StrictModel):
    quality_gates: list[QualityGateRowModel]
    checkpoint_summary: CheckpointSummaryTemplateModel


class TraceTemplateFragmentsModel(StrictModel):
    decision_trace: list[DecisionTraceRowModel]
    design_task_trace_matrix: list[TaskTraceRowModel]
    task_design_compose_matrix: list[TaskComposeRowModel]
    temporary_mechanism_trace: list[TemporaryMechanismTraceRowModel]
    ac_ownership_map: list[AcOwnershipMapRowModel]
    behavioral_lock_map: list[BehavioralLockMapRowModel]


class ReviewSummaryModel(StrictModel):
    forward_fidelity: Literal["PASS", "FAIL"]
    reverse_fidelity: Literal["PASS", "FAIL"]
    round_trip: Literal["PASS", "FAIL"]
    behavioral_lock: Literal["PASS", "FAIL"]
    negative_path: Literal["PASS", "FAIL"]
    temporal: Literal["PASS", "FAIL"]
    traceability: Literal["PASS", "FAIL"]
    scope: Literal["PASS", "FAIL"]
    testability: Literal["PASS", "FAIL"]
    execution_readiness: Literal["PASS", "FAIL"]
    integration_coverage: Literal["PASS", "FAIL", "N/A"]
    risk_classification: Literal["PASS", "FAIL", "N/A"]


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
