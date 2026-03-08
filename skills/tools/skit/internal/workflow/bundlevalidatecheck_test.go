package workflow

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func runBundleValidateCheckCmd(args ...string) (int, map[string]any) {
	rc, stdout, _, err := runCommandOutput(BundleValidateCheck(), "", args...)
	if err != nil {
		return 1, map[string]any{"_err": err.Error()}
	}
	return rc, parseJSONResult(stdout)
}

func writeTempPlan(t *testing.T, content string) string {
	t.Helper()
	p := filepath.Join(t.TempDir(), "plan.md")
	if err := os.WriteFile(p, []byte(content), 0644); err != nil {
		t.Fatal(err)
	}
	return p
}

func makeCheckpointKV(overrides map[string]string) string {
	kv := map[string]string{
		"Alignment Verdict":    "PASS",
		"Scope Contract Guard": "PASS",
		"Quality Gate Guard":   "PASS",
		"Review Artifact":      "docs/plans/topic/plan.review.md",
		"Trace Pack":           "docs/plans/topic/plan.trace.md",
		"Compose Pack":         "docs/plans/topic/plan.compose.md",
		"Updated At":           "2026-03-09",
	}
	for k, v := range overrides {
		kv[k] = v
	}
	var sb strings.Builder
	for _, k := range bundleRequiredKeys {
		sb.WriteString("- **" + k + "**: " + kv[k] + "\n")
	}
	return sb.String()
}

func TestBundleValidateCheck_FileNotFound(t *testing.T) {
	rc, out := runBundleValidateCheckCmd("/nonexistent/plan.md")
	if rc != 1 || out["code"] != "PLAN_FILE_NOT_FOUND" {
		t.Fatalf("unexpected output: rc=%d out=%v", rc, out)
	}
}

func TestBundleValidateCheck_MissingRequiredKey(t *testing.T) {
	plan := "# Plan\n\n## Checkpoint Summary\n\n- **Alignment Verdict**: PASS\n"
	p := writeTempPlan(t, plan)
	rc, out := runBundleValidateCheckCmd(p)
	if rc != 1 || out["code"] != "BUNDLE_VALIDATION_FAILED" {
		t.Fatalf("unexpected output: rc=%d out=%v", rc, out)
	}
}

func TestBundleValidateCheck_GuardMustPass(t *testing.T) {
	plan := "# Plan\n\n## Checkpoint Summary\n\n" + makeCheckpointKV(map[string]string{
		"Scope Contract Guard": "FAIL",
	}) + "\n"
	p := writeTempPlan(t, plan)
	rc, out := runBundleValidateCheckCmd(p)
	if rc != 1 || out["code"] != "BUNDLE_VALIDATION_FAILED" {
		t.Fatalf("unexpected output: rc=%d out=%v", rc, out)
	}
}

func TestBundleValidateCheck_ValidBundle(t *testing.T) {
	dir := t.TempDir()
	planDir := filepath.Join(dir, "docs", "plans", "topic")
	if err := os.MkdirAll(planDir, 0755); err != nil {
		t.Fatal(err)
	}
	for _, name := range []string{"plan.review.md", "plan.trace.md", "plan.compose.md"} {
		if err := os.WriteFile(filepath.Join(planDir, name), []byte("# ok\n"), 0644); err != nil {
			t.Fatal(err)
		}
	}

	plan := strings.Join([]string{
		"# Plan",
		"",
		"- **Trace Pack**: `docs/plans/topic/plan.trace.md`",
		"- **Compose Pack**: `docs/plans/topic/plan.compose.md`",
		"",
		"## Checkpoint Summary",
		"",
		makeCheckpointKV(nil),
	}, "\n")
	planPath := filepath.Join(dir, "plan.md")
	if err := os.WriteFile(planPath, []byte(plan), 0644); err != nil {
		t.Fatal(err)
	}

	rc, out := runBundleValidateCheckCmd(planPath)
	if rc != 0 || out["status"] != "PASS" {
		t.Fatalf("unexpected output: rc=%d out=%v", rc, out)
	}
}

func TestBundleValidateCheck_RepoRelativeLinksFromNestedPlan(t *testing.T) {
	dir := t.TempDir()
	planDir := filepath.Join(dir, "docs", "plans", "topic")
	if err := os.MkdirAll(planDir, 0755); err != nil {
		t.Fatal(err)
	}
	for _, name := range []string{"plan.review.md", "plan.trace.md", "plan.compose.md"} {
		if err := os.WriteFile(filepath.Join(planDir, name), []byte("# ok\n"), 0644); err != nil {
			t.Fatal(err)
		}
	}

	plan := strings.Join([]string{
		"# Plan",
		"",
		"- **Trace Pack**: `docs/plans/topic/plan.trace.md`",
		"- **Compose Pack**: `docs/plans/topic/plan.compose.md`",
		"",
		"## Checkpoint Summary",
		"",
		makeCheckpointKV(nil),
	}, "\n")
	planPath := filepath.Join(planDir, "plan.md")
	if err := os.WriteFile(planPath, []byte(plan), 0644); err != nil {
		t.Fatal(err)
	}

	rc, out := runBundleValidateCheckCmd(planPath)
	if rc != 0 || out["status"] != "PASS" {
		t.Fatalf("unexpected output: rc=%d out=%v", rc, out)
	}
}
