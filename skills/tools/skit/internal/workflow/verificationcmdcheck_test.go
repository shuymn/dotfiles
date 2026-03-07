package workflow

import (
	"strings"
	"testing"
)

func runVerificationCmdCheckCmd(args ...string) (int, map[string]any) {
	rc, stdout, _, err := runCommandOutput(VerificationCmdCheck(), "", args...)
	if err != nil {
		return 1, map[string]any{"_err": err.Error()}
	}
	return rc, parseJSONResult(stdout)
}

// --- Unit tests: checkVerificationRow ---

func TestCheckVerificationRow_Empty(t *testing.T) {
	row := map[string]string{"AC ID": "AC01", "Verification Command": ""}
	status, msg := checkVerificationRow(row)
	if status != "FAIL" {
		t.Errorf("expected FAIL, got %q", status)
	}
	if !strings.Contains(msg, "empty") {
		t.Errorf("expected 'empty' in message, got %q", msg)
	}
}

func TestCheckVerificationRow_Dash(t *testing.T) {
	row := map[string]string{"AC ID": "AC01", "Verification Command": "-"}
	status, _ := checkVerificationRow(row)
	if status != "FAIL" {
		t.Errorf("expected FAIL for '-', got %q", status)
	}
}

func TestCheckVerificationRow_None(t *testing.T) {
	row := map[string]string{"AC ID": "AC01", "Verification Command": "none"}
	status, _ := checkVerificationRow(row)
	if status != "FAIL" {
		t.Errorf("expected FAIL for 'none', got %q", status)
	}
}

func TestCheckVerificationRow_NA(t *testing.T) {
	row := map[string]string{"AC ID": "AC01", "Verification Command": "n/a"}
	status, _ := checkVerificationRow(row)
	if status != "FAIL" {
		t.Errorf("expected FAIL for 'n/a', got %q", status)
	}
}

func TestCheckVerificationRow_TBDAtPlanHyphen(t *testing.T) {
	row := map[string]string{"AC ID": "AC01", "Verification Command": "TBD-at-plan"}
	status, msg := checkVerificationRow(row)
	if status != "TBD" {
		t.Errorf("expected TBD for 'TBD-at-plan', got %q", status)
	}
	if !strings.Contains(msg, "TBD-at-plan") {
		t.Errorf("expected 'TBD-at-plan' in message, got %q", msg)
	}
}

func TestCheckVerificationRow_TBDAtPlanUnderscore(t *testing.T) {
	row := map[string]string{"AC ID": "AC01", "Verification Command": "tbd_at_plan"}
	status, _ := checkVerificationRow(row)
	if status != "TBD" {
		t.Errorf("expected TBD for 'tbd_at_plan', got %q", status)
	}
}

func TestCheckVerificationRow_ResolvableCommand(t *testing.T) {
	orig := lookPathFn
	lookPathFn = func(file string) (string, error) { return "/usr/bin/" + file, nil }
	t.Cleanup(func() { lookPathFn = orig })

	row := map[string]string{"AC ID": "AC01", "Verification Command": "go test ./..."}
	status, _ := checkVerificationRow(row)
	if status != "PASS" {
		t.Errorf("expected PASS for resolvable command, got %q", status)
	}
}

func TestCheckVerificationRow_UnresolvableCommand(t *testing.T) {
	orig := lookPathFn
	lookPathFn = func(file string) (string, error) {
		return "", &exec_error{name: file}
	}
	t.Cleanup(func() { lookPathFn = orig })

	row := map[string]string{"AC ID": "AC02", "Verification Command": "nonexistent-tool --check"}
	status, msg := checkVerificationRow(row)
	if status != "FAIL" {
		t.Errorf("expected FAIL for unresolvable command, got %q", status)
	}
	if !strings.Contains(msg, "nonexistent-tool") {
		t.Errorf("expected command name in message, got %q", msg)
	}
}

func TestCheckVerificationRow_FallbackColumnName(t *testing.T) {
	orig := lookPathFn
	lookPathFn = func(file string) (string, error) { return "/usr/bin/" + file, nil }
	t.Cleanup(func() { lookPathFn = orig })

	// "Verification" as fallback column
	row := map[string]string{"AC ID": "AC01", "Verification": "go test ./..."}
	status, _ := checkVerificationRow(row)
	if status != "PASS" {
		t.Errorf("expected PASS using fallback column, got %q", status)
	}
}

// exec_error is a minimal error for simulating exec.ErrNotFound.
type exec_error struct{ name string }

func (e *exec_error) Error() string { return e.name + ": executable file not found in $PATH" }

// --- Unit tests: extractSection ---

func TestExtractSection_Present(t *testing.T) {
	text := "# Design\n\n## Acceptance Criteria\n\nSome AC content.\n"
	got := extractSection(text, "Acceptance Criteria")
	if !strings.Contains(got, "Some AC content") {
		t.Errorf("expected section content, got %q", got)
	}
}

func TestExtractSection_Absent(t *testing.T) {
	text := "# Design\n\nNo AC section.\n"
	got := extractSection(text, "Acceptance Criteria")
	if got != "" {
		t.Errorf("expected empty string, got %q", got)
	}
}

func TestExtractSection_StopsAtNextSection(t *testing.T) {
	text := "## Acceptance Criteria\n\nAC content.\n\n## Next Section\n\nnext content.\n"
	got := extractSection(text, "Acceptance Criteria")
	if strings.Contains(got, "next content") {
		t.Errorf("section should not include next section content, got %q", got)
	}
	if !strings.Contains(got, "AC content") {
		t.Errorf("expected AC content, got %q", got)
	}
}

