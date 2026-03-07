package workflow

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func runReviewFinalizeCmd(args ...string) (int, map[string]any) {
	rc, stdout, _, err := runCommandOutput(ReviewFinalize(), "", args...)
	if err != nil {
		return 1, map[string]any{"_err": err.Error()}
	}
	return rc, parseJSONResult(stdout)
}

// --- Parse function tests ---

func TestRfExtractSection(t *testing.T) {
	md := "## Summary\n\nSome content here.\n\n## Findings\n\nOther content.\n"
	got := rfExtractSection(md, "Summary")
	if !strings.Contains(got, "Some content here.") {
		t.Errorf("expected summary content, got %q", got)
	}
	got = rfExtractSection(md, "Findings")
	if !strings.Contains(got, "Other content.") {
		t.Errorf("expected findings content, got %q", got)
	}
	got = rfExtractSection(md, "Missing")
	if got != "" {
		t.Errorf("expected empty for missing section, got %q", got)
	}
}

func TestRfExtractSectionAtEnd(t *testing.T) {
	md := "## Only Section\n\nContent at the end."
	got := rfExtractSection(md, "Only Section")
	if got != "Content at the end." {
		t.Errorf("expected 'Content at the end.', got %q", got)
	}
}

func TestRfParseSummaryAllPass(t *testing.T) {
	body := `- Forward Fidelity: PASS
- Reverse Fidelity: PASS
- Round-trip: PASS
- Behavioral Lock: PASS
- Negative Path: PASS
- Temporal: PASS
- Traceability: PASS
- Scope: PASS
- Testability: PASS
- Execution Readiness: PASS
- Integration Coverage: PASS
- Risk Classification: PASS`

	m, errors := rfParseSummary(body)
	if len(errors) != 0 {
		t.Errorf("expected no errors, got %v", errors)
	}
	for _, field := range rfSummaryFields {
		if m[field] != "PASS" {
			t.Errorf("expected PASS for %s, got %s", field, m[field])
		}
	}
}

func TestRfParseSummaryWithNA(t *testing.T) {
	body := `- Forward Fidelity: PASS
- Reverse Fidelity: PASS
- Round-trip: PASS
- Behavioral Lock: PASS
- Negative Path: PASS
- Temporal: PASS
- Traceability: PASS
- Scope: PASS
- Testability: PASS
- Execution Readiness: PASS
- Integration Coverage: N/A (no cross-task deps)
- Risk Classification: N/A`

	m, errors := rfParseSummary(body)
	if len(errors) != 0 {
		t.Errorf("expected no errors, got %v", errors)
	}
	if m["Integration Coverage"] != "N/A" {
		t.Errorf("expected N/A, got %s", m["Integration Coverage"])
	}
}

func TestRfParseSummaryNANotAllowed(t *testing.T) {
	body := "- Forward Fidelity: N/A\n"
	m, errors := rfParseSummary(body)
	if m["Forward Fidelity"] != "FAIL" {
		t.Errorf("expected FAIL for non-NA field, got %s", m["Forward Fidelity"])
	}
	found := false
	for _, e := range errors {
		if strings.Contains(e, "cannot be `N/A`") {
			found = true
		}
	}
	if !found {
		t.Error("expected N/A rejection error")
	}
}

func TestRfParseSummaryMissingField(t *testing.T) {
	body := "- Forward Fidelity: PASS\n"
	_, errors := rfParseSummary(body)
	if len(errors) == 0 {
		t.Error("expected errors for missing fields")
	}
}

func TestRfParseSummaryInvalidVerdict(t *testing.T) {
	body := "- Forward Fidelity: MAYBE\n"
	m, errors := rfParseSummary(body)
	if m["Forward Fidelity"] != "FAIL" {
		t.Errorf("expected FAIL, got %s", m["Forward Fidelity"])
	}
	found := false
	for _, e := range errors {
		if strings.Contains(e, "invalid verdict") {
			found = true
		}
	}
	if !found {
		t.Error("expected invalid verdict error")
	}
}

func TestRfParsePlanTasks(t *testing.T) {
	plan := "### Task 1: Setup\n### Task 2: Build\n### Task 3: Deploy\n"
	tasks := rfParsePlanTasks(plan)
	if len(tasks) != 3 {
		t.Fatalf("expected 3 tasks, got %d", len(tasks))
	}
	if tasks[0] != "Task 1" || tasks[2] != "Task 3" {
		t.Errorf("unexpected tasks: %v", tasks)
	}
}

