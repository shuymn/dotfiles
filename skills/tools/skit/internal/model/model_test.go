package model

import (
	"bytes"
	"encoding/json"
	"os"
	"path/filepath"
	"testing"
)

// skillsSrcPath returns the path to skills/src/ relative to this test file's package.
// go test runs with CWD = package directory (internal/model/).
func skillsSrcPath(parts ...string) string {
	base := filepath.Join("..", "..", "..", "..", "src")
	return filepath.Join(append([]string{base}, parts...)...)
}

func loadJSON(t *testing.T, path string) []byte {
	t.Helper()
	data, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("readFile %s: %v", path, err)
	}
	return data
}

func loadDesignTemplateSource(data []byte) (*DesignTemplateSource, error) {
	dec := json.NewDecoder(bytes.NewReader(data))
	dec.DisallowUnknownFields()
	var v DesignTemplateSource
	if err := dec.Decode(&v); err != nil {
		return nil, err
	}
	if err := v.Validate(); err != nil {
		return nil, err
	}
	return &v, nil
}

func loadPlanTemplateSource(data []byte) (*PlanTemplateSource, error) {
	dec := json.NewDecoder(bytes.NewReader(data))
	dec.DisallowUnknownFields()
	var v PlanTemplateSource
	if err := dec.Decode(&v); err != nil {
		return nil, err
	}
	if err := v.Validate(); err != nil {
		return nil, err
	}
	return &v, nil
}

func loadTraceTemplateSource(data []byte) (*TraceTemplateSource, error) {
	dec := json.NewDecoder(bytes.NewReader(data))
	dec.DisallowUnknownFields()
	var v TraceTemplateSource
	if err := dec.Decode(&v); err != nil {
		return nil, err
	}
	if err := v.Validate(); err != nil {
		return nil, err
	}
	return &v, nil
}

func TestDesignTemplateSourceAcceptsSemanticFragments(t *testing.T) {
	data := loadJSON(t, skillsSrcPath("design-doc", "references", "design-templates.fragments.json"))
	m, err := loadDesignTemplateSource(data)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	if len(m.BoundaryInventory) == 0 {
		t.Fatal("expected non-empty boundary_inventory")
	}
	want := []string{"[Boundary names]"}
	got := m.BoundaryInventory[0].DependsOn
	if len(got) != len(want) || got[0] != want[0] {
		t.Errorf("boundary_inventory[0].DependsOn = %v, want %v", got, want)
	}

	if len(m.AcceptanceCriteria) == 0 {
		t.Fatal("expected non-empty acceptance_criteria")
	}
	if m.AcceptanceCriteria[0].AcID != "AC01" {
		t.Errorf("acceptance_criteria[0].AcID = %q, want %q", m.AcceptanceCriteria[0].AcID, "AC01")
	}
}

func TestDesignTemplateSourceRejectsBlankRequiredCell(t *testing.T) {
	data := loadJSON(t, skillsSrcPath("design-doc", "references", "design-templates.fragments.json"))

	var raw map[string]any
	if err := json.Unmarshal(data, &raw); err != nil {
		t.Fatal(err)
	}
	acs := raw["acceptance_criteria"].([]any)
	acs[0].(map[string]any)["ac_id"] = ""
	modified, _ := json.Marshal(raw)

	_, err := loadDesignTemplateSource(modified)
	if err == nil {
		t.Fatal("expected error for blank ac_id, got nil")
	}
}

func TestPlanTemplateSourceRejectsLegacyGenericFragmentShape(t *testing.T) {
	// quality_gates as object instead of array — JSON type mismatch.
	raw := `{
		"quality_gates": {"kind": "table", "headers": ["Category", "Command"], "rows": [["test", "` + "`uv run pytest`" + `"]]},
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
			"trace_pack": "docs/plans/<topic>/plan.trace.md",
			"compose_pack": "docs/plans/<topic>/plan.compose.md",
			"updated_at": "YYYY-MM-DD"
		}
	}`
	_, err := loadPlanTemplateSource([]byte(raw))
	if err == nil {
		t.Fatal("expected error for legacy generic fragment shape, got nil")
	}
}

func TestPlanTemplateSourceRejectsBlankRequiredCell(t *testing.T) {
	data := loadJSON(t, skillsSrcPath("decompose-plan", "references", "plan-templates.fragments.json"))

	var raw map[string]any
	if err := json.Unmarshal(data, &raw); err != nil {
		t.Fatal(err)
	}
	gates := raw["quality_gates"].([]any)
	gates[0].(map[string]any)["category"] = ""
	modified, _ := json.Marshal(raw)

	_, err := loadPlanTemplateSource(modified)
	if err == nil {
		t.Fatal("expected error for blank category, got nil")
	}
}

