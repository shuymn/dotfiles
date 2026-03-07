package cmd

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func runTraceComposeCheckCmd(t *testing.T, args ...string) (int, map[string]any) {
	t.Helper()
	rc, stdout, _, err := runCommandOutput(TraceComposeCheck(), "", args...)
	if err != nil {
		return 1, map[string]any{"_err": err.Error()}
	}
	return rc, parseJSONResult(stdout)
}

func writeTempDesignAndTrace(t *testing.T, design, trace string) (designPath, tracePath string) {
	t.Helper()
	dir := t.TempDir()
	designPath = filepath.Join(dir, "design.md")
	tracePath = filepath.Join(dir, "plan.trace.md")
	if err := os.WriteFile(designPath, []byte(design), 0644); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(tracePath, []byte(trace), 0644); err != nil {
		t.Fatal(err)
	}
	return designPath, tracePath
}

// --- Unit tests: tccExtractDesignAtoms ---

func TestTccExtractDesignAtoms_Mixed(t *testing.T) {
	text := "REQ1, AC2, GOAL3, DEC4 and REQ-5 again"
	atoms := tccExtractDesignAtoms(text)
	for _, want := range []string{"REQ1", "AC2", "GOAL3", "DEC4", "REQ-5"} {
		if _, ok := atoms[want]; !ok {
			t.Errorf("expected atom %q not found", want)
		}
	}
}

func TestTccExtractDesignAtoms_Empty(t *testing.T) {
	atoms := tccExtractDesignAtoms("no atoms here")
	if len(atoms) != 0 {
		t.Errorf("expected empty, got %v", atoms)
	}
}

// --- Unit tests: tccFilterACs ---

func TestTccFilterACs_OnlyAC(t *testing.T) {
	atoms := map[string]struct{}{"REQ1": {}, "AC2": {}, "AC-3": {}, "GOAL4": {}}
	acs := tccFilterACs(atoms)
	if _, ok := acs["AC2"]; !ok {
		t.Error("expected AC2")
	}
	if _, ok := acs["AC-3"]; !ok {
		t.Error("expected AC-3")
	}
	if _, ok := acs["REQ1"]; ok {
		t.Error("REQ1 should not be in ACs")
	}
}

// --- Unit tests: tccExtractDesignTemps ---

func TestTccExtractDesignTemps(t *testing.T) {
	text := "TEMP1 some text TEMP-2 and REQ1"
	temps := tccExtractDesignTemps(text)
	if _, ok := temps["TEMP1"]; !ok {
		t.Error("expected TEMP1")
	}
	if _, ok := temps["TEMP-2"]; !ok {
		t.Error("expected TEMP-2")
	}
	if _, ok := temps["REQ1"]; ok {
		t.Error("REQ1 should not be in temps")
	}
}

// --- Unit tests: tccParseTraceMatrixAtoms ---

func TestTccParseTraceMatrixAtoms_BulletLines(t *testing.T) {
	section := "- REQ1: Task 1, Task 2\n- AC2: Task 3\n- GOAL3: Task 1\nnot a bullet\n"
	atoms := tccParseTraceMatrixAtoms(section)
	for _, want := range []string{"REQ1", "AC2", "GOAL3"} {
		if _, ok := atoms[want]; !ok {
			t.Errorf("expected atom %q", want)
		}
	}
}

func TestTccParseTraceMatrixAtoms_NoColon(t *testing.T) {
	section := "- REQ1 Task 1\n"
	atoms := tccParseTraceMatrixAtoms(section)
	if len(atoms) != 0 {
		t.Errorf("line without colon should yield no atoms, got %v", atoms)
	}
}

// --- Unit tests: parseGenericTable (AC Ownership Map usage) ---

func TestTccACOwnershipMap_WithSeparator(t *testing.T) {
	section := "| AC ID | Owner Task |\n|-------|------------|\n| AC1 | Task 1 |\n| AC2 | Task 2 |\n"
	rows := parseGenericTable(section)
	if len(rows) != 2 {
		t.Fatalf("expected 2 rows, got %d", len(rows))
	}
	if rows[0]["AC ID"] != "AC1" {
		t.Errorf("expected AC1, got %q", rows[0]["AC ID"])
	}
	if rows[1]["Owner Task"] != "Task 2" {
		t.Errorf("expected Task 2, got %q", rows[1]["Owner Task"])
	}
}

func TestTccACOwnershipMap_Empty(t *testing.T) {
	rows := parseGenericTable("no table here")
	if len(rows) != 0 {
		t.Errorf("expected empty, got %v", rows)
	}
}

// --- Unit tests: tccParseTempTraceIDs ---

func TestTccParseTempTraceIDs_Bullets(t *testing.T) {
	section := "- TEMP1: resolved in Task 1\n- TEMP-2: Task 2\n"
	temps := tccParseTempTraceIDs(section)
	if _, ok := temps["TEMP1"]; !ok {
		t.Error("expected TEMP1")
	}
	if _, ok := temps["TEMP-2"]; !ok {
		t.Error("expected TEMP-2")
	}
}

