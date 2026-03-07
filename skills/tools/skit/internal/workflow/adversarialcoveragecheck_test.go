package workflow

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

const accTestAttackVectorsMD = `# Attack Vectors

## 1. Input Boundary Attacks

Target: Input validation.

- **Empty/null values** [required]: Pass empty strings.
- **Injection** [required]: SQL injection, command injection.
- **Type coercion**: Wrong type inputs.

## 2. Error Handling Attacks

Target: Failure paths.

- **Invalid state transitions** [required]: Call methods in wrong order.
- **Retry storms**: Unbounded retries.
`

const accTestSummaryAllCovered = `## Attack Summary

| # | Category | Attack Vector | Required? | Test File | Command | Exit Code | Result | Evidence |
|---|----------|--------------|-----------|-----------|---------|-----------|--------|----------|
| 1 | Input Boundary Attacks | Empty/null values | yes | t.py | pytest | 0 | DEFENDED | ok |
| 2 | Input Boundary Attacks | Injection | yes | t.py | pytest | 0 | DEFENDED | ok |
`

const accTestSummaryMissingInjection = `## Attack Summary

| # | Category | Attack Vector | Required? | Test File | Command | Exit Code | Result | Evidence |
|---|----------|--------------|-----------|-----------|---------|-----------|--------|----------|
| 1 | Input Boundary Attacks | Empty/null values | yes | t.py | pytest | 0 | DEFENDED | ok |
`

func runAdversarialCoverageCheckCmd(t *testing.T, args ...string) (int, map[string]any) {
	t.Helper()
	rc, stdout, _, err := runCommandOutput(AdversarialCoverageCheck(), "", args...)
	if err != nil {
		return 1, map[string]any{"_err": err.Error()}
	}
	return rc, parseJSONResult(stdout)
}

func writeAccTempFiles(t *testing.T, report, vectors string) (reportPath, vectorsPath string) {
	t.Helper()
	dir := t.TempDir()
	reportPath = filepath.Join(dir, "report.adversarial.md")
	vectorsPath = filepath.Join(dir, "attack-vectors.md")
	if err := os.WriteFile(reportPath, []byte(report), 0644); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(vectorsPath, []byte(vectors), 0644); err != nil {
		t.Fatal(err)
	}
	return reportPath, vectorsPath
}

// --- Unit tests: accParseAttackVectors ---

func TestAccParseAttackVectors_CategoriesAndRequiredTags(t *testing.T) {
	cats := accParseAttackVectors(accTestAttackVectorsMD)

	if _, ok := cats["Input Boundary Attacks"]; !ok {
		t.Fatal("expected category 'Input Boundary Attacks'")
	}

	vectors := cats["Input Boundary Attacks"]
	reqNames := map[string]bool{}
	nonReqNames := map[string]bool{}
	for _, v := range vectors {
		if v.Required {
			reqNames[v.Name] = true
		} else {
			nonReqNames[v.Name] = true
		}
	}

	for _, want := range []string{"Empty/null values", "Injection"} {
		if !reqNames[want] {
			t.Errorf("expected %q to be required", want)
		}
	}
	if !nonReqNames["Type coercion"] {
		t.Error("expected 'Type coercion' to be non-required")
	}
}

func TestAccParseAttackVectors_MultipleCategories(t *testing.T) {
	cats := accParseAttackVectors(accTestAttackVectorsMD)
	if _, ok := cats["Error Handling Attacks"]; !ok {
		t.Error("expected category 'Error Handling Attacks'")
	}
	if _, ok := cats["Input Boundary Attacks"]; !ok {
		t.Error("expected category 'Input Boundary Attacks'")
	}
}

func TestAccParseAttackVectors_Empty(t *testing.T) {
	cats := accParseAttackVectors("# No categories here\n")
	if len(cats) != 0 {
		t.Errorf("expected empty map, got %v", cats)
	}
}

// --- Unit tests: accCheckCoverage ---