func TestRfParsePlanTasksEmpty(t *testing.T) {
	tasks := rfParsePlanTasks("# Plan\nNo tasks here.\n")
	if len(tasks) != 0 {
		t.Errorf("expected no tasks, got %v", tasks)
	}
}

func TestRfParsePlanTitle(t *testing.T) {
	tests := []struct {
		name     string
		plan     string
		expected string
	}{
		{"normal", "# Foo Implementation Plan\n", "Foo - Plan Review"},
		{"no suffix", "# Bar Design\n", "Bar Design - Plan Review"},
		{"no title", "No heading\n", "tmp - Plan Review"},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got := rfParsePlanTitle(tt.plan, "/tmp/plan.md")
			if got != tt.expected {
				t.Errorf("expected %q, got %q", tt.expected, got)
			}
		})
	}
}

func TestRfParseDesignPath(t *testing.T) {
	t.Run("from source line", func(t *testing.T) {
		plan := "- **Source**: `docs/design.md`\n"
		got := rfParseDesignPath(plan, "/tmp/plan.md")
		if !strings.HasSuffix(got, "docs/design.md") {
			t.Errorf("expected design.md suffix, got %s", got)
		}
	})

	t.Run("fallback", func(t *testing.T) {
		plan := "No source line.\n"
		got := rfParseDesignPath(plan, "/tmp/plans/plan.md")
		if got != "/tmp/plans/design.md" {
			t.Errorf("expected /tmp/plans/design.md, got %s", got)
		}
	})
}

func TestRfParseGranularityTable(t *testing.T) {
	body := `| Task | Objective | Surface | Verification | Rollback | Evidence |
|------|-----------|---------|--------------|----------|----------|
| Task 1 | 2 | 3 | 2 | 1 | evidence |
| Task 2 | 5 | 3 | 3 | 2 | evidence2 |`

	rows, errors := rfParseGranularityTable(body)
	if len(errors) != 0 {
		t.Errorf("expected no errors, got %v", errors)
	}
	if len(rows) != 2 {
		t.Fatalf("expected 2 rows, got %d", len(rows))
	}
	if rows[0].Task != "Task 1" || rows[0].Objective != "2" {
		t.Errorf("unexpected row: %+v", rows[0])
	}
}

func TestRfParseGranularityTableNoHeader(t *testing.T) {
	body := "| Task 1 | 2 | 3 | 2 | 1 | evidence |"
	_, errors := rfParseGranularityTable(body)
	found := false
	for _, e := range errors {
		if strings.Contains(e, "header is missing") {
			found = true
		}
	}
	if !found {
		t.Error("expected missing header error")
	}
}

func TestRfParseGranularityTableMalformed(t *testing.T) {
	body := `| Task | Objective | Surface | Verification | Rollback | Evidence |
|------|-----------|---------|--------------|----------|----------|
| Task 1 | 2 | 3 |`

	_, errors := rfParseGranularityTable(body)
	found := false
	for _, e := range errors {
		if strings.Contains(e, "Malformed") {
			found = true
		}
	}
	if !found {
		t.Error("expected malformed row error")
	}
}

// --- Scoring tests ---

func TestRfComputeMachineRowsAllPass(t *testing.T) {
	taskIDs := []string{"Task 1", "Task 2"}
	rows := []rfGranularityRow{
		{Task: "Task 1", Objective: "2", Surface: "3", Verification: "2", Rollback: "1", Evidence: "e"},
		{Task: "Task 2", Objective: "1", Surface: "2", Verification: "3", Rollback: "2", Evidence: "e"},
	}
	machineRows, blockers := rfComputeMachineRows(taskIDs, rows, nil)
	if len(machineRows) != 2 {
		t.Fatalf("expected 2 rows, got %d", len(machineRows))
	}
	for _, row := range machineRows {
		if row.Verdict != "PASS" {
			t.Errorf("expected PASS for %s, got %s (%s)", row.Task, row.Verdict, row.Trigger)
		}
	}
	if len(blockers) != 0 {
		t.Errorf("expected no blockers, got %v", blockers)
	}
}

func TestRfComputeMachineRowsMissingRow(t *testing.T) {
	taskIDs := []string{"Task 1", "Task 2"}
	rows := []rfGranularityRow{
		{Task: "Task 1", Objective: "2", Surface: "3", Verification: "2", Rollback: "1", Evidence: "e"},
	}
	machineRows, blockers := rfComputeMachineRows(taskIDs, rows, nil)
	if len(machineRows) != 2 {
		t.Fatalf("expected 2 rows, got %d", len(machineRows))
	}
	if machineRows[1].Verdict != "FAIL" {
		t.Errorf("expected FAIL for missing task, got %s", machineRows[1].Verdict)
	}
	if len(blockers) == 0 {
		t.Error("expected blockers for missing row")
	}
}

