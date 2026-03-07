package workflow

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func runArtifactFormatCheckCmd(args ...string) (int, map[string]any) {
	rc, stdout, _, err := runCommandOutput(ArtifactFormatCheck(), "", args...)
	if err != nil {
		return 1, map[string]any{"_err": err.Error()}
	}
	return rc, parseJSONResult(stdout)
}

func writeTempArtifact(t *testing.T, content string) string {
	t.Helper()
	p := filepath.Join(t.TempDir(), "artifact.md")
	if err := os.WriteFile(p, []byte(content), 0644); err != nil {
		t.Fatal(err)
	}
	return p
}

// --- Unit tests: checkRequiredSections ---

func TestRequiredSections_PlanMissingGraph(t *testing.T) {
	lines := strings.Split("## Checkpoint Summary\n\n- **Alignment Verdict**: PASS\n", "\n")
	missing := checkRequiredSections(lines, "plan")
	found := false
	for _, m := range missing {
		if strings.Contains(m, "Task Dependency Graph") {
			found = true
		}
	}
	if !found {
		t.Errorf("expected 'Task Dependency Graph' in missing, got %v", missing)
	}
}

func TestRequiredSections_PlanAllPresent(t *testing.T) {
	lines := strings.Split("## Checkpoint Summary\n\n...\n\n## Task Dependency Graph\n\n...\n", "\n")
	missing := checkRequiredSections(lines, "plan")
	if len(missing) != 0 {
		t.Errorf("expected no missing sections, got %v", missing)
	}
}

func TestRequiredSections_DesignMissingAcceptanceCriteria(t *testing.T) {
	lines := strings.Split("## Goals\n\n## Decomposition Strategy\n\n", "\n")
	missing := checkRequiredSections(lines, "design")
	found := false
	for _, m := range missing {
		if strings.Contains(m, "Acceptance Criteria") {
			found = true
		}
	}
	if !found {
		t.Errorf("expected 'Acceptance Criteria' in missing, got %v", missing)
	}
}

// --- Unit tests: checkTableStructure ---

func TestTableStructure_Valid(t *testing.T) {
	lines := strings.Split("| A | B | C |\n|---|---|---|\n| 1 | 2 | 3 |\n", "\n")
	issues := checkTableStructure(lines)
	if len(issues) != 0 {
		t.Errorf("expected no issues, got %v", issues)
	}
}

func TestTableStructure_MissingSeparator(t *testing.T) {
	lines := strings.Split("| A | B |\n| 1 | 2 |\n| 3 | 4 |\n", "\n")
	issues := checkTableStructure(lines)
	found := false
	for _, i := range issues {
		if strings.Contains(i, "separator") {
			found = true
		}
	}
	if !found {
		t.Errorf("expected separator issue, got %v", issues)
	}
}

func TestTableStructure_ColumnMismatch(t *testing.T) {
	lines := strings.Split("| A | B | C |\n|---|---|---|\n| 1 | 2 |\n", "\n")
	issues := checkTableStructure(lines)
	found := false
	for _, i := range issues {
		if strings.Contains(i, "columns") {
			found = true
		}
	}
	if !found {
		t.Errorf("expected column count issue, got %v", issues)
	}
}

// --- Unit tests: checkIDFormat ---

func TestIDFormat_ValidTwoDigit(t *testing.T) {
	lines := strings.Split("| AC ID | Description |\n|-------|-------------|\n| AC01  | Does X      |\n", "\n")
	issues := checkIDFormat(lines)
	if len(issues) != 0 {
		t.Errorf("expected no issues, got %v", issues)
	}
}

func TestIDFormat_SingleDigitFlagged(t *testing.T) {
	lines := strings.Split("| AC ID | Description |\n|-------|-------------|\n| AC1   | Does X      |\n", "\n")
	issues := checkIDFormat(lines)
	found := false
	for _, i := range issues {
		if strings.Contains(i, "AC1") {
			found = true
		}
	}
	if !found {
		t.Errorf("expected AC1 issue, got %v", issues)
	}
}

// --- Unit tests: checkOverallVerdict ---

func TestOverallVerdict_PresentPass(t *testing.T) {
	issues := checkOverallVerdict("- **Overall Verdict**: PASS\n")
	if len(issues) != 0 {
		t.Errorf("expected no issues, got %v", issues)
	}
}

func TestOverallVerdict_PresentFail(t *testing.T) {
	issues := checkOverallVerdict("- **Overall Verdict**: FAIL\n")
	if len(issues) != 0 {
		t.Errorf("expected no issues for FAIL verdict, got %v", issues)
	}
}

func TestOverallVerdict_Missing(t *testing.T) {
	issues := checkOverallVerdict("# Report\n\nSome content\n")
	if len(issues) == 0 {
		t.Error("expected issue for missing Overall Verdict")
	}
	if !strings.Contains(issues[0], "Overall Verdict") {
		t.Errorf("expected 'Overall Verdict' in issue, got %q", issues[0])
	}
}

func TestOverallVerdict_InvalidValue(t *testing.T) {
	issues := checkOverallVerdict("- **Overall Verdict**: MAYBE\n")
	if len(issues) == 0 {
		t.Error("expected issue for invalid Overall Verdict value")
	}
	if !strings.Contains(issues[0], "MAYBE") {
		t.Errorf("expected 'MAYBE' in issue, got %q", issues[0])
	}
}

