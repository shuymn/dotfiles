package workflow

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func runFileScopeCheckCmd(stdin string, args ...string) (int, map[string]any) {
	rc, stdout, _, err := runCommandOutput(FileScopeCheck(), stdin, args...)
	if err != nil {
		return 1, map[string]any{"_err": err.Error()}
	}
	return rc, parseJSONResult(stdout)
}

func writePlanFile(t *testing.T, content string) string {
	t.Helper()
	tmp := t.TempDir()
	p := filepath.Join(tmp, "plan.md")
	if err := os.WriteFile(p, []byte(strings.TrimSpace(content)+"\n"), 0644); err != nil {
		t.Fatal(err)
	}
	return p
}

func TestExtractTaskBlock_ZeroPaddedTaskID(t *testing.T) {
	plan := "# Plan\n### Task 01: First\n- **Goal**: Do A\n### Task 2: Second\n- **Goal**: Do B\n"
	block := extractTaskBlock(plan, 1)
	if !strings.Contains(block, "Do A") {
		t.Fatalf("expected zero-padded task to be extracted, got %q", block)
	}
}

func TestParseScopeContract(t *testing.T) {
	block := `### Task 1: Scope
- **Owned Paths**:
  - ` + "`src/feature/**`" + `
- **Shared Touchpoints**:
  - ` + "`config/project.yaml`" + ` (shared configuration update)
- **Prohibited Paths**:
  - ` + "`generated/**`" + `
`

	scope, issues := parseScopeContract(block)
	if len(issues) != 0 {
		t.Fatalf("expected no issues, got %v", issues)
	}
	if len(scope.Owned) != 1 || scope.Owned[0].Pattern != "src/feature/**" {
		t.Fatalf("unexpected owned paths: %+v", scope.Owned)
	}
	if len(scope.Shared) != 1 || scope.Shared[0].Rationale != "shared configuration update" {
		t.Fatalf("unexpected shared touchpoints: %+v", scope.Shared)
	}
	if len(scope.Prohibited) != 1 || scope.Prohibited[0].Pattern != "generated/**" {
		t.Fatalf("unexpected prohibited paths: %+v", scope.Prohibited)
	}
}

func TestMatchFile_ProhibitedPrecedence(t *testing.T) {
	scope := scopeContract{
		Owned:      []scopeEntry{{Pattern: "src/**"}},
		Prohibited: []scopeEntry{{Pattern: "src/generated/**"}},
	}
	match := matchFile("src/generated/schema.json", scope)
	if match.Status != scopeStatusProhibited {
		t.Fatalf("expected prohibited precedence, got %+v", match)
	}
}

func TestFileScopeCheck_ScopeContractSatisfied(t *testing.T) {
	plan := `
# Plan
### Task 1: Test
- **Owned Paths**:
  - ` + "`src/feature/**`" + `
- **Shared Touchpoints**:
  - ` + "`config/project.yaml`" + ` (shared configuration update)
`
	p := writePlanFile(t, plan)
	rc, out := runFileScopeCheckCmd("src/feature/main.txt\nconfig/project.yaml\n", p, "--task", "1")
	if rc != 0 {
		t.Fatalf("expected rc=0, got %d with %v", rc, out)
	}
	if out["status"] != "PASS" || out["code"] != "SCOPE_CONTRACT_SATISFIED" {
		t.Fatalf("unexpected output: %v", out)
	}
	if out["signal.owned"] != float64(1) || out["signal.shared"] != float64(1) {
		t.Fatalf("unexpected counters: %v", out)
	}
}

func TestFileScopeCheck_CrossBoundaryFails(t *testing.T) {
	plan := `
# Plan
### Task 1: Test
- **Owned Paths**:
  - ` + "`src/feature/**`" + `
`
	p := writePlanFile(t, plan)
	rc, out := runFileScopeCheckCmd("src/feature/main.txt\nREADME.md\n", p, "--task", "1")
	if rc != 1 {
		t.Fatalf("expected rc=1, got %d", rc)
	}
	if out["code"] != "CROSS_BOUNDARY_CHANGE_DETECTED" {
		t.Fatalf("unexpected output: %v", out)
	}
}

func TestFileScopeCheck_ProhibitedFails(t *testing.T) {
	plan := `
# Plan
### Task 1: Test
- **Owned Paths**:
  - ` + "`src/**`" + `
- **Prohibited Paths**:
  - ` + "`generated/**`" + `
`
	p := writePlanFile(t, plan)
	rc, out := runFileScopeCheckCmd("generated/schema.json\n", p, "--task", "1")
	if rc != 1 {
		t.Fatalf("expected rc=1, got %d", rc)
	}
	if out["code"] != "PROHIBITED_PATH_CHANGE_DETECTED" {
		t.Fatalf("unexpected output: %v", out)
	}
}

func TestFileScopeCheck_MissingOwnedPathsFailsClosed(t *testing.T) {
	plan := `
# Plan
### Task 1: Test
- **Shared Touchpoints**:
  - ` + "`config/project.yaml`" + ` (shared configuration update)
`
	p := writePlanFile(t, plan)
	rc, out := runFileScopeCheckCmd("config/project.yaml\n", p, "--task", "1")
	if rc != 1 {
		t.Fatalf("expected rc=1, got %d", rc)
	}
	if out["code"] != "NO_OWNED_PATHS" {
		t.Fatalf("unexpected output: %v", out)
	}
}