func TestRfComputeMachineRowsDuplicateRow(t *testing.T) {
	taskIDs := []string{"Task 1"}
	rows := []rfGranularityRow{
		{Task: "Task 1", Objective: "2", Surface: "3", Verification: "2", Rollback: "1", Evidence: "e"},
		{Task: "Task 1", Objective: "3", Surface: "3", Verification: "2", Rollback: "1", Evidence: "e2"},
	}
	machineRows, _ := rfComputeMachineRows(taskIDs, rows, nil)
	if len(machineRows) != 1 {
		t.Fatalf("expected 1 row, got %d", len(machineRows))
	}
	// Duplicate causes issues but the first row is used for scoring.
	if !strings.Contains(machineRows[0].Trigger, "duplicate draft row") {
		t.Errorf("expected duplicate trigger, got %s", machineRows[0].Trigger)
	}
}

func TestRfComputeMachineRowsUnknownTask(t *testing.T) {
	taskIDs := []string{"Task 1"}
	rows := []rfGranularityRow{
		{Task: "Task 1", Objective: "2", Surface: "3", Verification: "2", Rollback: "1", Evidence: "e"},
		{Task: "Task 99", Objective: "2", Surface: "3", Verification: "2", Rollback: "1", Evidence: "e"},
	}
	machineRows, blockers := rfComputeMachineRows(taskIDs, rows, nil)
	if len(machineRows) != 2 {
		t.Fatalf("expected 2 rows, got %d", len(machineRows))
	}
	found := false
	for _, row := range machineRows {
		if row.Task == "Task 99" && row.Verdict == "FAIL" {
			found = true
		}
	}
	if !found {
		t.Error("expected FAIL row for unknown task")
	}
	if len(blockers) == 0 {
		t.Error("expected blockers for unknown task")
	}
}

func TestRfComputeMachineRowsAggregateExceeded(t *testing.T) {
	taskIDs := []string{"Task 1"}
	rows := []rfGranularityRow{
		{Task: "Task 1", Objective: "5", Surface: "5", Verification: "3", Rollback: "3", Evidence: "e"},
	}
	machineRows, blockers := rfComputeMachineRows(taskIDs, rows, nil)
	if machineRows[0].Verdict != "FAIL" {
		t.Errorf("expected FAIL for aggregate exceeded, got %s", machineRows[0].Verdict)
	}
	if !strings.Contains(machineRows[0].Trigger, "aggregate score exceeded") {
		t.Errorf("expected aggregate trigger, got %s", machineRows[0].Trigger)
	}
	if len(blockers) == 0 {
		t.Error("expected blockers")
	}
}

func TestRfComputeMachineRowsAxisCeiling(t *testing.T) {
	taskIDs := []string{"Task 1"}
	rows := []rfGranularityRow{
		{Task: "Task 1", Objective: "8", Surface: "1", Verification: "1", Rollback: "1", Evidence: "e"},
	}
	machineRows, _ := rfComputeMachineRows(taskIDs, rows, nil)
	if machineRows[0].Verdict != "FAIL" {
		t.Errorf("expected FAIL for axis ceiling, got %s", machineRows[0].Verdict)
	}
	if !strings.Contains(machineRows[0].Trigger, "axis ceiling exceeded") {
		t.Errorf("expected axis ceiling trigger, got %s", machineRows[0].Trigger)
	}
}

func TestRfComputeMachineRowsInvalidCard(t *testing.T) {
	taskIDs := []string{"Task 1"}
	rows := []rfGranularityRow{
		{Task: "Task 1", Objective: "4", Surface: "2", Verification: "2", Rollback: "1", Evidence: "e"},
	}
	machineRows, _ := rfComputeMachineRows(taskIDs, rows, nil)
	if machineRows[0].Verdict != "FAIL" {
		t.Errorf("expected FAIL for invalid card, got %s", machineRows[0].Verdict)
	}
	if !strings.Contains(machineRows[0].Trigger, "invalid") {
		t.Errorf("expected invalid trigger, got %s", machineRows[0].Trigger)
	}
}

// --- Decision tests ---

