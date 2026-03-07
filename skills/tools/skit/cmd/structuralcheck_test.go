package cmd

import (
	"bytes"
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func runStructuralCheckCmd(args ...string) (int, map[string]any) {
	var buf bytes.Buffer
	rc := runStructuralCheck(&buf, args)
	var result map[string]any
	if line := strings.TrimSpace(buf.String()); line != "" {
		if err := json.Unmarshal([]byte(line), &result); err != nil {
			return rc, map[string]any{"_raw": line, "_err": err.Error()}
		}
	}
	return rc, result
}

const stcMinimalDesign = `# Design

## Acceptance Criteria

| ID | Description |
|----|-------------|
| AC01 | Something works |
`

const stcMinimalPlan = `# Plan

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

func writeStcFiles(t *testing.T, design, plan string) (string, string) {
	t.Helper()
	tmp := t.TempDir()
	designFile := filepath.Join(tmp, "design.md")
	planFile := filepath.Join(tmp, "plan.md")
	if err := os.WriteFile(designFile, []byte(design), 0644); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(planFile, []byte(plan), 0644); err != nil {
		t.Fatal(err)
	}
	return designFile, planFile
}

func TestStructuralCheckAllPass(t *testing.T) {
	designFile, planFile := writeStcFiles(t, stcMinimalDesign, stcMinimalPlan)
	rc, result := runStructuralCheckCmd(designFile, planFile)
	if rc != 0 {
		t.Fatalf("expected exit 0, got %d; result: %v", rc, result)
	}
	if result["status"] != "PASS" {
		t.Errorf("expected PASS, got %v", result["status"])
	}
}

func TestStructuralCheckInvalidArgCount(t *testing.T) {
	rc, result := runStructuralCheckCmd("only-one")
	if rc != 1 {
		t.Fatalf("expected exit 1, got %d", rc)
	}
	if result["code"] != "INVALID_ARGUMENT_COUNT" {
		t.Errorf("expected INVALID_ARGUMENT_COUNT, got %v", result["code"])
	}
}

func TestStructuralCheckDesignNotFound(t *testing.T) {
	tmp := t.TempDir()
	planFile := filepath.Join(tmp, "plan.md")
	if err := os.WriteFile(planFile, []byte("# Plan"), 0644); err != nil {
		t.Fatal(err)
	}
	rc, result := runStructuralCheckCmd("/nonexistent/design.md", planFile)
	if rc != 1 {
		t.Fatalf("expected exit 1, got %d", rc)
	}
	if result["code"] != "DESIGN_FILE_NOT_FOUND" {
		t.Errorf("expected DESIGN_FILE_NOT_FOUND, got %v", result["code"])
	}
}

func TestStructuralCheckPlanNotFound(t *testing.T) {
	tmp := t.TempDir()
	designFile := filepath.Join(tmp, "design.md")
	if err := os.WriteFile(designFile, []byte("# Design"), 0644); err != nil {
		t.Fatal(err)
	}
	rc, result := runStructuralCheckCmd(designFile, "/nonexistent/plan.md")
	if rc != 1 {
		t.Fatalf("expected exit 1, got %d", rc)
	}
	if result["code"] != "PLAN_FILE_NOT_FOUND" {
		t.Errorf("expected PLAN_FILE_NOT_FOUND, got %v", result["code"])
	}
}

// --- Unit tests for individual checks ---

func TestStcCheckIDUniquenessPass(t *testing.T) {
	plan := "### Task 1: A\n### Task 2: B\n"
	c := stcCheckIDUniqueness(plan)
	if c.Status != "PASS" {
		t.Errorf("expected PASS, got %s", c.Status)
	}
}

func TestStcCheckIDUniquenessFail(t *testing.T) {
	plan := "### Task 1: A\n### Task 1: B\n### Task 2: C\n"
	c := stcCheckIDUniqueness(plan)
	if c.Status != "FAIL" {
		t.Errorf("expected FAIL, got %s", c.Status)
	}
	if !strings.Contains(c.Evidence, "Task 1") {
		t.Errorf("expected evidence to contain Task 1, got %q", c.Evidence)
	}
}

func TestStcCheckDepCyclePass(t *testing.T) {
	plan := "### Task 1: A\n- **Dependencies**: none\n### Task 2: B\n- **Dependencies**: T1\n"
	c := stcCheckDepCycle(plan)
	if c.Status != "PASS" {
		t.Errorf("expected PASS, got %s: %s", c.Status, c.Evidence)
	}
}

func TestStcCheckDepCycleFail(t *testing.T) {
	plan := "### Task 1: A\n- **Dependencies**: T2\n### Task 2: B\n- **Dependencies**: T1\n"
	c := stcCheckDepCycle(plan)
	if c.Status != "FAIL" {
		t.Errorf("expected FAIL, got %s", c.Status)
	}
}

func TestStcCheckDepCycleNoDeps(t *testing.T) {
	plan := "### Task 1: A\n### Task 2: B\n"
	c := stcCheckDepCycle(plan)
	if c.Status != "PASS" {
		t.Errorf("expected PASS for no deps, got %s", c.Status)
	}
}

func TestStcCheckCoverageACPass(t *testing.T) {
	design := "AC01 is defined here.\n"
	plan := "Task references AC01.\n"
	c := stcCheckCoverage("AC", design, plan)
	if c.Status != "PASS" {
		t.Errorf("expected PASS, got %s", c.Status)
	}
}

func TestStcCheckCoverageACFail(t *testing.T) {
	design := "AC01 and AC02 are defined.\n"
	plan := "Only AC01 referenced.\n"
	c := stcCheckCoverage("AC", design, plan)
	if c.Status != "FAIL" {
		t.Errorf("expected FAIL, got %s", c.Status)
	}
	if !strings.Contains(c.Evidence, "AC02") {
		t.Errorf("expected AC02 in evidence, got %q", c.Evidence)
	}
}

func TestStcCheckCoverageNoDesignIDs(t *testing.T) {
	c := stcCheckCoverage("REQ", "No ids here.", "No ids here either.")
	if c.Status != "PASS" {
		t.Errorf("expected PASS when no design IDs, got %s", c.Status)
	}
}

func TestStcCheckDoDExistencePass(t *testing.T) {
	plan := "### Task 1: A\n**DoD**\n- something\n### Task 2: B\n**DoD**\n- other\n"
	c := stcCheckDoDExistence(plan)
	if c.Status != "PASS" {
		t.Errorf("expected PASS, got %s", c.Status)
	}
}

func TestStcCheckDoDExistenceFail(t *testing.T) {
	plan := "### Task 1: A\n**DoD**\n- something\n### Task 2: B\nNo DoD here.\n"
	c := stcCheckDoDExistence(plan)
	if c.Status != "FAIL" {
		t.Errorf("expected FAIL, got %s", c.Status)
	}
	if !strings.Contains(c.Evidence, "Task 2") {
		t.Errorf("expected Task 2 in evidence, got %q", c.Evidence)
	}
}

func TestStcCheckQGateExecPass(t *testing.T) {
	// "go" should be on PATH in test environment.
	plan := "## Quality Gates\n\n| Gate | Command |\n|------|---------|---|\n| 1 | `go version` |\n"
	c := stcCheckQGateExec(plan)
	if c.Status != "PASS" {
		t.Errorf("expected PASS, got %s: %s", c.Status, c.Evidence)
	}
}

func TestStcCheckQGateExecFail(t *testing.T) {
	plan := "## Quality Gates\n\n| Gate | Command |\n|------|---------|---|\n| 1 | `nonexistent-tool-xyz789 --check` |\n"
	c := stcCheckQGateExec(plan)
	if c.Status != "FAIL" {
		t.Errorf("expected FAIL, got %s", c.Status)
	}
	if !strings.Contains(c.Evidence, "nonexistent-tool-xyz789") {
		t.Errorf("expected tool name in evidence, got %q", c.Evidence)
	}
}

func TestStcCheckQGateExecNoSection(t *testing.T) {
	plan := "# Plan\n### Task 1: A\n"
	c := stcCheckQGateExec(plan)
	if c.Status != "PASS" {
		t.Errorf("expected PASS when no QGates, got %s", c.Status)
	}
}

func TestStcCheckDoDRunExecPass(t *testing.T) {
	plan := "### Task 1: A\n**DoD**\n- Run: `go version`\n"
	c := stcCheckDoDRunExec(plan)
	if c.Status != "PASS" {
		t.Errorf("expected PASS, got %s: %s", c.Status, c.Evidence)
	}
}

func TestStcCheckDoDRunExecFail(t *testing.T) {
	plan := "### Task 1: A\n**DoD**\n- Run: `nonexistent-cmd-abc123`\n"
	c := stcCheckDoDRunExec(plan)
	if c.Status != "FAIL" {
		t.Errorf("expected FAIL, got %s", c.Status)
	}
}

func TestStcCheckDoDRunExecSkipsQGates(t *testing.T) {
	// The Run line inside Quality Gates should be skipped.
	plan := "### Task 1: A\n**DoD**\n- Run: `go version`\n\n## Quality Gates\n\n| Gate | Command |\n|------|---------|---|\n| 1 | `nonexistent-qgate-tool` |\n  - Run: `nonexistent-qgate-tool`\n"
	c := stcCheckDoDRunExec(plan)
	if c.Status != "PASS" {
		t.Errorf("expected PASS (skipping QGates section), got %s: %s", c.Status, c.Evidence)
	}
}

// --- Integration: StcRunStructuralChecks ---

func TestStcRunStructuralChecksAllPass(t *testing.T) {
	tmp := t.TempDir()
	designFile := filepath.Join(tmp, "design.md")
	planFile := filepath.Join(tmp, "plan.md")
	if err := os.WriteFile(designFile, []byte(stcMinimalDesign), 0644); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(planFile, []byte(stcMinimalPlan), 0644); err != nil {
		t.Fatal(err)
	}

	result := StcRunStructuralChecks(designFile, planFile)
	if !result.Passed {
		for _, c := range result.Checks {
			if c.Status == "FAIL" {
				t.Logf("FAIL: %s — %s [%s]", c.ID, c.Summary, c.Evidence)
			}
		}
		t.Fatalf("expected all PASS, got %d failures", result.FailedCount)
	}
	if result.TotalChecks != stcTotalChecks {
		t.Errorf("expected %d checks, got %d", stcTotalChecks, result.TotalChecks)
	}
}

func TestStcRunStructuralChecksDesignMissing(t *testing.T) {
	tmp := t.TempDir()
	planFile := filepath.Join(tmp, "plan.md")
	if err := os.WriteFile(planFile, []byte("# Plan"), 0644); err != nil {
		t.Fatal(err)
	}
	result := StcRunStructuralChecks("/nonexistent/design.md", planFile)
	if result.Passed {
		t.Error("expected failure for missing design file")
	}
}
