package workflow

import (
	"os"
	"path/filepath"
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

func TestRiskDodCheck_NoTasksSkip(t *testing.T) {
	planPath, designPath := writeTempPlanAndDesign(t, "# Plan\n", "# Design\n")
	rc, out := runRiskDodCheckCmd(t, planPath, designPath)
	if rc != 0 || out["status"] != "SKIP" {
		t.Fatalf("unexpected output: rc=%d out=%v", rc, out)
	}
}

func TestRiskDodCheck_PassesWithNewContract(t *testing.T) {
	plan := `
# Plan
### Task 1: Harden CLI
- **Risk Tier**: Sensitive
- **Owned Paths**:
  - ` + "`crates/cli/src/**`" + `
- **Shared Touchpoints**:
  - ` + "`Cargo.toml`" + ` (workspace dependency update)
- **Boundary Verification**:
  - Run: ` + "`cargo test -p stateql-cli --test live_smoke`" + `
- **DoD**:
  - Global Quality Gates apply.
`
	planPath, designPath := writeTempPlanAndDesign(t, plan, "# Design\n")
	rc, out := runRiskDodCheckCmd(t, planPath, designPath)
	if rc != 0 || out["status"] != "PASS" {
		t.Fatalf("unexpected output: rc=%d out=%v", rc, out)
	}
}

func TestRiskDodCheck_FailsWithoutBoundaryVerification(t *testing.T) {
	plan := `
# Plan
### Task 1: Harden CLI
- **Risk Tier**: Critical
- **Owned Paths**:
  - ` + "`crates/cli/src/**`" + `
- **DoD**:
  - Global Quality Gates apply.
`
	planPath, designPath := writeTempPlanAndDesign(t, plan, "# Design\n")
	rc, out := runRiskDodCheckCmd(t, planPath, designPath)
	if rc != 1 || out["code"] != "TASK_CONTRACT_ISSUES" {
		t.Fatalf("unexpected output: rc=%d out=%v", rc, out)
	}
}

func TestRiskDodCheck_FailsOnLegacyFieldsAndBoilerplate(t *testing.T) {
	plan := `
# Plan
### Task 1: Legacy
- **Risk Tier**: Standard
- **Allowed Files**:
  - ` + "`crates/cli/src/**`" + `
- **Owned Paths**:
  - ` + "`crates/cli/src/**`" + `
- **DoD**:
  - ` + rdcLegacyStandardImpl + `
`
	planPath, designPath := writeTempPlanAndDesign(t, plan, "# Design\n")
	rc, out := runRiskDodCheckCmd(t, planPath, designPath)
	if rc != 1 || out["code"] != "TASK_CONTRACT_ISSUES" {
		t.Fatalf("unexpected output: rc=%d out=%v", rc, out)
	}
}