func TestRfMakeDecisionReasonAllPass(t *testing.T) {
	summaryMap := make(map[string]string)
	for _, f := range rfSummaryFields {
		summaryMap[f] = "PASS"
	}
	rows := []rfMachineRow{{Verdict: "PASS"}}
	proceed, _ := rfMakeDecisionReason(true, summaryMap, rows)
	if proceed != "yes" {
		t.Errorf("expected yes, got %s", proceed)
	}
}

func TestRfMakeDecisionReasonStructuralFail(t *testing.T) {
	summaryMap := make(map[string]string)
	for _, f := range rfSummaryFields {
		summaryMap[f] = "PASS"
	}
	rows := []rfMachineRow{{Verdict: "PASS"}}
	proceed, reason := rfMakeDecisionReason(false, summaryMap, rows)
	if proceed != "no" {
		t.Errorf("expected no, got %s", proceed)
	}
	if !strings.Contains(reason, "structural") {
		t.Errorf("expected structural in reason, got %s", reason)
	}
}

func TestRfMakeDecisionReasonSummaryFail(t *testing.T) {
	summaryMap := make(map[string]string)
	for _, f := range rfSummaryFields {
		summaryMap[f] = "PASS"
	}
	summaryMap["Scope"] = "FAIL"
	rows := []rfMachineRow{{Verdict: "PASS"}}
	proceed, _ := rfMakeDecisionReason(true, summaryMap, rows)
	if proceed != "no" {
		t.Errorf("expected no, got %s", proceed)
	}
}

func TestRfMakeDecisionReasonGranularityFail(t *testing.T) {
	summaryMap := make(map[string]string)
	for _, f := range rfSummaryFields {
		summaryMap[f] = "PASS"
	}
	rows := []rfMachineRow{{Task: "Task 1", Verdict: "FAIL"}}
	proceed, _ := rfMakeDecisionReason(true, summaryMap, rows)
	if proceed != "no" {
		t.Errorf("expected no, got %s", proceed)
	}
}

// --- Build recommendation tests ---

func TestRfBuildRecommendationNoIssues(t *testing.T) {
	got := rfBuildRecommendation(nil, nil, nil, false)
	if got != "-" {
		t.Errorf("expected -, got %q", got)
	}
}

func TestRfBuildRecommendationMissingRow(t *testing.T) {
	got := rfBuildRecommendation([]string{"missing draft row"}, nil, nil, false)
	if !strings.Contains(got, "Add one granularity poker row") {
		t.Errorf("expected missing row recommendation, got %q", got)
	}
}

func TestRfBuildRecommendationDuplicateRow(t *testing.T) {
	got := rfBuildRecommendation([]string{"duplicate draft row"}, nil, nil, false)
	if !strings.Contains(got, "Keep exactly one") {
		t.Errorf("expected duplicate recommendation, got %q", got)
	}
}

func TestRfBuildRecommendationInvalidCard(t *testing.T) {
	got := rfBuildRecommendation([]string{"invalid objective card `4`"}, nil, nil, false)
	if !strings.Contains(got, "Replace invalid") {
		t.Errorf("expected invalid card recommendation, got %q", got)
	}
}

func TestRfBuildRecommendationHighAxes(t *testing.T) {
	got := rfBuildRecommendation(nil, nil, []string{"Objective"}, false)
	if !strings.Contains(got, "Split independently releasable") {
		t.Errorf("expected axis recommendation, got %q", got)
	}
}

func TestRfBuildRecommendationAggregate(t *testing.T) {
	scores := map[string]int{"Objective": 5, "Surface": 5, "Verification": 3, "Rollback": 3}
	got := rfBuildRecommendation(nil, scores, nil, true)
	if got == "-" {
		t.Error("expected non-empty recommendation for aggregate exceeded")
	}
}

// --- Integration tests ---

const rfTestDesign = `# Design

## Acceptance Criteria

| ID | Description |
|----|-------------|
| AC01 | Something works |
`

func rfTestPlan() string {
	return `# Test Implementation Plan

- **Source**: ` + "`design.md`" + `

### Task 1: Setup
- **Dependencies**: none

**DoD**
- Run: ` + "`go test ./...`" + `

### Task 2: Implement
- **Dependencies**: T1

**DoD**
- Run: ` + "`go vet ./...`" + `

## Quality Gates

| Gate | Command |
|------|---------|
| 1 | ` + "`go test ./...`" + ` |

AC01 is referenced here.
`
}