func TestTccParseTempTraceIDs_Table(t *testing.T) {
	section := "| TEMP-ID | Resolution |\n|---------|------------|\n| TEMP3 | Task 1 |\n"
	temps := tccParseTempTraceIDs(section)
	if _, ok := temps["TEMP3"]; !ok {
		t.Error("expected TEMP3 from table")
	}
}

func TestTccParseTempTraceIDs_BulletNoColon(t *testing.T) {
	section := "- TEMP4\n"
	temps := tccParseTempTraceIDs(section)
	if _, ok := temps["TEMP4"]; !ok {
		t.Error("expected TEMP4 from bullet without colon")
	}
}

// --- Unit tests: tccCheckTraceXRef ---

func TestTccCheckTraceXRef_Pass(t *testing.T) {
	atoms := map[string]struct{}{"REQ1": {}, "AC2": {}}
	status, _, evidence := tccCheckTraceXRef(atoms, atoms)
	if status != "PASS" {
		t.Errorf("expected PASS, got %q (evidence: %s)", status, evidence)
	}
}

func TestTccCheckTraceXRef_MissingForward(t *testing.T) {
	design := map[string]struct{}{"REQ1": {}, "AC2": {}}
	trace := map[string]struct{}{"REQ1": {}}
	status, _, evidence := tccCheckTraceXRef(design, trace)
	if status != "FAIL" {
		t.Errorf("expected FAIL, got %q", status)
	}
	if !strings.Contains(evidence, "AC2") {
		t.Errorf("expected AC2 in evidence, got %q", evidence)
	}
}

func TestTccCheckTraceXRef_OrphanReverse(t *testing.T) {
	design := map[string]struct{}{"REQ1": {}}
	trace := map[string]struct{}{"REQ1": {}, "GOAL99": {}}
	status, _, evidence := tccCheckTraceXRef(design, trace)
	if status != "FAIL" {
		t.Errorf("expected FAIL, got %q", status)
	}
	if !strings.Contains(evidence, "GOAL99") {
		t.Errorf("expected GOAL99 in evidence, got %q", evidence)
	}
}

// --- Unit tests: tccCheckACOwnership ---

func TestTccCheckACOwnership_Pass(t *testing.T) {
	acs := map[string]struct{}{"AC1": {}, "AC2": {}}
	rows := []map[string]string{
		{"AC ID": "AC1", "Owner Task": "Task 1"},
		{"AC ID": "AC2", "Owner Task": "Task 2"},
	}
	status, _, evidence := tccCheckACOwnership(acs, rows)
	if status != "PASS" {
		t.Errorf("expected PASS, got %q (evidence: %s)", status, evidence)
	}
}

func TestTccCheckACOwnership_MissingFromOwnership(t *testing.T) {
	acs := map[string]struct{}{"AC1": {}, "AC2": {}}
	rows := []map[string]string{
		{"AC ID": "AC1", "Owner Task": "Task 1"},
	}
	status, _, evidence := tccCheckACOwnership(acs, rows)
	if status != "FAIL" {
		t.Errorf("expected FAIL, got %q", status)
	}
	if !strings.Contains(evidence, "AC2") {
		t.Errorf("expected AC2 in evidence, got %q", evidence)
	}
}

func TestTccCheckACOwnership_Phantom(t *testing.T) {
	acs := map[string]struct{}{"AC1": {}}
	rows := []map[string]string{
		{"AC ID": "AC1", "Owner Task": "Task 1"},
		{"AC ID": "AC99", "Owner Task": "Task 2"},
	}
	status, _, evidence := tccCheckACOwnership(acs, rows)
	if status != "FAIL" {
		t.Errorf("expected FAIL, got %q", status)
	}
	if !strings.Contains(evidence, "AC99") {
		t.Errorf("expected AC99 in evidence, got %q", evidence)
	}
}

func TestTccCheckACOwnership_Duplicate(t *testing.T) {
	acs := map[string]struct{}{"AC1": {}}
	rows := []map[string]string{
		{"AC ID": "AC1", "Owner Task": "Task 1"},
		{"AC ID": "AC1", "Owner Task": "Task 2"},
	}
	status, _, evidence := tccCheckACOwnership(acs, rows)
	if status != "FAIL" {
		t.Errorf("expected FAIL, got %q", status)
	}
	if !strings.Contains(evidence, "duplicate") {
		t.Errorf("expected 'duplicate' in evidence, got %q", evidence)
	}
}

// --- Unit tests: tccCheckTempTrace ---

func TestTccCheckTempTrace_Pass(t *testing.T) {
	temps := map[string]struct{}{"TEMP1": {}}
	status, _, evidence := tccCheckTempTrace(temps, temps)
	if status != "PASS" {
		t.Errorf("expected PASS, got %q (evidence: %s)", status, evidence)
	}
}

func TestTccCheckTempTrace_Missing(t *testing.T) {
	design := map[string]struct{}{"TEMP1": {}, "TEMP2": {}}
	trace := map[string]struct{}{"TEMP1": {}}
	status, _, evidence := tccCheckTempTrace(design, trace)
	if status != "FAIL" {
		t.Errorf("expected FAIL, got %q", status)
	}
	if !strings.Contains(evidence, "TEMP2") {
		t.Errorf("expected TEMP2 in evidence, got %q", evidence)
	}
}

