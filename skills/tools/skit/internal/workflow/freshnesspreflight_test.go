package workflow

import (
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

func makeTaskArtifact(sourceArtifact string, taskID int, taskDigest, baseCommit string, implFiles []string) string {
	lines := []string{
		"- **Mode**: dod-recheck",
		fmt.Sprintf("- **Source Artifact**: %s", sourceArtifact),
		fmt.Sprintf("- **Task ID**: Task %d", taskID),
		fmt.Sprintf("- **Task Contract Digest**: %s", taskDigest),
		fmt.Sprintf("- **Base Commit**: %s", baseCommit),
		"- **Implementation Files**:",
	}
	for _, file := range implFiles {
		lines = append(lines, "  - "+file)
	}
	lines = append(lines, "- **Overall Verdict**: PASS")
	return strings.Join(lines, "\n") + "\n"
}

func runCmd(args ...string) (int, map[string]any) {
	rc, stdout, _, err := runCommandOutput(FreshnessPreflight(), "", args...)
	if err != nil {
		return 1, map[string]any{"_err": err.Error()}
	}
	return rc, parseJSONResult(stdout)
}

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
	if status != "PASS" || name != "design.review.md" {
		t.Fatalf("unexpected result: status=%q name=%q", status, name)
	}
}

func TestRunFreshnessPreflight_DefaultBaseDirSupportsRepoRelativeArtifact(t *testing.T) {
	root := t.TempDir()
	topicDir := filepath.Join(root, "docs", "plans", "topic")
	if err := os.MkdirAll(topicDir, 0755); err != nil {
		t.Fatal(err)
	}

	content := []byte("# Design\n")
	srcPath := filepath.Join(topicDir, "design.md")
	if err := os.WriteFile(srcPath, content, 0644); err != nil {
		t.Fatal(err)
	}
	reviewPath := filepath.Join(topicDir, "design.review.md")
	if err := os.WriteFile(reviewPath, []byte(makeReviewArtifact("docs/plans/topic/design.md", sha256Bytes(content))), 0644); err != nil {
		t.Fatal(err)
	}

	rc, out := runCmd(topicDir)
	if rc != 0 {
		t.Fatalf("expected exit 0, got %d: %v", rc, out)
	}
	if out["code"] != "ALL_ARTIFACTS_FRESH" {
		t.Fatalf("expected ALL_ARTIFACTS_FRESH, got %v", out["code"])
	}
}

func TestStaleWholeSourceArtifact(t *testing.T) {
	tmp := t.TempDir()
	srcPath := filepath.Join(tmp, "design.md")
	if err := os.WriteFile(srcPath, []byte("# Design v2\n"), 0644); err != nil {
		t.Fatal(err)
	}
	reviewPath := filepath.Join(tmp, "design.review.md")
	if err := os.WriteFile(reviewPath, []byte(makeReviewArtifact("design.md", sha256Bytes([]byte("# Design v1\n")))), 0644); err != nil {
		t.Fatal(err)
	}

	status, _, issue := checkArtifact(reviewPath, tmp)
	if status != "STALE" || !strings.Contains(issue, "digest mismatch") {
		t.Fatalf("unexpected result: status=%q issue=%q", status, issue)
	}
}