func rfTestDraftAllPass() string {
	return `# Test - Plan Review Draft

## Reviewer Summary

- Forward Fidelity: PASS
- Reverse Fidelity: PASS
- Round-trip: PASS
- Behavioral Lock: PASS
- Negative Path: PASS
- Temporal: PASS
- Traceability: PASS
- Scope: PASS
- Testability: PASS
- Execution Readiness: PASS
- Integration Coverage: N/A
- Risk Classification: N/A

## Granularity Poker

| Task | Objective | Surface | Verification | Rollback | Evidence |
|------|-----------|---------|--------------|----------|----------|
| Task 1 | 2 | 3 | 2 | 1 | evidence |
| Task 2 | 3 | 2 | 2 | 1 | evidence |

## Findings

| ID | Severity | Area | File/Section | Issue | Action |
|----|----------|------|--------------|-------|--------|
| R1 | info | scope | plan.md | Looks good | None |

## Blocking Issues

- None.

## Non-Blocking Improvements

- Consider adding more tests.

## Decision

- Proceed to execute-plan: pending machine finalization
- Reason: awaiting machine check
`
}

func writeRfTestFiles(t *testing.T, design, plan, draft string) (string, string, string, string) {
	t.Helper()
	tmp := t.TempDir()
	designFile := filepath.Join(tmp, "design.md")
	planFile := filepath.Join(tmp, "plan.md")
	draftFile := filepath.Join(tmp, "plan.review.draft.md")
	finalFile := filepath.Join(tmp, "plan.review.md")

	for _, pair := range [][2]string{
		{designFile, design},
		{planFile, plan},
		{draftFile, draft},
	} {
		if err := os.WriteFile(pair[0], []byte(pair[1]), 0644); err != nil {
			t.Fatal(err)
		}
	}
	return planFile, draftFile, finalFile, tmp
}

func TestReviewFinalizeAllPass(t *testing.T) {
	planFile, draftFile, finalFile, _ := writeRfTestFiles(t, rfTestDesign, rfTestPlan(), rfTestDraftAllPass())

	rc, result := runReviewFinalizeCmd(planFile, draftFile, finalFile)
	if rc != 0 {
		t.Logf("result: %v", result)
	}
	if rc != 0 {
		t.Fatalf("expected exit 0, got %d; result: %v", rc, result)
	}
	if result["status"] != "PASS" {
		t.Errorf("expected PASS, got %v", result["status"])
	}
	if result["proceed"] != "yes" {
		t.Errorf("expected proceed=yes, got %v", result["proceed"])
	}

	// Verify final file was written.
	data, err := os.ReadFile(finalFile)
	if err != nil {
		t.Fatalf("final file not written: %v", err)
	}
	content := string(data)
	if !strings.Contains(content, "## Review Metadata") {
		t.Error("expected Review Metadata section")
	}
	if !strings.Contains(content, "## Summary") {
		t.Error("expected Summary section")
	}
	if !strings.Contains(content, "## Decision") {
		t.Error("expected Decision section")
	}
	if !strings.Contains(content, "Proceed to `execute-plan`: yes") {
		t.Error("expected proceed yes in Decision")
	}

	// Verify draft was deleted.
	if _, err := os.Stat(draftFile); !os.IsNotExist(err) {
		t.Error("expected draft file to be deleted")
	}
}

func TestReviewFinalizeSummaryFail(t *testing.T) {
	draft := strings.Replace(rfTestDraftAllPass(), "- Scope: PASS", "- Scope: FAIL", 1)
	planFile, draftFile, finalFile, _ := writeRfTestFiles(t, rfTestDesign, rfTestPlan(), draft)

	rc, result := runReviewFinalizeCmd(planFile, draftFile, finalFile)
	if rc != 1 {
		t.Fatalf("expected exit 1, got %d", rc)
	}
	if result["proceed"] != "no" {
		t.Errorf("expected proceed=no, got %v", result["proceed"])
	}
}

func TestReviewFinalizeGranularityFail(t *testing.T) {
	// Make Task 1 exceed aggregate limit.
	draft := strings.Replace(rfTestDraftAllPass(),
		"| Task 1 | 2 | 3 | 2 | 1 | evidence |",
		"| Task 1 | 5 | 5 | 5 | 5 | evidence |",
		1)
	planFile, draftFile, finalFile, _ := writeRfTestFiles(t, rfTestDesign, rfTestPlan(), draft)

	rc, result := runReviewFinalizeCmd(planFile, draftFile, finalFile)
	if rc != 1 {
		t.Fatalf("expected exit 1, got %d", rc)
	}
	if result["proceed"] != "no" {
		t.Errorf("expected proceed=no, got %v", result["proceed"])
	}
}