func TestAccCheckCoverage_AllRequiredCoveredPass(t *testing.T) {
	vectors := accParseAttackVectors(accTestAttackVectorsMD)
	selected := []string{"Input Boundary Attacks"}
	rows := []map[string]string{
		{"Category": "Input Boundary Attacks", "Attack Vector": "Empty/null values", "Result": "DEFENDED", "Evidence": "ok"},
		{"Category": "Input Boundary Attacks", "Attack Vector": "Injection", "Result": "DEFENDED", "Evidence": "ok"},
	}
	issues := accCheckCoverage(selected, vectors, rows, "Critical")
	if len(issues) != 0 {
		t.Errorf("expected no issues, got %v", issues)
	}
}

func TestAccCheckCoverage_MissingRequiredVectorFail(t *testing.T) {
	vectors := accParseAttackVectors(accTestAttackVectorsMD)
	selected := []string{"Input Boundary Attacks"}
	rows := []map[string]string{
		{"Category": "Input Boundary Attacks", "Attack Vector": "Empty/null values", "Result": "DEFENDED", "Evidence": "ok"},
	}
	issues := accCheckCoverage(selected, vectors, rows, "Critical")
	if len(issues) != 1 {
		t.Fatalf("expected 1 issue, got %d: %v", len(issues), issues)
	}
	if !strings.Contains(issues[0], "Injection") {
		t.Errorf("expected 'Injection' in issue, got %q", issues[0])
	}
}

func TestAccCheckCoverage_NADocumentedCountsAsCovered(t *testing.T) {
	vectors := accParseAttackVectors(accTestAttackVectorsMD)
	selected := []string{"Input Boundary Attacks"}
	rows := []map[string]string{
		{"Category": "Input Boundary Attacks", "Attack Vector": "Empty/null values", "Result": "DEFENDED", "Evidence": "ok"},
		{"Category": "Input Boundary Attacks", "Attack Vector": "Injection", "Result": "N/A", "Evidence": "not applicable: no external input"},
	}
	issues := accCheckCoverage(selected, vectors, rows, "Critical")
	if len(issues) != 0 {
		t.Errorf("expected no issues when N/A documented, got %v", issues)
	}
}

func TestAccCheckCoverage_StandardTierNoObligation(t *testing.T) {
	vectors := accParseAttackVectors(accTestAttackVectorsMD)
	issues := accCheckCoverage([]string{"Input Boundary Attacks"}, vectors, nil, "Standard")
	if len(issues) != 0 {
		t.Errorf("expected no issues for Standard tier, got %v", issues)
	}
}

func TestAccCheckCoverage_NonRequiredVectorNotRequired(t *testing.T) {
	vectors := accParseAttackVectors(accTestAttackVectorsMD)
	selected := []string{"Input Boundary Attacks"}
	// Only cover required vectors; "Type coercion" (non-required) is absent.
	rows := []map[string]string{
		{"Category": "Input Boundary Attacks", "Attack Vector": "Empty/null values", "Result": "DEFENDED", "Evidence": "ok"},
		{"Category": "Input Boundary Attacks", "Attack Vector": "Injection", "Result": "DEFENDED", "Evidence": "ok"},
	}
	issues := accCheckCoverage(selected, vectors, rows, "Sensitive")
	if len(issues) != 0 {
		t.Errorf("expected no issues (non-required vector absent), got %v", issues)
	}
}

// --- Unit tests: accParseSelectedCategories ---

func TestAccParseSelectedCategories_MatchesFromSummary(t *testing.T) {
	vectors := accParseAttackVectors(accTestAttackVectorsMD)
	selected := accParseSelectedCategories(accTestSummaryAllCovered, vectors)
	if len(selected) == 0 {
		t.Fatal("expected at least one category from summary")
	}
	found := false
	for _, s := range selected {
		if s == "Input Boundary Attacks" {
			found = true
		}
	}
	if !found {
		t.Errorf("expected 'Input Boundary Attacks' in selected, got %v", selected)
	}
}

func TestAccParseSelectedCategories_NoSummary(t *testing.T) {
	vectors := accParseAttackVectors(accTestAttackVectorsMD)
	selected := accParseSelectedCategories("# Report\n\nNo attack summary.\n", vectors)
	if len(selected) != 0 {
		t.Errorf("expected empty selection, got %v", selected)
	}
}

