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
		t.Fatalf("expected no errors, got %v", errors)
	}
	for _, field := range rfSummaryFields {
		if m[field] != "PASS" {
			t.Fatalf("expected PASS for %s, got %s", field, m[field])
		}
	}
}

func TestRfParseTaskShapeFindings(t *testing.T) {
	body := `| Task | Severity | Predicate | Evidence | Action |
|------|----------|-----------|----------|--------|
| Task 1 | blocker | OWNERSHIP_TOO_BROAD | Owned Paths cover two unrelated areas. | Re-slice the task. |
| Task 2 | warning | BOUNDARY_WITHOUT_VERIFICATION | Shared boundary lacks explicit verification. | Tighten the command. |`
	findings, issues := rfParseTaskShapeFindings(body, []string{"Task 1", "Task 2"})
	if len(issues) != 0 {
		t.Fatalf("expected no issues, got %v", issues)
	}
	if len(findings) != 2 || findings[0].Severity != "blocker" || findings[0].Predicate != "OWNERSHIP_TOO_BROAD" {
		t.Fatalf("unexpected findings: %+v", findings)
	}
}

func TestRfMakeDecisionReason_Blocker(t *testing.T) {
	summary := map[string]string{}
	for _, field := range rfSummaryFields {
		summary[field] = "PASS"
	}
	proceed, reason := rfMakeDecisionReason(true, summary, []rfTaskShapeFinding{{Task: "Task 1", Severity: "blocker"}})
	if proceed != "no" || !strings.Contains(reason, "task shape blockers") {
		t.Fatalf("unexpected decision: proceed=%q reason=%q", proceed, reason)
	}
}

func TestReviewFinalize_TaskShapeBlockerFails(t *testing.T) {
	dir := t.TempDir()
	designPath := filepath.Join(dir, "design.md")
	planPath := filepath.Join(dir, "plan.md")
	draftPath := filepath.Join(dir, "plan.review.draft.md")
	finalPath := filepath.Join(dir, "plan.review.md")

	design := "# Design\n\n## Acceptance Criteria\n\n| AC ID | Description |\n|-------|-------------|\n| AC01 | one |\n"
	plan := strings.Join([]string{
		"# Topic Implementation Plan",
		"",
		"- **Source**: `design.md`",
		"",
		"## Quality Gates",
		"",
		"- `go test ./...`",
		"",
		"### Task 1: Build",
		"- **Satisfied Requirements**: AC01",
		"- **Design Anchors**: AC01",
		"- **Dependencies**: none",
		"- **DoD**:",
		"  - Run: `go test ./...`",
	}, "\n")
	draft := strings.Join([]string{
		"# Topic - Plan Review Draft",
		"",
		"## Reviewer Summary",
		"",
		"- Forward Fidelity: PASS",
		"- Reverse Fidelity: PASS",
		"- Round-trip: PASS",
		"- Behavioral Lock: PASS",
		"- Negative Path: PASS",
		"- Temporal: PASS",
		"- Traceability: PASS",
		"- Scope: PASS",
		"- Testability: PASS",
		"- Execution Readiness: PASS",
		"- Integration Coverage: PASS",
		"- Risk Classification: PASS",
		"",
		"## Task Shape Findings",
		"",
		"| Task | Severity | Predicate | Evidence | Action |",
		"|------|----------|-----------|----------|--------|",
		"| Task 1 | blocker | OWNERSHIP_TOO_BROAD | Owned Paths are too broad to communicate rollback boundaries. | Re-slice the task. |",
	}, "\n")

	for path, content := range map[string]string{
		designPath: design,
		planPath:   plan,
		draftPath:  draft,
	} {
		if err := os.WriteFile(path, []byte(content), 0644); err != nil {
			t.Fatal(err)
		}
	}

	rc, out := runReviewFinalizeCmd(planPath, draftPath, finalPath)
	if rc != 1 || out["code"] != "REVIEW_BLOCKED" {
		t.Fatalf("unexpected output: rc=%d out=%v", rc, out)
	}

	finalData, err := os.ReadFile(finalPath)
	if err != nil {
		t.Fatal(err)
	}
	finalText := string(finalData)
	if !strings.Contains(finalText, "## Task Shape Findings") {
		t.Fatalf("expected Task Shape Findings section, got:\n%s", finalText)
	}
	if !strings.Contains(finalText, "**Overall Verdict**: FAIL") {
		t.Fatalf("expected FAIL verdict, got:\n%s", finalText)
	}
}

func TestReviewFinalize_AllClearPasses(t *testing.T) {
	dir := t.TempDir()
	designPath := filepath.Join(dir, "design.md")
	planPath := filepath.Join(dir, "plan.md")
	draftPath := filepath.Join(dir, "plan.review.draft.md")
	finalPath := filepath.Join(dir, "plan.review.md")

	design := "# Design\n\n## Acceptance Criteria\n\n| AC ID | Description |\n|-------|-------------|\n| AC01 | one |\n"
	plan := strings.Join([]string{
		"# Topic Implementation Plan",
		"",
		"- **Source**: `design.md`",
		"",
		"## Quality Gates",
		"",
		"- `go test ./...`",
		"",
		"### Task 1: Build",
		"- **Satisfied Requirements**: AC01",
		"- **Design Anchors**: AC01",
		"- **Dependencies**: none",
		"- **DoD**:",
		"  - Run: `go test ./...`",
	}, "\n")
	draft := strings.Join([]string{
		"# Topic - Plan Review Draft",
		"",
		"## Reviewer Summary",
		"",
		"- Forward Fidelity: PASS",
		"- Reverse Fidelity: PASS",
		"- Round-trip: PASS",
		"- Behavioral Lock: PASS",
		"- Negative Path: PASS",
		"- Temporal: PASS",
		"- Traceability: PASS",
		"- Scope: PASS",
		"- Testability: PASS",
		"- Execution Readiness: PASS",
		"- Integration Coverage: PASS",
		"- Risk Classification: PASS",
		"",
		"## Task Shape Findings",
		"",
		"| Task | Severity | Predicate | Evidence | Action |",
		"|------|----------|-----------|----------|--------|",
		"| Task 1 | info | OWNERSHIP_TOO_BROAD | Scope contract is tight enough for the current boundary. | No action required. |",
	}, "\n")

	for path, content := range map[string]string{
		designPath: design,
		planPath:   plan,
		draftPath:  draft,
	} {
		if err := os.WriteFile(path, []byte(content), 0644); err != nil {
			t.Fatal(err)
		}
	}

	rc, out := runReviewFinalizeCmd(planPath, draftPath, finalPath)
	if rc != 0 || out["code"] != "REVIEW_FINALIZED" {
		t.Fatalf("unexpected output: rc=%d out=%v", rc, out)
	}
}
