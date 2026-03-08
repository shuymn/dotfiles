package workflow

import (
	"fmt"
	"os"
	"os/exec"
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

func initGitRepo(t *testing.T) (string, string) {
	t.Helper()
	dir := t.TempDir()
	run := func(args ...string) string {
		t.Helper()
		cmd := exec.Command(args[0], args[1:]...)
		cmd.Dir = dir
		out, err := cmd.CombinedOutput()
		if err != nil {
			t.Fatalf("%v failed: %v\n%s", args, err, string(out))
		}
		return strings.TrimSpace(string(out))
	}

	run("git", "init")
	run("git", "config", "user.email", "test@example.com")
	run("git", "config", "user.name", "Test User")
	return dir, run("git", "rev-parse", "--show-toplevel")
}

func commitAll(t *testing.T, dir, message string) string {
	t.Helper()
	run := func(args ...string) string {
		t.Helper()
		cmd := exec.Command(args[0], args[1:]...)
		cmd.Dir = dir
		out, err := cmd.CombinedOutput()
		if err != nil {
			t.Fatalf("%v failed: %v\n%s", args, err, string(out))
		}
		return strings.TrimSpace(string(out))
	}
	run("git", "add", ".")
	run("git", "commit", "-m", message)
	return run("git", "rev-parse", "HEAD")
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
	repoDir, _ := initGitRepo(t)
	plan := "# Plan\n\n### Task 1: One\n- **Owned Paths**:\n  - `src/feature/**`\n\n### Task 2: Two\n- **Owned Paths**:\n  - `docs/**`\n"
	if err := os.MkdirAll(filepath.Join(repoDir, "src/feature"), 0755); err != nil {
		t.Fatal(err)
	}
	if err := os.MkdirAll(filepath.Join(repoDir, "docs"), 0755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(repoDir, "plan.md"), []byte(plan), 0644); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(repoDir, "src/feature/main.txt"), []byte("base\n"), 0644); err != nil {
		t.Fatal(err)
	}
	base := commitAll(t, repoDir, "base")

	if err := os.WriteFile(filepath.Join(repoDir, "src/feature/main.txt"), []byte("updated\n"), 0644); err != nil {
		t.Fatal(err)
	}
	taskDigest := computeTaskContractDigest(extractTaskBlock(plan, 1))
	artifact := makeTaskArtifact("plan.md", 1, taskDigest, base, []string{"src/feature/main.txt"})
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
	repoDir, _ := initGitRepo(t)
	plan := "# Plan\n\n### Task 1: One\n- **Owned Paths**:\n  - `src/feature/**`\n"
	if err := os.MkdirAll(filepath.Join(repoDir, "src/feature"), 0755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(repoDir, "plan.md"), []byte(plan), 0644); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(repoDir, "src/feature/main.txt"), []byte("base\n"), 0644); err != nil {
		t.Fatal(err)
	}
	base := commitAll(t, repoDir, "base")

	if err := os.WriteFile(filepath.Join(repoDir, "src/feature/main.txt"), []byte("updated\n"), 0644); err != nil {
		t.Fatal(err)
	}
	taskDigest := computeTaskContractDigest(extractTaskBlock(plan, 1))
	artifactPath := filepath.Join(repoDir, "topic-task-1.dod-recheck.md")
	if err := os.WriteFile(artifactPath, []byte(makeTaskArtifact("plan.md", 1, taskDigest, base, []string{"src/feature/main.txt"})), 0644); err != nil {
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
	repoDir, _ := initGitRepo(t)
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