// --- Integration tests: runArtifactFormatCheck ---

func TestArtifactFormatCheck_ValidAdversarialPass(t *testing.T) {
	content := "# Report\n\n- **Overall Verdict**: PASS\n\n## Attack Summary\n\n" +
		"| # | Category | Attack Vector | Required? | Test File | Command | Exit Code | Result | Evidence |\n" +
		"|---|----------|--------------|-----------|-----------|---------|-----------|--------|----------|\n" +
		"| 1 | Input    | Empty values | yes       | t.py      | pytest  | 0         | DEFENDED | ok |\n"
	p := writeTempArtifact(t, content)
	rc, out := runArtifactFormatCheckCmd(p, "--type", "adversarial")
	if rc != 0 {
		t.Errorf("expected rc=0, got %d; output: %v", rc, out)
	}
	if out["status"] != "PASS" {
		t.Errorf("expected status=PASS, got %v", out["status"])
	}
}

func TestArtifactFormatCheck_MissingOverallVerdictFail(t *testing.T) {
	content := "# Report\n\n## Attack Summary\n\n" +
		"| # | Category | Attack Vector | Required? | Test File | Command | Exit Code | Result | Evidence |\n" +
		"|---|----------|--------------|-----------|-----------|---------|-----------|--------|----------|\n"
	p := writeTempArtifact(t, content)
	rc, out := runArtifactFormatCheckCmd(p, "--type", "adversarial")
	if rc != 1 {
		t.Errorf("expected rc=1, got %d", rc)
	}
	if !strings.Contains(fmt.Sprint(out["issue.1"]), "Overall Verdict") {
		t.Errorf("expected 'Overall Verdict' in issue.1, got %v", out["issue.1"])
	}
}

func TestArtifactFormatCheck_TableColumnMismatchFail(t *testing.T) {
	content := "## Checkpoint Summary\n\n## Task Dependency Graph\n\n" +
		"| A | B | C |\n|---|---|---|\n| 1 | 2 |\n"
	p := writeTempArtifact(t, content)
	rc, out := runArtifactFormatCheckCmd(p, "--type", "plan")
	if rc != 1 {
		t.Errorf("expected rc=1, got %d", rc)
	}
	found := false
	for k, v := range out {
		if strings.HasPrefix(k, "issue.") && strings.Contains(fmt.Sprint(v), "columns") {
			found = true
		}
	}
	if !found {
		t.Errorf("expected 'columns' in some issue field, got %v", out)
	}
}

func TestArtifactFormatCheck_EmptyFileFail(t *testing.T) {
	p := filepath.Join(t.TempDir(), "empty.md")
	if err := os.WriteFile(p, []byte(""), 0644); err != nil {
		t.Fatal(err)
	}
	rc, out := runArtifactFormatCheckCmd(p, "--type", "plan")
	if rc != 1 {
		t.Errorf("expected rc=1, got %d", rc)
	}
	if out["code"] != "ARTIFACT_FILE_EMPTY" {
		t.Errorf("expected code=ARTIFACT_FILE_EMPTY, got %v", out["code"])
	}
}

func TestArtifactFormatCheck_FileNotFound(t *testing.T) {
	rc, out := runArtifactFormatCheckCmd("/nonexistent/artifact.md", "--type", "plan")
	if rc != 1 {
		t.Errorf("expected rc=1, got %d", rc)
	}
	if out["code"] != "ARTIFACT_FILE_NOT_FOUND" {
		t.Errorf("expected code=ARTIFACT_FILE_NOT_FOUND, got %v", out["code"])
	}
}

func TestArtifactFormatCheck_ValidDesignPass(t *testing.T) {
	content := "## Goals\n\nSome goals.\n\n## Acceptance Criteria\n\nSome ACs.\n\n## Decomposition Strategy\n\nStrategy.\n"
	p := writeTempArtifact(t, content)
	rc, out := runArtifactFormatCheckCmd(p, "--type", "design")
	if rc != 0 {
		t.Errorf("expected rc=0, got %d; output: %v", rc, out)
	}
	if out["status"] != "PASS" {
		t.Errorf("expected status=PASS, got %v", out["status"])
	}
}

func TestArtifactFormatCheck_TraceTypePass(t *testing.T) {
	content := "## Design -> Task Trace Matrix\n\n...\n\n## AC Ownership Map\n\n...\n"
	p := writeTempArtifact(t, content)
	rc, out := runArtifactFormatCheckCmd(p, "--type", "trace")
	if rc != 0 {
		t.Errorf("expected rc=0, got %d; output: %v", rc, out)
	}
	if out["status"] != "PASS" {
		t.Errorf("expected status=PASS, got %v", out["status"])
	}
}

func TestArtifactFormatCheck_ComposeTypePass(t *testing.T) {
	content := "# Compose Output\n\nSome content here.\n"
	p := writeTempArtifact(t, content)
	rc, out := runArtifactFormatCheckCmd(p, "--type", "compose")
	if rc != 0 {
		t.Errorf("expected rc=0, got %d; output: %v", rc, out)
	}
	if out["status"] != "PASS" {
		t.Errorf("expected status=PASS, got %v", out["status"])
	}
}
