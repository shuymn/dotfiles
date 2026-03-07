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

// --- Unit tests: extractTaskBlock ---

func TestExtractTaskBlock_ExtractsCorrect(t *testing.T) {
	plan := "# Plan\n### Task 1: First\n- **Goal**: Do A\n### Task 2: Second\n- **Goal**: Do B\n"
	block := extractTaskBlock(plan, 1)
	if !strings.Contains(block, "Do A") {
		t.Errorf("expected block to contain 'Do A', got: %q", block)
	}
	if strings.Contains(block, "Do B") {
		t.Errorf("expected block to NOT contain 'Do B', got: %q", block)
	}
}

func TestExtractTaskBlock_MissingTask(t *testing.T) {
	plan := "# Plan\n### Task 1: Only\n- **Goal**: X\n"
	block := extractTaskBlock(plan, 99)
	if block != "" {
		t.Errorf("expected empty string for missing task, got: %q", block)
	}
}

// --- Unit tests: parseAllowedFiles ---

func TestParseAllowedFiles_BacktickPatterns(t *testing.T) {
	block := "### Task 1: Test\n- **Allowed Files**:\n  - `src/**/*.py`\n  - `tests/**/*.py`\n- **Goal**: test\n"
	patterns := parseAllowedFiles(block)
	if len(patterns) != 2 || patterns[0] != "src/**/*.py" || patterns[1] != "tests/**/*.py" {
		t.Errorf("unexpected patterns: %v", patterns)
	}
}

func TestParseAllowedFiles_Empty(t *testing.T) {
	block := "### Task 1: Test\n- **Goal**: test\n"
	patterns := parseAllowedFiles(block)
	if len(patterns) != 0 {
		t.Errorf("expected empty, got: %v", patterns)
	}
}

// --- Unit tests: parseExceptionFiles ---

func TestParseExceptionFiles_WithRationale(t *testing.T) {
	block := "### Task 1: Test\n- **Exception Files**:\n  - `config.json` (shared config)\n  - `pyproject.toml` (dependency update)\n"
	exceptions := parseExceptionFiles(block)
	if len(exceptions) != 2 {
		t.Fatalf("expected 2 exceptions, got %d", len(exceptions))
	}
	if exceptions[0].Pattern != "config.json" || exceptions[0].Rationale != "shared config" {
		t.Errorf("unexpected exception[0]: %+v", exceptions[0])
	}
	if exceptions[1].Pattern != "pyproject.toml" || exceptions[1].Rationale != "dependency update" {
		t.Errorf("unexpected exception[1]: %+v", exceptions[1])
	}
}

// --- Unit tests: matchFile ---

func TestMatchFile_Allowed(t *testing.T) {
	m := matchFile("src/foo.py", []string{"src/**/*.py"}, nil)
	if m.Status != "OK" {
		t.Errorf("expected OK, got %q", m.Status)
	}
	if m.Pattern != "src/**/*.py" {
		t.Errorf("expected pattern src/**/*.py, got %q", m.Pattern)
	}
}

func TestMatchFile_Exception(t *testing.T) {
	m := matchFile("config.json", []string{"src/**/*.py"}, []exceptionEntry{{Pattern: "config.json", Rationale: "shared"}})
	if m.Status != "OK (exception)" {
		t.Errorf("expected 'OK (exception)', got %q", m.Status)
	}
	if !strings.Contains(m.Pattern, "EXCEPTION") {
		t.Errorf("expected EXCEPTION in pattern, got %q", m.Pattern)
	}
}

func TestMatchFile_Deviation(t *testing.T) {
	m := matchFile("README.md", []string{"src/**/*.py"}, nil)
	if m.Status != "SCOPE_DEVIATION" {
		t.Errorf("expected SCOPE_DEVIATION, got %q", m.Status)
	}
	if m.Pattern != "NONE" {
		t.Errorf("expected pattern NONE, got %q", m.Pattern)
	}
}

func TestMatchFile_AllowedPrecedence(t *testing.T) {
	m := matchFile("src/foo.py", []string{"src/**/*.py"}, []exceptionEntry{{Pattern: "src/foo.py", Rationale: "also excepted"}})
	if m.Status != "OK" {
		t.Errorf("expected OK (allowed takes precedence), got %q", m.Status)
	}
}

// --- Unit tests: fullMatch ---

func TestFullMatch(t *testing.T) {
	tests := []struct {
		pattern string
		path    string
		want    bool
	}{
		{"src/**/*.py", "src/foo.py", true},
		{"src/**/*.py", "src/sub/foo.py", true},
		{"src/**/*.py", "src/a/b/c/foo.py", true},
		{"src/**/*.py", "tests/foo.py", false},
		{"*.md", "README.md", true},
		{"*.md", "docs/README.md", false},
		{"**/*.go", "cmd/foo.go", true},
		{"**/*.go", "foo.go", true},
		{"**/*.go", "cmd/sub/foo.go", true},
		{"**/*.go", "cmd/foo.py", false},
		{"config.json", "config.json", true},
		{"config.json", "other.json", false},
		{"**", "anything", true},
		{"**", "a/b/c", true},
	}
	for _, tt := range tests {
		got := fullMatch(tt.pattern, tt.path)
		if got != tt.want {
			t.Errorf("fullMatch(%q, %q) = %v, want %v", tt.pattern, tt.path, got, tt.want)
		}
	}
}

// --- Integration tests ---

