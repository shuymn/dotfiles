package workflow

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func runRiskDodCheckCmd(t *testing.T, args ...string) (int, map[string]any) {
	t.Helper()
	rc, stdout, _, err := runCommandOutput(RiskDodCheck(), "", args...)
	if err != nil {
		return 1, map[string]any{"_err": err.Error()}
	}
	return rc, parseJSONResult(stdout)
}

func writeTempPlanAndDesign(t *testing.T, plan, design string) (planPath, designPath string) {
	t.Helper()
	dir := t.TempDir()
	planPath = filepath.Join(dir, "plan.md")
	designPath = filepath.Join(dir, "design.md")
	if err := os.WriteFile(planPath, []byte(plan), 0644); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(designPath, []byte(design), 0644); err != nil {
		t.Fatal(err)
	}
	return planPath, designPath
}

func makeDesign(tier string) string {
	var rationale string
	switch tier {
	case "Critical":
		rationale = "Defect Impact: breach / Blast Radius: all"
	case "Sensitive":
		rationale = "Defect Impact: corruption / Blast Radius: services"
	default:
		rationale = "Not Critical: low risk / Not Sensitive: visible failure"
	}
	return "# Design\n\n## Risk Classification\n\n" +
		"| Area | Risk Tier | Change Rationale |\n" +
		"|------|-----------|------------------|\n" +
		"| Core | " + tier + " | " + rationale + " |\n"
}

func makePlan(dodLines, files string) string {
	if files == "" {
		files = "src/foo.py"
	}
	return "# Plan\n\n" +
		"### Task 01: Do something\n" +
		"- **Goal**: Implement X\n" +
		"- **Allowed Files**:\n  - `" + files + "`\n" +
		"- **RED**: test fails\n" +
		"- **GREEN**: implement\n" +
		"- **REFACTOR**: cleanup\n" +
		"- **DoD**:\n" +
		"  - All tests pass\n" +
		"  " + dodLines + "\n"
}

// --- Unit tests: rdcParseMaxRiskTier ---

func TestRdcParseMaxRiskTier_Critical(t *testing.T) {
	got := rdcParseMaxRiskTier(makeDesign("Critical"))
	if got != "Critical" {
		t.Errorf("expected Critical, got %q", got)
	}
}

func TestRdcParseMaxRiskTier_Sensitive(t *testing.T) {
	got := rdcParseMaxRiskTier(makeDesign("Sensitive"))
	if got != "Sensitive" {
		t.Errorf("expected Sensitive, got %q", got)
	}
}

func TestRdcParseMaxRiskTier_Standard(t *testing.T) {
	got := rdcParseMaxRiskTier(makeDesign("Standard"))
	if got != "Standard" {
		t.Errorf("expected Standard, got %q", got)
	}
}

func TestRdcParseMaxRiskTier_NoSectionDefaultsStandard(t *testing.T) {
	got := rdcParseMaxRiskTier("# Design\n\nNo risk.\n")
	if got != "Standard" {
		t.Errorf("expected Standard, got %q", got)
	}
}

func TestRdcParseMaxRiskTier_CriticalBeatsSensitive(t *testing.T) {
	design := "## Risk Classification\n\n" +
		"| Area | Risk Tier | Change Rationale |\n" +
		"|------|-----------|------------------|\n" +
		"| A    | Sensitive | Defect Impact: x / Blast Radius: y |\n" +
		"| B    | Critical  | Defect Impact: x / Blast Radius: y |\n"
	got := rdcParseMaxRiskTier(design)
	if got != "Critical" {
		t.Errorf("expected Critical, got %q", got)
	}
}

// --- Unit tests: rdcCheckTask ---

func TestRdcCheckTask_CriticalWithAnnotationPass(t *testing.T) {
	body := "### Task 01\n- **DoD**:\n  - " + rdcDodCritical + "\n"
	issues := rdcCheckTask(1, body, "Critical")
	if len(issues) != 0 {
		t.Errorf("expected no issues, got %v", issues)
	}
}

func TestRdcCheckTask_CriticalMissingAnnotationFail(t *testing.T) {
	body := "### Task 01\n- **DoD**:\n  - All tests pass\n"
	issues := rdcCheckTask(1, body, "Critical")
	if len(issues) != 1 {
		t.Fatalf("expected 1 issue, got %d", len(issues))
	}
	if !strings.Contains(issues[0], "Critical") {
		t.Errorf("expected 'Critical' in issue, got %q", issues[0])
	}
}

func TestRdcCheckTask_SensitiveRequiresBothAnnotations(t *testing.T) {
	body := "### Task 01\n- **DoD**:\n  - " + rdcDodSensitive1 + "\n"
	issues := rdcCheckTask(1, body, "Sensitive")
	if len(issues) != 1 {
		t.Errorf("expected 1 issue (missing Sensitive2), got %d", len(issues))
	}
}