// --- Unit tests: parseGenericTable ---

func TestParseGenericTable_ValidTable(t *testing.T) {
	section := "| AC ID | Verification Command |\n" +
		"|-------|----------------------|\n" +
		"| AC01  | go test ./...        |\n"
	rows := parseGenericTable(section)
	if len(rows) != 1 {
		t.Fatalf("expected 1 row, got %d", len(rows))
	}
	if rows[0]["AC ID"] != "AC01" {
		t.Errorf("expected AC ID=AC01, got %q", rows[0]["AC ID"])
	}
}

func TestParseGenericTable_NoSeparator(t *testing.T) {
	section := "| AC ID | Verification Command |\n| AC01  | go test ./...        |\n"
	rows := parseGenericTable(section)
	if len(rows) != 0 {
		t.Errorf("expected 0 rows when separator missing, got %d", len(rows))
	}
}

func TestParseGenericTable_TooFewLines(t *testing.T) {
	section := "| AC ID | Verification Command |\n"
	rows := parseGenericTable(section)
	if len(rows) != 0 {
		t.Errorf("expected 0 rows for single-line table, got %d", len(rows))
	}
}

// --- Integration tests: runVerificationCmdCheck ---

func TestVerificationCmdCheck_FileNotFound(t *testing.T) {
	rc, out := runVerificationCmdCheckCmd("/nonexistent/design.md")
	if rc != 1 {
		t.Errorf("expected rc=1, got %d", rc)
	}
	if out["code"] != "DESIGN_FILE_NOT_FOUND" {
		t.Errorf("expected code=DESIGN_FILE_NOT_FOUND, got %v", out["code"])
	}
}

func TestVerificationCmdCheck_NoACTable(t *testing.T) {
	p := writeTempDesign(t, "# Design\n\nNo AC section here.\n")
	rc, out := runVerificationCmdCheckCmd(p)
	if rc != 0 {
		t.Errorf("expected rc=0, got %d", rc)
	}
	if out["status"] != "SKIP" {
		t.Errorf("expected status=SKIP, got %v", out["status"])
	}
	if out["code"] != "NO_AC_TABLE" {
		t.Errorf("expected code=NO_AC_TABLE, got %v", out["code"])
	}
}

func TestVerificationCmdCheck_AllValid(t *testing.T) {
	orig := lookPathFn
	lookPathFn = func(file string) (string, error) { return "/usr/bin/" + file, nil }
	t.Cleanup(func() { lookPathFn = orig })

	content := "## Acceptance Criteria\n\n" +
		"| AC ID | Description | Verification Command |\n" +
		"|-------|-------------|----------------------|\n" +
		"| AC01  | Feature X   | go test ./...        |\n" +
		"| AC02  | Feature Y   | make test            |\n"
	p := writeTempDesign(t, content)
	rc, out := runVerificationCmdCheckCmd(p)
	if rc != 0 {
		t.Errorf("expected rc=0, got %d; output: %v", rc, out)
	}
	if out["status"] != "PASS" {
		t.Errorf("expected status=PASS, got %v", out["status"])
	}
	if out["code"] != "ALL_VERIFICATION_COMMANDS_OK" {
		t.Errorf("expected code=ALL_VERIFICATION_COMMANDS_OK, got %v", out["code"])
	}
}

func TestVerificationCmdCheck_EmptyCommandFail(t *testing.T) {
	content := "## Acceptance Criteria\n\n" +
		"| AC ID | Verification Command |\n" +
		"|-------|----------------------|\n" +
		"| AC01  | -                    |\n"
	p := writeTempDesign(t, content)
	rc, out := runVerificationCmdCheckCmd(p)
	if rc != 1 {
		t.Errorf("expected rc=1, got %d", rc)
	}
	if out["status"] != "FAIL" {
		t.Errorf("expected status=FAIL, got %v", out["status"])
	}
	if out["code"] != "VERIFICATION_CMD_ISSUES" {
		t.Errorf("expected code=VERIFICATION_CMD_ISSUES, got %v", out["code"])
	}
}

func TestVerificationCmdCheck_TBDAdvisoryStillPass(t *testing.T) {
	orig := lookPathFn
	lookPathFn = func(file string) (string, error) { return "/usr/bin/" + file, nil }
	t.Cleanup(func() { lookPathFn = orig })

	content := "## Acceptance Criteria\n\n" +
		"| AC ID | Verification Command |\n" +
		"|-------|----------------------|\n" +
		"| AC01  | go test ./...        |\n" +
		"| AC02  | TBD-at-plan          |\n"
	p := writeTempDesign(t, content)
	rc, out := runVerificationCmdCheckCmd(p)
	if rc != 0 {
		t.Errorf("expected rc=0 (advisory does not fail), got %d", rc)
	}
	if out["status"] != "PASS" {
		t.Errorf("expected status=PASS, got %v", out["status"])
	}
	advisories, _ := out["signal.advisories"].(float64)
	if advisories != 1 {
		t.Errorf("expected signal.advisories=1, got %v", out["signal.advisories"])
	}
}

func TestVerificationCmdCheck_Help(t *testing.T) {
	rc, _ := runVerificationCmdCheckCmd("--help")
	if rc != 0 {
		t.Errorf("expected rc=0 for --help, got %d", rc)
	}
}
