package cmd

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

// --- Helper ---

func makeCheckpointKV(overrides map[string]string) string {
	kv := make(map[string]string)
	for _, k := range bundleRequiredKeys {
		kv[k] = "PASS"
	}
	kv["Trace Pack"] = "docs/plans/topic/plan.trace.md"
	kv["Compose Pack"] = "docs/plans/topic/plan.compose.md"
	kv["Updated At"] = "2026-01-01"
	for k, v := range overrides {
		kv[k] = v
	}
	var sb strings.Builder
	for _, k := range bundleRequiredKeys {
		sb.WriteString("- **" + k + "**: " + kv[k] + "\n")
	}
	return sb.String()
}

// --- Unit tests: parseKV ---

func TestParseKV_BoldKV(t *testing.T) {
	text := "- **Key One**: value1\n- **Key Two**: value2\n"
	kv := parseKV(text)
	if kv["Key One"] != "value1" {
		t.Errorf("expected value1, got %q", kv["Key One"])
	}
	if kv["Key Two"] != "value2" {
		t.Errorf("expected value2, got %q", kv["Key Two"])
	}
}

// --- Integration tests: runBundleValidateCheck ---

func TestBundleValidateCheck_FileNotFound(t *testing.T) {
	rc, out := runBundleValidateCheckCmd("/nonexistent/plan.md")
	if rc != 1 {
		t.Errorf("expected rc=1, got %d", rc)
	}
	if out["code"] != "PLAN_FILE_NOT_FOUND" {
		t.Errorf("expected code=PLAN_FILE_NOT_FOUND, got %v", out["code"])
	}
}

func TestBundleValidateCheck_NoCheckpointSection(t *testing.T) {
	p := writeTempPlan(t, "# Plan\n\nNo checkpoint here.\n")
	rc, out := runBundleValidateCheckCmd(p)
	if rc != 1 {
		t.Errorf("expected rc=1, got %d", rc)
	}
	if out["code"] != "NO_CHECKPOINT_SUMMARY" {
		t.Errorf("expected code=NO_CHECKPOINT_SUMMARY, got %v", out["code"])
	}
}

func TestBundleValidateCheck_MissingKey(t *testing.T) {
	// All required keys except Alignment Verdict
	keys := []string{
		"Forward Fidelity",
		"Reverse Fidelity",
		"Non-Goal Guard",
		"Behavioral Lock Guard",
		"Temporal Completeness Guard",
		"Quality Gate Guard",
		"Integration Coverage Guard",
		"Risk Classification Guard",
		"Trace Pack",
		"Compose Pack",
		"Updated At",
	}
	var sb strings.Builder
	sb.WriteString("# Plan\n\n## Checkpoint Summary\n\n")
	for _, k := range keys {
		sb.WriteString("- **" + k + "**: PASS\n")
	}
	p := writeTempPlan(t, sb.String())
	rc, out := runBundleValidateCheckCmd(p)
	if rc != 1 {
		t.Errorf("expected rc=1, got %d", rc)
	}
	if out["code"] != "BUNDLE_VALIDATION_FAILED" {
		t.Errorf("expected code=BUNDLE_VALIDATION_FAILED, got %v", out["code"])
	}
}

func TestBundleValidateCheck_AlignmentVerdictNotPass(t *testing.T) {
	kv := makeCheckpointKV(map[string]string{"Alignment Verdict": "FAIL"})
	plan := "# Plan\n\n## Checkpoint Summary\n\n" + kv + "\n"
	p := writeTempPlan(t, plan)
	rc, out := runBundleValidateCheckCmd(p)
	if rc != 1 {
		t.Errorf("expected rc=1, got %d", rc)
	}
	if out["code"] != "BUNDLE_VALIDATION_FAILED" {
		t.Errorf("expected code=BUNDLE_VALIDATION_FAILED, got %v", out["code"])
	}
}

func TestBundleValidateCheck_ValidBundle(t *testing.T) {
	dir := t.TempDir()

	// Create sidecar files
	tracePath := filepath.Join(dir, "docs", "plans", "topic")
	if err := os.MkdirAll(tracePath, 0755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(tracePath, "plan.trace.md"), []byte("# trace\n"), 0644); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(tracePath, "plan.compose.md"), []byte("# compose\n"), 0644); err != nil {
		t.Fatal(err)
	}

	kv := makeCheckpointKV(nil)
	plan := "# Plan\n\n## Checkpoint Summary\n\n" + kv + "\n"
	planPath := filepath.Join(dir, "plan.md")
	if err := os.WriteFile(planPath, []byte(plan), 0644); err != nil {
		t.Fatal(err)
	}

	rc, out := runBundleValidateCheckCmd(planPath)
	if rc != 0 {
		t.Errorf("expected rc=0, got %d; output: %v", rc, out)
	}
	if out["status"] != "PASS" {
		t.Errorf("expected status=PASS, got %v", out["status"])
	}
	if out["code"] != "BUNDLE_VALID" {
		t.Errorf("expected code=BUNDLE_VALID, got %v", out["code"])
	}
}

func TestBundleValidateCheck_Help(t *testing.T) {
	rc, _ := runBundleValidateCheckCmd("--help")
	if rc != 0 {
		t.Errorf("expected rc=0 for --help, got %d", rc)
	}
}