func TestFileScopeCheck_AllInScope(t *testing.T) {
	plan := `
# Plan
### Task 1: Test
- **Allowed Files**:
  - ` + "`src/**/*.py`" + `
  - ` + "`tests/**/*.py`" + `
- **Goal**: test
`
	p := writePlanFile(t, plan)
	rc, out := runFileScopeCheckCmd("src/foo.py\ntests/test_bar.py\n", p, "--task", "1")
	if rc != 0 {
		t.Errorf("expected rc=0, got %d", rc)
	}
	if out["status"] != "PASS" {
		t.Errorf("expected status=PASS, got %v", out["status"])
	}
	if out["code"] != "ALL_FILES_IN_SCOPE" {
		t.Errorf("expected code=ALL_FILES_IN_SCOPE, got %v", out["code"])
	}
	if out["signal.ok"] != float64(2) {
		t.Errorf("expected signal.ok=2, got %v", out["signal.ok"])
	}
	if out["signal.deviation"] != float64(0) {
		t.Errorf("expected signal.deviation=0, got %v", out["signal.deviation"])
	}
}

func TestFileScopeCheck_ExceptionOK(t *testing.T) {
	plan := `
# Plan
### Task 1: Test
- **Allowed Files**:
  - ` + "`src/**/*.py`" + `
- **Exception Files**:
  - ` + "`config.json`" + ` (shared config)
- **Goal**: test
`
	p := writePlanFile(t, plan)
	rc, out := runFileScopeCheckCmd("src/foo.py\nconfig.json\n", p, "--task", "1")
	if rc != 0 {
		t.Errorf("expected rc=0, got %d", rc)
	}
	if out["status"] != "PASS" {
		t.Errorf("expected status=PASS, got %v", out["status"])
	}
	if out["signal.exception"] != float64(1) {
		t.Errorf("expected signal.exception=1, got %v", out["signal.exception"])
	}
}

func TestFileScopeCheck_Deviation(t *testing.T) {
	plan := `
# Plan
### Task 1: Test
- **Allowed Files**:
  - ` + "`src/**/*.py`" + `
- **Goal**: test
`
	p := writePlanFile(t, plan)
	rc, out := runFileScopeCheckCmd("src/foo.py\nREADME.md\n", p, "--task", "1")
	if rc != 1 {
		t.Errorf("expected rc=1, got %d", rc)
	}
	if out["status"] != "FAIL" {
		t.Errorf("expected status=FAIL, got %v", out["status"])
	}
	if out["code"] != "SCOPE_DEVIATION_DETECTED" {
		t.Errorf("expected code=SCOPE_DEVIATION_DETECTED, got %v", out["code"])
	}
	if out["signal.deviation"] != float64(1) {
		t.Errorf("expected signal.deviation=1, got %v", out["signal.deviation"])
	}
	evidence, _ := out["evidence"].(string)
	if !strings.Contains(evidence, "README.md") {
		t.Errorf("expected evidence to contain README.md, got %v", out["evidence"])
	}
	fix, _ := out["fix"].([]any)
	if len(fix) < 1 || fix[0] != "FIX_ADD_TO_ALLOWED_OR_EXCEPTION_FILES" {
		t.Errorf("expected fix[0]=FIX_ADD_TO_ALLOWED_OR_EXCEPTION_FILES, got %v", out["fix"])
	}
}

func TestFileScopeCheck_NoAllowedFiles(t *testing.T) {
	plan := `
# Plan
### Task 1: Test
- **Goal**: test
`
	p := writePlanFile(t, plan)
	rc, out := runFileScopeCheckCmd("src/foo.py\n", p, "--task", "1")
	if rc != 0 {
		t.Errorf("expected rc=0, got %d", rc)
	}
	if out["status"] != "SKIP" {
		t.Errorf("expected status=SKIP, got %v", out["status"])
	}
	if out["code"] != "NO_ALLOWED_FILES" {
		t.Errorf("expected code=NO_ALLOWED_FILES, got %v", out["code"])
	}
}

func TestFileScopeCheck_TaskNotFound(t *testing.T) {
	plan := `
# Plan
### Task 1: Test
- **Goal**: test
`
	p := writePlanFile(t, plan)
	rc, out := runFileScopeCheckCmd("src/foo.py\n", p, "--task", "99")
	if rc != 1 {
		t.Errorf("expected rc=1, got %d", rc)
	}
	if out["status"] != "FAIL" {
		t.Errorf("expected status=FAIL, got %v", out["status"])
	}
	if out["code"] != "TASK_NOT_FOUND" {
		t.Errorf("expected code=TASK_NOT_FOUND, got %v", out["code"])
	}
	if out["fix.1"] != "FIX_CHECK_TASK_ID" {
		t.Errorf("expected fix.1=FIX_CHECK_TASK_ID, got %v", out["fix.1"])
	}
}

func TestFileScopeCheck_NoChangedFiles(t *testing.T) {
	plan := `
# Plan
### Task 1: Test
- **Allowed Files**:
  - ` + "`src/**/*.py`" + `
- **Goal**: test
`
	p := writePlanFile(t, plan)
	rc, out := runFileScopeCheckCmd("", p, "--task", "1")
	if rc != 0 {
		t.Errorf("expected rc=0, got %d", rc)
	}
	if out["status"] != "SKIP" {
		t.Errorf("expected status=SKIP, got %v", out["status"])
	}
	if out["code"] != "NO_CHANGED_FILES" {
		t.Errorf("expected code=NO_CHANGED_FILES, got %v", out["code"])
	}
}

func TestFileScopeCheck_PlanNotFound(t *testing.T) {
	rc, out := runFileScopeCheckCmd("src/foo.py\n", "/nonexistent/path/plan.md", "--task", "1")
	if rc != 1 {
		t.Errorf("expected rc=1, got %d", rc)
	}
	if out["code"] != "PLAN_FILE_NOT_FOUND" {
		t.Errorf("expected code=PLAN_FILE_NOT_FOUND, got %v", out["code"])
	}
}
