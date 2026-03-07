package workflow

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func runRiskFormatCheckCmd(args ...string) (int, map[string]any) {
	rc, stdout, _, err := runCommandOutput(RiskFormatCheck(), "", args...)
	if err != nil {
		return 1, map[string]any{"_err": err.Error()}
	}
	return rc, parseJSONResult(stdout)
}

func writeTempDesign(t *testing.T, content string) string {
	t.Helper()
	p := filepath.Join(t.TempDir(), "design.md")
	if err := os.WriteFile(p, []byte(content), 0644); err != nil {
		t.Fatal(err)
	}
	return p
}

// --- Unit tests: checkRiskRow ---

func TestCheckRiskRow_CriticalValid(t *testing.T) {
	row := map[string]string{
		"Area":             "Auth",
		"Risk Tier":        "Critical",
		"Change Rationale": "Defect Impact: auth bypass / Blast Radius: all users",
	}
	ok, _ := checkRiskRow(row)
	if !ok {
		t.Error("expected ok=true for valid Critical row")
	}
}

func TestCheckRiskRow_CriticalMissingFormat(t *testing.T) {
	row := map[string]string{
		"Area":             "Auth",
		"Risk Tier":        "Critical",
		"Change Rationale": "Very important area",
	}
	ok, issue := checkRiskRow(row)
	if ok {
		t.Error("expected ok=false for invalid Critical row")
	}
	if !strings.Contains(issue, "Defect Impact") {
		t.Errorf("expected 'Defect Impact' in issue, got %q", issue)
	}
}

func TestCheckRiskRow_SensitiveValid(t *testing.T) {
	row := map[string]string{
		"Area":             "DB Schema",
		"Risk Tier":        "Sensitive",
		"Change Rationale": "Defect Impact: silent corruption / Blast Radius: all services",
	}
	ok, _ := checkRiskRow(row)
	if !ok {
		t.Error("expected ok=true for valid Sensitive row")
	}
}

func TestCheckRiskRow_StandardValid(t *testing.T) {
	row := map[string]string{
		"Area":             "UI",
		"Risk Tier":        "Standard",
		"Change Rationale": "Not Critical: UI only / Not Sensitive: locally visible failure",
	}
	ok, _ := checkRiskRow(row)
	if !ok {
		t.Error("expected ok=true for valid Standard row")
	}
}

func TestCheckRiskRow_StandardMissingFormat(t *testing.T) {
	row := map[string]string{
		"Area":             "UI",
		"Risk Tier":        "Standard",
		"Change Rationale": "Low risk area",
	}
	ok, issue := checkRiskRow(row)
	if ok {
		t.Error("expected ok=false for invalid Standard row")
	}
	if !strings.Contains(issue, "Not Critical") {
		t.Errorf("expected 'Not Critical' in issue, got %q", issue)
	}
}

func TestCheckRiskRow_UnknownTierSkipped(t *testing.T) {
	row := map[string]string{
		"Area":             "X",
		"Risk Tier":        "Unknown",
		"Change Rationale": "irrelevant",
	}
	ok, _ := checkRiskRow(row)
	if !ok {
		t.Error("expected ok=true for unknown tier (skipped)")
	}
}

// --- Unit tests: parseGenericTable (risk table rows) ---

func TestParseRiskTable_ValidTable(t *testing.T) {
	section := "| Area | Risk Tier | Change Rationale |\n" +
		"|------|-----------|------------------|\n" +
		"| Auth | Critical  | Defect Impact: breach / Blast Radius: all |\n"
	rows := parseGenericTable(section)
	if len(rows) != 1 {
		t.Fatalf("expected 1 row, got %d", len(rows))
	}
	if rows[0]["Risk Tier"] != "Critical" {
		t.Errorf("expected Risk Tier=Critical, got %q", rows[0]["Risk Tier"])
	}
}

func TestParseRiskTable_NoSeparator(t *testing.T) {
	section := "| Area | Risk Tier |\n| Auth | Critical  |\n"
	rows := parseGenericTable(section)
	if len(rows) != 0 {
		t.Errorf("expected 0 rows when separator missing, got %d", len(rows))
	}
}

func TestParseRiskTable_TooFewLines(t *testing.T) {
	section := "| Area | Risk Tier |\n"
	rows := parseGenericTable(section)
	if len(rows) != 0 {
		t.Errorf("expected 0 rows for single-line table, got %d", len(rows))
	}
}

// --- Unit tests: extractSection (Risk Classification) ---

