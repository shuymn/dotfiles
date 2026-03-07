package workflow

import (
	"crypto/sha256"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

// --- Fixture helpers (shared with gatecheck_smoke_test.go) ---

func gcTestWriteReviewFile(t *testing.T, dir, content string) string {
	t.Helper()
	path := filepath.Join(dir, "review.md")
	if err := os.WriteFile(path, []byte(content), 0644); err != nil {
		t.Fatal(err)
	}
	return path
}

func gcTestWriteSourceFile(t *testing.T, dir, content string) string {
	t.Helper()
	path := filepath.Join(dir, "source.md")
	if err := os.WriteFile(path, []byte(content), 0644); err != nil {
		t.Fatal(err)
	}
	return path
}

func gcTestComputeDigest(t *testing.T, path string) string {
	t.Helper()
	data, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	return fmt.Sprintf("%x", sha256.Sum256(data))
}

func gcTestMakePassingReview(t *testing.T, dir, sourceDigest string) string {
	t.Helper()
	content := fmt.Sprintf(`- **Mode**: plan-review
- **Source Artifact**: source.md
- **Source Digest**: %s
- **Reviewed At**: 2024-01-01T00:00:00Z
- **Isolation**: sub-agent
- **Overall Verdict**: PASS

## Checklist

- Criterion A: PASS
- Criterion B: PASS
`, sourceDigest)
	return gcTestWriteReviewFile(t, dir, content)
}

func gcTestMakeDodRecheckReview(t *testing.T, dir, sourceDigest string) string {
	t.Helper()
	content := fmt.Sprintf(`- **Mode**: dod-recheck
- **Source Artifact**: source.md
- **Source Digest**: %s
- **Reviewed At**: 2024-01-01T00:00:00Z
- **Isolation**: sub-agent
- **Overall Verdict**: PASS

## DoD Verification

| # | Command | Exit Code | Expected | Actual | Verdict |
|---|---------|-----------|----------|--------|---------|
| 1 | go test ./... | 0 | 0 | 0 | PASS |

## Quality Gate Verification

| # | Command | Exit Code | Verdict |
|---|---------|-----------|---------|
| 1 | make build | 0 | PASS |
`, sourceDigest)
	return gcTestWriteReviewFile(t, dir, content)
}

// --- Go implementation test runner ---

func runGateCheckCmd(args ...string) (int, map[string]any) {
	rc, stdout, _, err := runCommandOutput(GateCheck(), "", args...)
	if err != nil {
		return 1, map[string]any{"_err": err.Error()}
	}
	return rc, parseJSONResult(stdout)
}

// --- Test cases ---

func TestGateCheck_InvalidArgCount(t *testing.T) {
	tests := []struct {
		args []string
		code string
	}{
		{args: []string{}, code: "MISSING_REQUIRED_ARGUMENT"},
		{args: []string{"only-one"}, code: "MISSING_REQUIRED_ARGUMENT"},
		{args: []string{"a", "b", "c"}, code: "TOO_MANY_ARGUMENTS"},
	}
	for _, tc := range tests {
		rc, result := runGateCheckCmd(tc.args...)
		if rc != 1 {
			t.Errorf("args=%v: expected exit 1, got %d", tc.args, rc)
		}
		if result["code"] != tc.code {
			t.Errorf("args=%v: expected %s, got %v", tc.args, tc.code, result["code"])
		}
	}
}

func TestGateCheck_ReviewFileMissing(t *testing.T) {
	dir := t.TempDir()
	srcPath := gcTestWriteSourceFile(t, dir, "# Source\n")
	rc, result := runGateCheckCmd("/nonexistent/review.md", srcPath)
	if rc != 1 {
		t.Fatalf("expected exit 1, got %d", rc)
	}
	if result["code"] != "REVIEW_FILE_NOT_FOUND" {
		t.Errorf("expected REVIEW_FILE_NOT_FOUND, got %v", result["code"])
	}
}

func TestGateCheck_SourceFileMissing(t *testing.T) {
	dir := t.TempDir()
	digest := fmt.Sprintf("%x", sha256.Sum256([]byte("# Source\n")))
	reviewPath := gcTestMakePassingReview(t, dir, digest)
	rc, result := runGateCheckCmd(reviewPath, "/nonexistent/source.md")
	if rc != 1 {
		t.Fatalf("expected exit 1, got %d", rc)
	}
	if result["code"] != "SOURCE_FILE_NOT_FOUND" {
		t.Errorf("expected SOURCE_FILE_NOT_FOUND, got %v", result["code"])
	}
}

func TestGateCheck_MissingOverallVerdict(t *testing.T) {
	dir := t.TempDir()
	srcPath := gcTestWriteSourceFile(t, dir, "# Source\n")
	digest := gcTestComputeDigest(t, srcPath)
	reviewPath := gcTestWriteReviewFile(t, dir, fmt.Sprintf("- **Source Digest**: %s\nNo verdict here.\n", digest))
	rc, result := runGateCheckCmd(reviewPath, srcPath)
	if rc != 1 {
		t.Fatalf("expected exit 1, got %d", rc)
	}
	if result["code"] != "MISSING_OVERALL_VERDICT" {
		t.Errorf("expected MISSING_OVERALL_VERDICT, got %v", result["code"])
	}
}

func TestGateCheck_OverallVerdictFail(t *testing.T) {
	dir := t.TempDir()
	srcPath := gcTestWriteSourceFile(t, dir, "# Source\n")
	digest := gcTestComputeDigest(t, srcPath)
	reviewPath := gcTestWriteReviewFile(t, dir, fmt.Sprintf("- **Overall Verdict**: FAIL\n- **Source Digest**: %s\n", digest))
	rc, result := runGateCheckCmd(reviewPath, srcPath)
	if rc != 1 {
		t.Fatalf("expected exit 1, got %d", rc)
	}
	if result["code"] != "OVERALL_VERDICT_NOT_PASS" {
		t.Errorf("expected OVERALL_VERDICT_NOT_PASS, got %v", result["code"])
	}
}

func TestGateCheck_InvalidVerdictValue(t *testing.T) {
	dir := t.TempDir()
	srcPath := gcTestWriteSourceFile(t, dir, "# Source\n")
	reviewPath := gcTestWriteReviewFile(t, dir, "- **Overall Verdict**: PASS | FAIL\n")
	rc, result := runGateCheckCmd(reviewPath, srcPath)
	if rc != 1 {
		t.Fatalf("expected exit 1, got %d", rc)
	}
	if result["code"] != "INVALID_OVERALL_VERDICT_VALUE" {
		t.Errorf("expected INVALID_OVERALL_VERDICT_VALUE, got %v", result["code"])
	}
}

func TestGateCheck_MissingSourceDigest(t *testing.T) {
	dir := t.TempDir()
	srcPath := gcTestWriteSourceFile(t, dir, "# Source\n")
	reviewPath := gcTestWriteReviewFile(t, dir, "- **Overall Verdict**: PASS\nNo digest here.\n")
	rc, result := runGateCheckCmd(reviewPath, srcPath)
	if rc != 1 {
		t.Fatalf("expected exit 1, got %d", rc)
	}
	if result["code"] != "MISSING_SOURCE_DIGEST" {
		t.Errorf("expected MISSING_SOURCE_DIGEST, got %v", result["code"])
	}
}

func TestGateCheck_SourceDigestMismatch(t *testing.T) {
	dir := t.TempDir()
	srcPath := gcTestWriteSourceFile(t, dir, "# Source\n")
	badDigest := strings.Repeat("0", 63) + "1"
	reviewPath := gcTestWriteReviewFile(t, dir, fmt.Sprintf("- **Overall Verdict**: PASS\n- **Source Digest**: %s\n", badDigest))
	rc, result := runGateCheckCmd(reviewPath, srcPath)
	if rc != 1 {
		t.Fatalf("expected exit 1, got %d", rc)
	}
	if result["code"] != "SOURCE_DIGEST_MISMATCH" {
		t.Errorf("expected SOURCE_DIGEST_MISMATCH, got %v", result["code"])
	}
}

func TestGateCheck_SubVerdictListFail(t *testing.T) {
	dir := t.TempDir()
	srcPath := gcTestWriteSourceFile(t, dir, "# Source\n")
	digest := gcTestComputeDigest(t, srcPath)
	reviewPath := gcTestWriteReviewFile(t, dir, fmt.Sprintf(`- **Overall Verdict**: PASS
- **Source Digest**: %s

## Checklist

- Criterion A: PASS
- Criterion B: FAIL
`, digest))
	rc, result := runGateCheckCmd(reviewPath, srcPath)
	if rc != 1 {
		t.Fatalf("expected exit 1, got %d", rc)
	}
	if result["code"] != "SUB_VERDICT_FAILURES" {
		t.Errorf("expected SUB_VERDICT_FAILURES, got %v", result["code"])
	}
}

func TestGateCheck_SubVerdictTableFail(t *testing.T) {
	dir := t.TempDir()
	srcPath := gcTestWriteSourceFile(t, dir, "# Source\n")
	digest := gcTestComputeDigest(t, srcPath)
	reviewPath := gcTestWriteReviewFile(t, dir, fmt.Sprintf(`- **Overall Verdict**: PASS
- **Source Digest**: %s

## Review Criteria

| # | Criterion | Verdict | Evidence |
|---|-----------|---------|----------|
| 1 | Something | FAIL | reason |
`, digest))
	rc, result := runGateCheckCmd(reviewPath, srcPath)
	if rc != 1 {
		t.Fatalf("expected exit 1, got %d", rc)
	}
	if result["code"] != "SUB_VERDICT_FAILURES" {
		t.Errorf("expected SUB_VERDICT_FAILURES, got %v", result["code"])
	}
}

func TestGateCheck_SubVerdictNAAccepted(t *testing.T) {
	dir := t.TempDir()
	srcPath := gcTestWriteSourceFile(t, dir, "# Source\n")
	digest := gcTestComputeDigest(t, srcPath)
	reviewPath := gcTestWriteReviewFile(t, dir, fmt.Sprintf(`- **Overall Verdict**: PASS
- **Source Digest**: %s

## Checklist

- Criterion A: N/A
`, digest))
	rc, result := runGateCheckCmd(reviewPath, srcPath)
	if rc != 0 {
		t.Fatalf("expected exit 0, got %d: %v", rc, result)
	}
	if result["code"] != "ALL_CHECKS_PASSED" {
		t.Errorf("expected ALL_CHECKS_PASSED, got %v", result["code"])
	}
}

func TestGateCheck_DodNonzeroExitCode(t *testing.T) {
	dir := t.TempDir()
	srcPath := gcTestWriteSourceFile(t, dir, "# Source\n")
	digest := gcTestComputeDigest(t, srcPath)
	reviewPath := gcTestWriteReviewFile(t, dir, fmt.Sprintf(`- **Overall Verdict**: PASS
- **Source Digest**: %s

## DoD Verification

| # | Command | Exit Code | Expected | Actual | Verdict |
|---|---------|-----------|----------|--------|---------|
| 1 | go test ./... | 1 | 0 | 1 | FAIL |
`, digest))
	rc, result := runGateCheckCmd(reviewPath, srcPath)
	if rc != 1 {
		t.Fatalf("expected exit 1, got %d", rc)
	}
	if result["code"] != "NONZERO_EXIT_CODES" {
		t.Errorf("expected NONZERO_EXIT_CODES, got %v", result["code"])
	}
}

func TestGateCheck_QGateNonzeroExitCode(t *testing.T) {
	dir := t.TempDir()
	srcPath := gcTestWriteSourceFile(t, dir, "# Source\n")
	digest := gcTestComputeDigest(t, srcPath)
	reviewPath := gcTestWriteReviewFile(t, dir, fmt.Sprintf(`- **Overall Verdict**: PASS
- **Source Digest**: %s

## DoD Verification

| # | Command | Exit Code | Expected | Actual | Verdict |
|---|---------|-----------|----------|--------|---------|
| 1 | go test ./... | 0 | 0 | 0 | PASS |

## Quality Gate Verification

| # | Command | Exit Code | Verdict |
|---|---------|-----------|---------|
| 1 | make build | 2 | FAIL |
`, digest))
	rc, result := runGateCheckCmd(reviewPath, srcPath)
	if rc != 1 {
		t.Fatalf("expected exit 1, got %d", rc)
	}
	if result["code"] != "NONZERO_EXIT_CODES" {
		t.Errorf("expected NONZERO_EXIT_CODES, got %v", result["code"])
	}
}

func TestGateCheck_AllPass(t *testing.T) {
	dir := t.TempDir()
	srcPath := gcTestWriteSourceFile(t, dir, "# Source\n")
	digest := gcTestComputeDigest(t, srcPath)
	reviewPath := gcTestMakePassingReview(t, dir, digest)
	rc, result := runGateCheckCmd(reviewPath, srcPath)
	if rc != 0 {
		t.Fatalf("expected exit 0, got %d: %v", rc, result)
	}
	if result["code"] != "ALL_CHECKS_PASSED" {
		t.Errorf("expected ALL_CHECKS_PASSED, got %v", result["code"])
	}
}

func TestGateCheck_AllPassDodRecheck(t *testing.T) {
	dir := t.TempDir()
	srcPath := gcTestWriteSourceFile(t, dir, "# Source\n")
	digest := gcTestComputeDigest(t, srcPath)
	reviewPath := gcTestMakeDodRecheckReview(t, dir, digest)
	rc, result := runGateCheckCmd(reviewPath, srcPath)
	if rc != 0 {
		t.Fatalf("expected exit 0, got %d: %v", rc, result)
	}
	if result["code"] != "ALL_CHECKS_PASSED" {
		t.Errorf("expected ALL_CHECKS_PASSED, got %v", result["code"])
	}
}

func TestGateCheck_BoldFormatAccepted(t *testing.T) {
	dir := t.TempDir()
	srcPath := gcTestWriteSourceFile(t, dir, "# Source\n")
	digest := gcTestComputeDigest(t, srcPath)
	// Use bold Overall Verdict (digest-stamp format)
	reviewPath := gcTestWriteReviewFile(t, dir, fmt.Sprintf(`- **Mode**: plan-review
- **Source Artifact**: source.md
- **Source Digest**: %s
- **Reviewed At**: 2024-01-01T00:00:00Z
- **Overall Verdict**: PASS

- Criterion A: PASS
`, digest))
	rc, result := runGateCheckCmd(reviewPath, srcPath)
	if rc != 0 {
		t.Fatalf("expected exit 0, got %d: %v", rc, result)
	}
	if result["code"] != "ALL_CHECKS_PASSED" {
		t.Errorf("expected ALL_CHECKS_PASSED, got %v", result["code"])
	}
}

func TestGateCheck_DodTableExcludedFromSubVerdicts(t *testing.T) {
	// FAIL verdict in DoD table must not trigger SUB_VERDICT_FAILURES.
	dir := t.TempDir()
	srcPath := gcTestWriteSourceFile(t, dir, "# Source\n")
	digest := gcTestComputeDigest(t, srcPath)
	reviewPath := gcTestWriteReviewFile(t, dir, fmt.Sprintf(`- **Overall Verdict**: PASS
- **Source Digest**: %s

## DoD Verification

| # | Command | Exit Code | Expected | Actual | Verdict |
|---|---------|-----------|----------|--------|---------|
| 1 | go test ./... | 0 | 0 | 0 | PASS |
`, digest))
	rc, result := runGateCheckCmd(reviewPath, srcPath)
	if rc != 0 {
		t.Fatalf("expected exit 0, got %d: %v", rc, result)
	}
	if result["code"] != "ALL_CHECKS_PASSED" {
		t.Errorf("expected ALL_CHECKS_PASSED, got %v", result["code"])
	}
}