func TestTaskScopedArtifactIgnoresOtherTaskEdits(t *testing.T) {
	repoDir := t.TempDir()
	stubGit(t, repoDir, []string{"src/feature/main.txt"})

	plan := "# Plan\n\n### Task 1: One\n- **Owned Paths**:\n  - `src/feature/**`\n\n### Task 2: Two\n- **Owned Paths**:\n  - `docs/**`\n"
	if err := os.MkdirAll(filepath.Join(repoDir, "src/feature"), 0755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(repoDir, "plan.md"), []byte(plan), 0644); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(repoDir, "src/feature/main.txt"), []byte("updated\n"), 0644); err != nil {
		t.Fatal(err)
	}

	taskDigest := computeTaskContractDigest(extractTaskBlock(plan, 1))
	artifact := makeTaskArtifact("plan.md", 1, taskDigest, "abcdef1234567", []string{"src/feature/main.txt"})
	artifactPath := filepath.Join(repoDir, "topic-task-1.dod-recheck.md")
	if err := os.WriteFile(artifactPath, []byte(artifact), 0644); err != nil {
		t.Fatal(err)
	}

	updatedPlan := strings.Replace(plan, "### Task 2: Two", "### Task 2: Two Updated", 1)
	if err := os.WriteFile(filepath.Join(repoDir, "plan.md"), []byte(updatedPlan), 0644); err != nil {
		t.Fatal(err)
	}

	status, _, issue := checkArtifact(artifactPath, repoDir)
	if status != "PASS" {
		t.Fatalf("expected PASS, got status=%q issue=%q", status, issue)
	}
}

func TestTaskScopedArtifactStaleOnTaskContractChange(t *testing.T) {
	repoDir := t.TempDir()
	stubGit(t, repoDir, []string{"src/feature/main.txt"})

	plan := "# Plan\n\n### Task 1: One\n- **Owned Paths**:\n  - `src/feature/**`\n"
	if err := os.MkdirAll(filepath.Join(repoDir, "src/feature"), 0755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(repoDir, "plan.md"), []byte(plan), 0644); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(repoDir, "src/feature/main.txt"), []byte("updated\n"), 0644); err != nil {
		t.Fatal(err)
	}

	taskDigest := computeTaskContractDigest(extractTaskBlock(plan, 1))
	artifactPath := filepath.Join(repoDir, "topic-task-1.dod-recheck.md")
	if err := os.WriteFile(artifactPath, []byte(makeTaskArtifact("plan.md", 1, taskDigest, "abcdef1234567", []string{"src/feature/main.txt"})), 0644); err != nil {
		t.Fatal(err)
	}

	changedPlan := strings.Replace(plan, "`src/feature/**`", "`src/**`", 1)
	if err := os.WriteFile(filepath.Join(repoDir, "plan.md"), []byte(changedPlan), 0644); err != nil {
		t.Fatal(err)
	}

	status, _, issue := checkArtifact(artifactPath, repoDir)
	if status != "STALE" || !strings.Contains(issue, "task contract digest mismatch") {
		t.Fatalf("unexpected result: status=%q issue=%q", status, issue)
	}
}

func TestTaskScopedArtifactMissingMetadataIsInvalid(t *testing.T) {
	repoDir := t.TempDir()
	if err := os.WriteFile(filepath.Join(repoDir, "plan.md"), []byte("# Plan\n"), 0644); err != nil {
		t.Fatal(err)
	}
	artifactPath := filepath.Join(repoDir, "topic-task-1.dod-recheck.md")
	if err := os.WriteFile(artifactPath, []byte("- **Source Artifact**: plan.md\n"), 0644); err != nil {
		t.Fatal(err)
	}

	status, _, issue := checkArtifact(artifactPath, repoDir)
	if status != "INVALID" || !strings.Contains(issue, "Task ID") {
		t.Fatalf("unexpected result: status=%q issue=%q", status, issue)
	}
}

func TestRunFreshnessPreflight_FailsForInvalidArtifact(t *testing.T) {
	tmp := t.TempDir()
	if err := os.WriteFile(filepath.Join(tmp, "task.dod-recheck.md"), []byte("- **Source Artifact**: plan.md\n"), 0644); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(tmp, "plan.md"), []byte("# Plan\n"), 0644); err != nil {
		t.Fatal(err)
	}

	rc, out := runCmd(tmp)
	if rc != 1 || out["code"] != "ARTIFACT_FRESHNESS_VIOLATIONS" {
		t.Fatalf("unexpected output: rc=%d out=%v", rc, out)
	}
}