func TestExtractRiskSection_Present(t *testing.T) {
	text := "# Design\n\n## Risk Classification\n\nSome content here.\n"
	got := extractSection(text, "Risk Classification")
	if !strings.Contains(got, "Some content here") {
		t.Errorf("expected section content, got %q", got)
	}
}

func TestExtractRiskSection_Absent(t *testing.T) {
	text := "# Design\n\nNo risk section.\n"
	got := extractSection(text, "Risk Classification")
	if got != "" {
		t.Errorf("expected empty string, got %q", got)
	}
}

func TestExtractRiskSection_StopsAtNextSection(t *testing.T) {
	text := "## Risk Classification\n\nrisk content\n\n## Next Section\n\nnext content\n"
	got := extractSection(text, "Risk Classification")
	if strings.Contains(got, "next content") {
		t.Errorf("section should not include content from next section, got %q", got)
	}
	if !strings.Contains(got, "risk content") {
		t.Errorf("expected risk content, got %q", got)
	}
}

// --- Integration tests: runRiskFormatCheck ---

func TestRiskFormatCheck_FileNotFound(t *testing.T) {
	rc, out := runRiskFormatCheckCmd("/nonexistent/design.md")
	if rc != 1 {
		t.Errorf("expected rc=1, got %d", rc)
	}
	if out["code"] != "DESIGN_FILE_NOT_FOUND" {
		t.Errorf("expected code=DESIGN_FILE_NOT_FOUND, got %v", out["code"])
	}
}

func TestRiskFormatCheck_NoSection(t *testing.T) {
	p := writeTempDesign(t, "# Design\n\nNo risk section.\n")
	rc, out := runRiskFormatCheckCmd(p)
	if rc != 0 {
		t.Errorf("expected rc=0, got %d", rc)
	}
	if out["code"] != "NO_RISK_CLASSIFICATION_SECTION" {
		t.Errorf("expected code=NO_RISK_CLASSIFICATION_SECTION, got %v", out["code"])
	}
	if out["status"] != "SKIP" {
		t.Errorf("expected status=SKIP, got %v", out["status"])
	}
}

func TestRiskFormatCheck_EmptyTable(t *testing.T) {
	p := writeTempDesign(t, "## Risk Classification\n\nNo rows here.\n")
	rc, out := runRiskFormatCheckCmd(p)
	if rc != 1 {
		t.Errorf("expected rc=1, got %d", rc)
	}
	if out["code"] != "RISK_TABLE_EMPTY" {
		t.Errorf("expected code=RISK_TABLE_EMPTY, got %v", out["code"])
	}
}

func TestRiskFormatCheck_ValidMixedRows(t *testing.T) {
	content := "## Risk Classification\n\n" +
		"| Area | Risk Tier | Change Rationale |\n" +
		"|------|-----------|------------------|\n" +
		"| Auth | Critical  | Defect Impact: breach / Blast Radius: all users |\n" +
		"| UI   | Standard  | Not Critical: UI / Not Sensitive: visible locally |\n"
	p := writeTempDesign(t, content)
	rc, out := runRiskFormatCheckCmd(p)
	if rc != 0 {
		t.Errorf("expected rc=0, got %d; output: %v", rc, out)
	}
	if out["status"] != "PASS" {
		t.Errorf("expected status=PASS, got %v", out["status"])
	}
	if out["code"] != "ALL_RISK_ROWS_VALID" {
		t.Errorf("expected code=ALL_RISK_ROWS_VALID, got %v", out["code"])
	}
}

func TestRiskFormatCheck_FormatViolations(t *testing.T) {
	content := "## Risk Classification\n\n" +
		"| Area | Risk Tier | Change Rationale |\n" +
		"|------|-----------|------------------|\n" +
		"| Auth | Critical  | Important area   |\n"
	p := writeTempDesign(t, content)
	rc, out := runRiskFormatCheckCmd(p)
	if rc != 1 {
		t.Errorf("expected rc=1, got %d", rc)
	}
	if out["status"] != "FAIL" {
		t.Errorf("expected status=FAIL, got %v", out["status"])
	}
	if out["code"] != "RISK_FORMAT_VIOLATIONS" {
		t.Errorf("expected code=RISK_FORMAT_VIOLATIONS, got %v", out["code"])
	}
}

func TestRiskFormatCheck_Help(t *testing.T) {
	rc, _ := runRiskFormatCheckCmd("--help")
	if rc != 0 {
		t.Errorf("expected rc=0 for --help, got %d", rc)
	}
}