// --- Unit tests: accIsCovered ---

func TestAccIsCovered_ExactMatch(t *testing.T) {
	covered := map[string]struct{}{"injection": {}}
	if !accIsCovered("Injection", covered) {
		t.Error("expected exact match (case-insensitive) to be covered")
	}
}

func TestAccIsCovered_PartialMatch(t *testing.T) {
	covered := map[string]struct{}{"empty/null values": {}}
	if !accIsCovered("Empty/null values", covered) {
		t.Error("expected partial match to be covered")
	}
}

func TestAccIsCovered_NotCovered(t *testing.T) {
	covered := map[string]struct{}{"empty/null values": {}}
	if accIsCovered("Injection", covered) {
		t.Error("expected 'Injection' to be not covered")
	}
}

func TestAccIsCovered_NAVectorCountsAsCovered(t *testing.T) {
	// N/A-documented vectors appear in the covered set (they're rows in the Attack Summary).
	covered := map[string]struct{}{"injection": {}}
	if !accIsCovered("Injection", covered) {
		t.Error("expected N/A-documented vector (present in covered set) to be covered")
	}
}

// --- Unit tests: accNormalize ---

func TestAccNormalize_CollapseWhitespace(t *testing.T) {
	got := accNormalize("  Hello   World  ")
	if got != "hello world" {
		t.Errorf("expected 'hello world', got %q", got)
	}
}

// --- Integration tests: runAdversarialCoverageCheck ---

func TestAdversarialCoverageCheck_Help(t *testing.T) {
	rc, _ := runAdversarialCoverageCheckCmd(t, "--help")
	if rc != 0 {
		t.Errorf("expected rc=0 for --help, got %d", rc)
	}
}

func TestAdversarialCoverageCheck_TooFewArgs(t *testing.T) {
	rc, _ := runAdversarialCoverageCheckCmd(t, "only-one.md", "--tier", "Critical")
	if rc != 1 {
		t.Errorf("expected rc=1 for too few positional args, got %d", rc)
	}
}

func TestAdversarialCoverageCheck_MissingTier(t *testing.T) {
	rc, _ := runAdversarialCoverageCheckCmd(t, "report.md", "vectors.md")
	if rc != 1 {
		t.Errorf("expected rc=1 when --tier is missing, got %d", rc)
	}
}

func TestAdversarialCoverageCheck_InvalidTier(t *testing.T) {
	rc, _ := runAdversarialCoverageCheckCmd(t, "report.md", "vectors.md", "--tier", "Unknown")
	if rc != 1 {
		t.Errorf("expected rc=1 for invalid tier, got %d", rc)
	}
}

func TestAdversarialCoverageCheck_ReportFileNotFound(t *testing.T) {
	rc, out := runAdversarialCoverageCheckCmd(t, "/nonexistent/report.md", "/nonexistent/vectors.md", "--tier", "Critical")
	if rc != 1 {
		t.Errorf("expected rc=1, got %d", rc)
	}
	if out["code"] != "REPORT_FILE_NOT_FOUND" {
		t.Errorf("expected code=REPORT_FILE_NOT_FOUND, got %v", out["code"])
	}
}

func TestAdversarialCoverageCheck_VectorsFileNotFound(t *testing.T) {
	dir := t.TempDir()
	reportPath := filepath.Join(dir, "report.md")
	if err := os.WriteFile(reportPath, []byte("# Report\n"), 0644); err != nil {
		t.Fatal(err)
	}
	rc, out := runAdversarialCoverageCheckCmd(t, reportPath, "/nonexistent/vectors.md", "--tier", "Critical")
	if rc != 1 {
		t.Errorf("expected rc=1, got %d", rc)
	}
	if out["code"] != "ATTACK_VECTORS_FILE_NOT_FOUND" {
		t.Errorf("expected code=ATTACK_VECTORS_FILE_NOT_FOUND, got %v", out["code"])
	}
}