func TestPlanTemplateSourceKeepsCheckpointPackValues(t *testing.T) {
	data := loadJSON(t, skillsSrcPath("decompose-plan", "references", "plan-templates.fragments.json"))
	m, err := loadPlanTemplateSource(data)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if m.CheckpointSummary.TracePack != "docs/plans/<topic>/plan.trace.md" {
		t.Errorf("trace_pack = %q", m.CheckpointSummary.TracePack)
	}
	if m.CheckpointSummary.ComposePack != "docs/plans/<topic>/plan.compose.md" {
		t.Errorf("compose_pack = %q", m.CheckpointSummary.ComposePack)
	}
	if m.CheckpointSummary.UpdatedAt != "YYYY-MM-DD" {
		t.Errorf("updated_at = %q", m.CheckpointSummary.UpdatedAt)
	}
}

func TestTraceTemplateSourceAcceptsSemanticFragments(t *testing.T) {
	data := loadJSON(t, skillsSrcPath("decompose-plan", "references", "trace-templates.fragments.json"))
	m, err := loadTraceTemplateSource(data)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if m.ForwardFidelity.RequirementsACCoverage.Covered != "X" {
		t.Errorf("forward_fidelity.requirements_ac_coverage.covered = %q, want X", m.ForwardFidelity.RequirementsACCoverage.Covered)
	}
	if len(m.ComposeAlignmentVerdict.RequiredFixes) == 0 || m.ComposeAlignmentVerdict.RequiredFixes[0] != "[if FAIL]" {
		t.Errorf("compose_alignment_verdict.required_fixes[0] = %v, want [if FAIL]", m.ComposeAlignmentVerdict.RequiredFixes)
	}
	if len(m.TemporaryMechanismTrace) == 0 || m.TemporaryMechanismTrace[0].RetirementTrigger != "objective condition" {
		t.Errorf("temporary_mechanism_trace[0].retirement_trigger = %q, want objective condition", m.TemporaryMechanismTrace[0].RetirementTrigger)
	}
}

func TestTraceTemplateSourceRejectsBlankRequiredCell(t *testing.T) {
	data := loadJSON(t, skillsSrcPath("decompose-plan", "references", "trace-templates.fragments.json"))

	var raw map[string]any
	if err := json.Unmarshal(data, &raw); err != nil {
		t.Fatal(err)
	}
	acMap := raw["ac_ownership_map"].([]any)
	acMap[0].(map[string]any)["owner_task"] = ""
	modified, _ := json.Marshal(raw)

	_, err := loadTraceTemplateSource(modified)
	if err == nil {
		t.Fatal("expected error for blank owner_task, got nil")
	}
}

func TestTraceTemplateSourceRejectsEmptyRequiredBulletSections(t *testing.T) {
	sections := []string{
		"decision_trace",
		"design_task_trace_matrix",
		"task_design_compose_matrix",
		"temporary_mechanism_trace",
		"behavioral_lock_map",
	}

	data := loadJSON(t, skillsSrcPath("decompose-plan", "references", "trace-templates.fragments.json"))

	for _, section := range sections {
		var raw map[string]any
		if err := json.Unmarshal(data, &raw); err != nil {
			t.Fatal(err)
		}
		raw[section] = []any{}
		modified, _ := json.Marshal(raw)

		_, err := loadTraceTemplateSource(modified)
		if err == nil {
			t.Errorf("section %q: expected error for empty list, got nil", section)
		}
	}
}

func TestBoundaryInventoryRowRequiresYesOrNo(t *testing.T) {
	r := BoundaryInventoryRow{
		Boundary:                   "API",
		OwnsRequirementsAC:         "AC01",
		PrimaryVerificationSurface: "pytest",
		TempLifecycleGroup:         "none",
		ParallelStream:             "maybe",
		DependsOn:                  []string{},
	}
	if err := r.Validate(); err == nil {
		t.Fatal("expected error for parallel_stream=maybe, got nil")
	}
}

func TestBoundaryInventoryRowDependsOnDisplay(t *testing.T) {
	cases := []struct {
		dependsOn []string
		want      string
	}{
		{nil, "none"},
		{[]string{}, "none"},
		{[]string{"A"}, "A"},
		{[]string{"A", "B"}, "A, B"},
	}
	for _, tc := range cases {
		r := BoundaryInventoryRow{DependsOn: tc.dependsOn}
		if got := r.DependsOnDisplay(); got != tc.want {
			t.Errorf("DependsOnDisplay(%v) = %q, want %q", tc.dependsOn, got, tc.want)
		}
	}
}

func TestSkillConfigRejectsDuplicates(t *testing.T) {
	s := SkillConfig{CommonScripts: []string{"foo.sh", "foo.sh"}}
	if err := s.Validate(); err == nil {
		t.Fatal("expected error for duplicate common_scripts, got nil")
	}
}

func TestSkillConfigRejectsEmptyItem(t *testing.T) {
	s := SkillConfig{CommonScripts: []string{"foo.sh", ""}}
	if err := s.Validate(); err == nil {
		t.Fatal("expected error for empty common_scripts item, got nil")
	}
}

func TestCommonDependencySpecRejectsEmptyDependency(t *testing.T) {
	c := CommonDependencySpec{Dependencies: []string{"ok.sh", ""}, InstallPath: "scripts/ok.sh"}
	if err := c.Validate(); err == nil {
		t.Fatal("expected error for empty dependency, got nil")
	}
}