// --- Integration tests: runTraceComposeCheck ---

func TestTraceComposeCheck_Help(t *testing.T) {
	rc, _ := runTraceComposeCheckCmd(t, "--help")
	if rc != 0 {
		t.Errorf("expected rc=0 for --help, got %d", rc)
	}
}

func TestTraceComposeCheck_TooFewArgs(t *testing.T) {
	rc, _ := runTraceComposeCheckCmd(t, "only-one-arg.md")
	if rc != 1 {
		t.Errorf("expected rc=1 for too few args, got %d", rc)
	}
}

func TestTraceComposeCheck_DesignFileNotFound(t *testing.T) {
	rc, out := runTraceComposeCheckCmd(t, "/nonexistent/design.md", "/nonexistent/trace.md")
	if rc != 1 {
		t.Errorf("expected rc=1, got %d", rc)
	}
	if out["code"] != "DESIGN_FILE_NOT_FOUND" {
		t.Errorf("expected code=DESIGN_FILE_NOT_FOUND, got %v", out["code"])
	}
}

func TestTraceComposeCheck_TraceFileNotFound(t *testing.T) {
	dir := t.TempDir()
	designPath := filepath.Join(dir, "design.md")
	if err := os.WriteFile(designPath, []byte("# Design\n"), 0644); err != nil {
		t.Fatal(err)
	}
	rc, out := runTraceComposeCheckCmd(t, designPath, "/nonexistent/trace.md")
	if rc != 1 {
		t.Errorf("expected rc=1, got %d", rc)
	}
	if out["code"] != "TRACE_FILE_NOT_FOUND" {
		t.Errorf("expected code=TRACE_FILE_NOT_FOUND, got %v", out["code"])
	}
}

func TestTraceComposeCheck_AllChecksPass(t *testing.T) {
	design := "# Design\n\nREQ1, AC1, GOAL1, DEC1, TEMP1\n"
	trace := "# Trace\n\n" +
		"## Design -> Task Trace Matrix\n\n" +
		"- REQ1: Task 1\n" +
		"- AC1: Task 1\n" +
		"- GOAL1: Task 1\n" +
		"- DEC1: Task 1\n\n" +
		"## AC Ownership Map\n\n" +
		"| AC ID | Owner Task |\n" +
		"|-------|------------|\n" +
		"| AC1 | Task 1 |\n\n" +
		"## Temporary Mechanism Trace\n\n" +
		"- TEMP1: resolved in Task 1\n"
	designPath, tracePath := writeTempDesignAndTrace(t, design, trace)
	rc, out := runTraceComposeCheckCmd(t, designPath, tracePath)
	if rc != 0 {
		t.Errorf("expected rc=0, got %d; output: %v", rc, out)
	}
	if out["status"] != "PASS" {
		t.Errorf("expected status=PASS, got %v", out["status"])
	}
	if out["code"] != "ALL_CHECKS_PASSED" {
		t.Errorf("expected code=ALL_CHECKS_PASSED, got %v", out["code"])
	}
	if out["checks.total"] != float64(3) {
		t.Errorf("expected checks.total=3, got %v", out["checks.total"])
	}
	if out["checks.failed"] != float64(0) {
		t.Errorf("expected checks.failed=0, got %v", out["checks.failed"])
	}
}

func TestTraceComposeCheck_TraceXRefFail(t *testing.T) {
	design := "# Design\n\nREQ1, REQ2\n"
	trace := "# Trace\n\n" +
		"## Design -> Task Trace Matrix\n\n" +
		"- REQ1: Task 1\n\n" + // REQ2 missing
		"## AC Ownership Map\n\n" +
		"## Temporary Mechanism Trace\n\n"
	designPath, tracePath := writeTempDesignAndTrace(t, design, trace)
	rc, out := runTraceComposeCheckCmd(t, designPath, tracePath)
	if rc != 1 {
		t.Errorf("expected rc=1, got %d", rc)
	}
	if out["status"] != "FAIL" {
		t.Errorf("expected status=FAIL, got %v", out["status"])
	}
	if out["check.1.status"] != "FAIL" {
		t.Errorf("expected check.1.status=FAIL, got %v", out["check.1.status"])
	}
}

func TestTraceComposeCheck_NoAtomsAndNoTemps_Pass(t *testing.T) {
	design := "# Design\n\nNo atoms or temps here.\n"
	trace := "# Trace\n\n" +
		"## Design -> Task Trace Matrix\n\n" +
		"## AC Ownership Map\n\n" +
		"## Temporary Mechanism Trace\n\n"
	designPath, tracePath := writeTempDesignAndTrace(t, design, trace)
	rc, out := runTraceComposeCheckCmd(t, designPath, tracePath)
	if rc != 0 {
		t.Errorf("expected rc=0, got %d; output: %v", rc, out)
	}
	if out["status"] != "PASS" {
		t.Errorf("expected status=PASS, got %v", out["status"])
	}
}