func TestAdversarialCoverageCheck_StandardTierSkip(t *testing.T) {
	reportPath, vectorsPath := writeAccTempFiles(t, "# Report\n", accTestAttackVectorsMD)
	rc, out := runAdversarialCoverageCheckCmd(t, reportPath, vectorsPath, "--tier", "Standard")
	if rc != 0 {
		t.Errorf("expected rc=0, got %d", rc)
	}
	if out["status"] != "SKIP" {
		t.Errorf("expected status=SKIP, got %v", out["status"])
	}
	if out["code"] != "STANDARD_TIER_NO_REQUIRED_COVERAGE" {
		t.Errorf("expected code=STANDARD_TIER_NO_REQUIRED_COVERAGE, got %v", out["code"])
	}
}

func TestAdversarialCoverageCheck_NoSelectedCategoriesSkip(t *testing.T) {
	reportPath, vectorsPath := writeAccTempFiles(t, "# Report\n\nNo attack summary.\n", accTestAttackVectorsMD)
	rc, out := runAdversarialCoverageCheckCmd(t, reportPath, vectorsPath, "--tier", "Critical")
	if rc != 0 {
		t.Errorf("expected rc=0, got %d", rc)
	}
	if out["status"] != "SKIP" {
		t.Errorf("expected status=SKIP, got %v", out["status"])
	}
	if out["code"] != "NO_SELECTED_CATEGORIES" {
		t.Errorf("expected code=NO_SELECTED_CATEGORIES, got %v", out["code"])
	}
}

func TestAdversarialCoverageCheck_AllCoveredPass(t *testing.T) {
	reportPath, vectorsPath := writeAccTempFiles(t, accTestSummaryAllCovered, accTestAttackVectorsMD)
	rc, out := runAdversarialCoverageCheckCmd(t, reportPath, vectorsPath, "--tier", "Critical")
	if rc != 0 {
		t.Errorf("expected rc=0, got %d; output: %v", rc, out)
	}
	if out["status"] != "PASS" {
		t.Errorf("expected status=PASS, got %v", out["status"])
	}
	if out["code"] != "ALL_REQUIRED_VECTORS_COVERED" {
		t.Errorf("expected code=ALL_REQUIRED_VECTORS_COVERED, got %v", out["code"])
	}
	if out["signal.issues"] != float64(0) {
		t.Errorf("expected signal.issues=0, got %v", out["signal.issues"])
	}
}

func TestAdversarialCoverageCheck_MissingVectorFail(t *testing.T) {
	reportPath, vectorsPath := writeAccTempFiles(t, accTestSummaryMissingInjection, accTestAttackVectorsMD)
	rc, out := runAdversarialCoverageCheckCmd(t, reportPath, vectorsPath, "--tier", "Critical")
	if rc != 1 {
		t.Errorf("expected rc=1, got %d", rc)
	}
	if out["status"] != "FAIL" {
		t.Errorf("expected status=FAIL, got %v", out["status"])
	}
	if out["code"] != "REQUIRED_VECTORS_NOT_COVERED" {
		t.Errorf("expected code=REQUIRED_VECTORS_NOT_COVERED, got %v", out["code"])
	}
	if out["signal.issues"] != float64(1) {
		t.Errorf("expected signal.issues=1, got %v", out["signal.issues"])
	}
	issue1, _ := out["issue.1"].(string)
	if !strings.Contains(issue1, "Injection") {
		t.Errorf("expected 'Injection' in issue.1, got %q", issue1)
	}
}

func TestAdversarialCoverageCheck_TierFlagEqualsForm(t *testing.T) {
	reportPath, vectorsPath := writeAccTempFiles(t, "# Report\n", accTestAttackVectorsMD)
	rc, out := runAdversarialCoverageCheckCmd(t, reportPath, vectorsPath, "--tier=Standard")
	if rc != 0 {
		t.Errorf("expected rc=0, got %d", rc)
	}
	if out["status"] != "SKIP" {
		t.Errorf("expected status=SKIP with --tier=Standard, got %v", out["status"])
	}
}
