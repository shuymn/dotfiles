package cmd

import (
	"bytes"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func makeReviewArtifact(sourceArtifact, sourceDigest string) string {
	return fmt.Sprintf(
		"- **Mode**: design-review\n- **Source Artifact**: %s\n- **Source Digest**: %s\n- **Reviewed At**: 2026-01-01T00:00:00Z\n- **Overall Verdict**: PASS\n",
		sourceArtifact, sourceDigest,
	)
}

func runCmd(args ...string) (int, map[string]any) {
	var buf bytes.Buffer
	rc := runFreshnessPreflight(&buf, args)
	var result map[string]any
	if line := strings.TrimSpace(buf.String()); line != "" {
		if err := json.Unmarshal([]byte(line), &result); err != nil {
			return rc, map[string]any{"_raw": line, "_err": err.Error()}
		}
	}
	return rc, result
}

// --- Unit tests: checkArtifact ---

func TestFreshArtifactPass(t *testing.T) {
	tmp := t.TempDir()
	content := []byte("# Design\n")
	srcPath := filepath.Join(tmp, "design.md")
	if err := os.WriteFile(srcPath, content, 0644); err != nil {
		t.Fatal(err)
	}
	digest := sha256Bytes(content)

	reviewPath := filepath.Join(tmp, "design.review.md")
	if err := os.WriteFile(reviewPath, []byte(makeReviewArtifact("design.md", digest)), 0644); err != nil {
		t.Fatal(err)
	}

	status, name, _ := checkArtifact(reviewPath, tmp)
	if status != "PASS" {
		t.Errorf("expected PASS, got %q", status)
	}
	if name != "design.review.md" {
		t.Errorf("expected name design.review.md, got %q", name)
	}
}

func TestStaleArtifactStale(t *testing.T) {
	tmp := t.TempDir()
	srcPath := filepath.Join(tmp, "design.md")
	if err := os.WriteFile(srcPath, []byte("# Design v1\n"), 0644); err != nil {
		t.Fatal(err)
	}
	staleDigest := sha256Bytes([]byte("# Design old\n"))

	reviewPath := filepath.Join(tmp, "design.review.md")
	if err := os.WriteFile(reviewPath, []byte(makeReviewArtifact("design.md", staleDigest)), 0644); err != nil {
		t.Fatal(err)
	}

	status, _, issue := checkArtifact(reviewPath, tmp)
	if status != "STALE" {
		t.Errorf("expected STALE, got %q", status)
	}
	if !strings.Contains(issue, "mismatch") {
		t.Errorf("expected 'mismatch' in issue, got %q", issue)
	}
}

func TestNoDigestSkip(t *testing.T) {
	tmp := t.TempDir()
	reviewPath := filepath.Join(tmp, "design.review.md")
	if err := os.WriteFile(reviewPath, []byte("# Review\n\n- **Overall Verdict**: PASS\n"), 0644); err != nil {
		t.Fatal(err)
	}

	status, _, _ := checkArtifact(reviewPath, tmp)
	if status != "SKIP" {
		t.Errorf("expected SKIP, got %q", status)
	}
}

func TestSourceNotFoundSkip(t *testing.T) {
	tmp := t.TempDir()
	reviewPath := filepath.Join(tmp, "design.review.md")
	if err := os.WriteFile(reviewPath, []byte(makeReviewArtifact("nonexistent.md", strings.Repeat("a", 64))), 0644); err != nil {
		t.Fatal(err)
	}

	status, _, issue := checkArtifact(reviewPath, tmp)
	if status != "SKIP" {
		t.Errorf("expected SKIP, got %q", status)
	}
	if !strings.Contains(issue, "not found") {
		t.Errorf("expected 'not found' in issue, got %q", issue)
	}
}

// --- Integration tests: runFreshnessPreflight ---

func TestNoArtifactFilesSkip(t *testing.T) {
	tmp := t.TempDir()
	rc, out := runCmd(tmp)
	if rc != 0 {
		t.Errorf("expected rc=0, got %d", rc)
	}
	if out["status"] != "SKIP" {
		t.Errorf("expected status=SKIP, got %v", out["status"])
	}
	if out["code"] != "NO_REVIEW_ARTIFACTS" {
		t.Errorf("expected code=NO_REVIEW_ARTIFACTS, got %v", out["code"])
	}
}

func TestAllFreshPass(t *testing.T) {
	tmp := t.TempDir()
	content := []byte("# Design\n")
	srcPath := filepath.Join(tmp, "design.md")
	if err := os.WriteFile(srcPath, content, 0644); err != nil {
		t.Fatal(err)
	}
	digest := sha256Bytes(content)

	reviewPath := filepath.Join(tmp, "design.review.md")
	if err := os.WriteFile(reviewPath, []byte(makeReviewArtifact("design.md", digest)), 0644); err != nil {
		t.Fatal(err)
	}

	rc, out := runCmd(tmp)
	if rc != 0 {
		t.Errorf("expected rc=0, got %d", rc)
	}
	if out["status"] != "PASS" {
		t.Errorf("expected status=PASS, got %v", out["status"])
	}
	if out["signal.stale"] != float64(0) {
		t.Errorf("expected signal.stale=0, got %v", out["signal.stale"])
	}
}

func TestStaleArtifactFail(t *testing.T) {
	tmp := t.TempDir()
	srcPath := filepath.Join(tmp, "design.md")
	if err := os.WriteFile(srcPath, []byte("# Current content\n"), 0644); err != nil {
		t.Fatal(err)
	}
	staleDigest := sha256Bytes([]byte("# Old content\n"))

	reviewPath := filepath.Join(tmp, "design.review.md")
	if err := os.WriteFile(reviewPath, []byte(makeReviewArtifact("design.md", staleDigest)), 0644); err != nil {
		t.Fatal(err)
	}

	rc, out := runCmd(tmp)
	if rc != 1 {
		t.Errorf("expected rc=1, got %d", rc)
	}
	if out["status"] != "FAIL" {
		t.Errorf("expected status=FAIL, got %v", out["status"])
	}
	if out["signal.stale"] != float64(1) {
		t.Errorf("expected signal.stale=1, got %v", out["signal.stale"])
	}
	if out["code"] != "STALE_REVIEW_ARTIFACTS" {
		t.Errorf("expected code=STALE_REVIEW_ARTIFACTS, got %v", out["code"])
	}
}

func TestTopicDirNotFound(t *testing.T) {
	rc, out := runCmd("/nonexistent/topic/dir/xyz")
	if rc != 1 {
		t.Errorf("expected rc=1, got %d", rc)
	}
	if out["code"] != "TOPIC_DIR_NOT_FOUND" {
		t.Errorf("expected code=TOPIC_DIR_NOT_FOUND, got %v", out["code"])
	}
}