func TestRdcCheckTask_SensitiveWithBothPass(t *testing.T) {
	body := "### Task 01\n- **DoD**:\n  - " + rdcDodSensitive1 + "\n  - " + rdcDodSensitive2 + "\n"
	issues := rdcCheckTask(1, body, "Sensitive")
	if len(issues) != 0 {
		t.Errorf("expected no issues, got %v", issues)
	}
}

func TestRdcCheckTask_StandardImplFileNeedsAnnotation(t *testing.T) {
	body := "### Task 01\n" +
		"- **Allowed Files**:\n  - `src/main.py`\n" +
		"- **DoD**:\n  - All tests pass\n"
	issues := rdcCheckTask(1, body, "Standard")
	if len(issues) != 1 {
		t.Fatalf("expected 1 issue, got %d", len(issues))
	}
	if !strings.Contains(issues[0], "Standard+impl") {
		t.Errorf("expected 'Standard+impl' in issue, got %q", issues[0])
	}
}

func TestRdcCheckTask_StandardTestFileOnlyNoAnnotationNeeded(t *testing.T) {
	body := "### Task 01\n" +
		"- **Allowed Files**:\n  - `tests/test_foo.py`\n" +
		"- **DoD**:\n  - All tests pass\n"
	issues := rdcCheckTask(1, body, "Standard")
	if len(issues) != 0 {
		t.Errorf("expected no issues, got %v", issues)
	}
}

// --- Integration tests: runRiskDodCheck ---

func TestRiskDodCheck_PlanFileNotFound(t *testing.T) {
	rc, out := runRiskDodCheckCmd(t, "/nonexistent/plan.md", "/nonexistent/design.md")
	if rc != 1 {
		t.Errorf("expected rc=1, got %d", rc)
	}
	if out["code"] != "PLAN_FILE_NOT_FOUND" {
		t.Errorf("expected code=PLAN_FILE_NOT_FOUND, got %v", out["code"])
	}
}

func TestRiskDodCheck_DesignFileNotFound(t *testing.T) {
	dir := t.TempDir()
	planPath := filepath.Join(dir, "plan.md")
	if err := os.WriteFile(planPath, []byte("# Plan\n"), 0644); err != nil {
		t.Fatal(err)
	}
	rc, out := runRiskDodCheckCmd(t, planPath, "/nonexistent/design.md")
	if rc != 1 {
		t.Errorf("expected rc=1, got %d", rc)
	}
	if out["code"] != "DESIGN_FILE_NOT_FOUND" {
		t.Errorf("expected code=DESIGN_FILE_NOT_FOUND, got %v", out["code"])
	}
}

func TestRiskDodCheck_NoTasksSkip(t *testing.T) {
	planPath, designPath := writeTempPlanAndDesign(t, "# Plan\n\nNo tasks.\n", makeDesign("Standard"))
	rc, out := runRiskDodCheckCmd(t, planPath, designPath)
	if rc != 0 {
		t.Errorf("expected rc=0, got %d", rc)
	}
	if out["status"] != "SKIP" {
		t.Errorf("expected status=SKIP, got %v", out["status"])
	}
	if out["code"] != "NO_TASKS_FOUND" {
		t.Errorf("expected code=NO_TASKS_FOUND, got %v", out["code"])
	}
}

func TestRiskDodCheck_CriticalWithAnnotationPass(t *testing.T) {
	plan := makePlan("- "+rdcDodCritical, "")
	planPath, designPath := writeTempPlanAndDesign(t, plan, makeDesign("Critical"))
	rc, out := runRiskDodCheckCmd(t, planPath, designPath)
	if rc != 0 {
		t.Errorf("expected rc=0, got %d; output: %v", rc, out)
	}
	if out["status"] != "PASS" {
		t.Errorf("expected status=PASS, got %v", out["status"])
	}
}

func TestRiskDodCheck_CriticalMissingAnnotationFail(t *testing.T) {
	plan := makePlan("- Run quality gates", "")
	planPath, designPath := writeTempPlanAndDesign(t, plan, makeDesign("Critical"))
	rc, out := runRiskDodCheckCmd(t, planPath, designPath)
	if rc != 1 {
		t.Errorf("expected rc=1, got %d", rc)
	}
	if out["status"] != "FAIL" {
		t.Errorf("expected status=FAIL, got %v", out["status"])
	}
}

func TestRiskDodCheck_StandardImplWithAnnotationPass(t *testing.T) {
	plan := makePlan("- "+rdcDodStandardImpl, "src/impl.py")
	planPath, designPath := writeTempPlanAndDesign(t, plan, makeDesign("Standard"))
	rc, out := runRiskDodCheckCmd(t, planPath, designPath)
	if rc != 0 {
		t.Errorf("expected rc=0, got %d; output: %v", rc, out)
	}
	if out["status"] != "PASS" {
		t.Errorf("expected status=PASS, got %v", out["status"])
	}
}

func TestRiskDodCheck_Help(t *testing.T) {
	rc, _ := runRiskDodCheckCmd(t, "--help")
	if rc != 0 {
		t.Errorf("expected rc=0 for --help, got %d", rc)
	}
}