func TestReviewFinalizeInvalidArgCount(t *testing.T) {
	rc, result := runReviewFinalizeCmd("only-one", "only-two")
	if rc != 1 {
		t.Fatalf("expected exit 1, got %d", rc)
	}
	if result["code"] != "MISSING_REQUIRED_ARGUMENT" {
		t.Errorf("expected MISSING_REQUIRED_ARGUMENT, got %v", result["code"])
	}
}

func TestReviewFinalizePlanNotFound(t *testing.T) {
	tmp := t.TempDir()
	draftFile := filepath.Join(tmp, "draft.md")
	if err := os.WriteFile(draftFile, []byte("draft"), 0644); err != nil {
		t.Fatal(err)
	}
	rc, result := runReviewFinalizeCmd("/nonexistent/plan.md", draftFile, filepath.Join(tmp, "final.md"))
	if rc != 1 {
		t.Fatalf("expected exit 1, got %d", rc)
	}
	if result["code"] != "PLAN_FILE_NOT_FOUND" {
		t.Errorf("expected PLAN_FILE_NOT_FOUND, got %v", result["code"])
	}
}

func TestReviewFinalizeDraftNotFound(t *testing.T) {
	tmp := t.TempDir()
	planFile := filepath.Join(tmp, "plan.md")
	if err := os.WriteFile(planFile, []byte("# Plan\n### Task 1: A\n"), 0644); err != nil {
		t.Fatal(err)
	}
	rc, result := runReviewFinalizeCmd(planFile, "/nonexistent/draft.md", filepath.Join(tmp, "final.md"))
	if rc != 1 {
		t.Fatalf("expected exit 1, got %d", rc)
	}
	if result["code"] != "DRAFT_FILE_NOT_FOUND" {
		t.Errorf("expected DRAFT_FILE_NOT_FOUND, got %v", result["code"])
	}
}

func TestReviewFinalizeSameFile(t *testing.T) {
	tmp := t.TempDir()
	f := filepath.Join(tmp, "same.md")
	if err := os.WriteFile(f, []byte("# Plan\n### Task 1: A\n"), 0644); err != nil {
		t.Fatal(err)
	}
	rc, result := runReviewFinalizeCmd(f, f, f)
	if rc != 1 {
		t.Fatalf("expected exit 1, got %d", rc)
	}
	if result["code"] != "SAME_FILE" {
		t.Errorf("expected SAME_FILE, got %v", result["code"])
	}
}

func TestReviewFinalizeNoTasks(t *testing.T) {
	tmp := t.TempDir()
	planFile := filepath.Join(tmp, "plan.md")
	draftFile := filepath.Join(tmp, "draft.md")
	if err := os.WriteFile(planFile, []byte("# Plan\nNo tasks.\n"), 0644); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(draftFile, []byte("# Draft\n"), 0644); err != nil {
		t.Fatal(err)
	}
	rc, result := runReviewFinalizeCmd(planFile, draftFile, filepath.Join(tmp, "final.md"))
	if rc != 1 {
		t.Fatalf("expected exit 1, got %d", rc)
	}
	if result["code"] != "NO_TASKS" {
		t.Errorf("expected NO_TASKS, got %v", result["code"])
	}
}

func TestReviewFinalizeStructuralFail(t *testing.T) {
	// Create a design with AC02 not referenced in plan to trigger structural check failure.
	design := `# Design

## Acceptance Criteria

| ID | Description |
|----|-------------|
| AC01 | Something |
| AC02 | Something else |
`
	// Plan only references AC01.
	planFile, draftFile, finalFile, _ := writeRfTestFiles(t, design, rfTestPlan(), rfTestDraftAllPass())

	rc, result := runReviewFinalizeCmd(planFile, draftFile, finalFile)
	if rc != 1 {
		t.Fatalf("expected exit 1, got %d", rc)
	}
	if result["proceed"] != "no" {
		t.Errorf("expected proceed=no, got %v", result["proceed"])
	}

	// Verify structural failure is mentioned in the final file.
	data, err := os.ReadFile(finalFile)
	if err != nil {
		t.Fatalf("final file not written: %v", err)
	}
	if !strings.Contains(string(data), "Structural Check**: FAIL") {
		t.Error("expected structural FAIL in output")
	}
}
