package cmd

import (
	"os"
	"os/exec"
	"path/filepath"
	"testing"
)

func runReconcileCmd(args ...string) (int, map[string]any) {
	rc, stdout, _, err := runCommandOutput(Reconcile(), "", args...)
	if err != nil {
		return 1, map[string]any{"_err": err.Error()}
	}
	return rc, parseJSONResult(stdout)
}

// mkManagedSkillDir creates a skill subdirectory under agentsSkills and, if marker
// is non-empty, writes the marker file inside it.
func mkManagedSkillDir(t *testing.T, agentsSkills, skill, marker string) {
	t.Helper()
	d := filepath.Join(agentsSkills, skill)
	if err := os.MkdirAll(d, 0755); err != nil {
		t.Fatal(err)
	}
	if marker != "" {
		if err := os.WriteFile(filepath.Join(d, marker), []byte(""), 0644); err != nil {
			t.Fatal(err)
		}
	}
}

// TestReconcile_NoStaleSkills: 全スキルがマニフェストに存在、削除なし
func TestReconcile_NoStaleSkills(t *testing.T) {
	tmp := t.TempDir()
	agentsSkills := filepath.Join(tmp, "skills")
	mkManagedSkillDir(t, agentsSkills, "foo", ".dotfiles-managed")
	mkManagedSkillDir(t, agentsSkills, "bar", ".dotfiles-managed")

	manifest := writeManifest(t, tmp, `{"version":1,"source_root":"/src","skills":["foo","bar"]}`)

	rc, out := runReconcileCmd("--manifest", manifest, "--agents-skills", agentsSkills, "--skills-cmd", "bunx --bun skills")
	if rc != 0 {
		t.Errorf("expected rc=0, got %d", rc)
	}
	if out["status"] != "PASS" {
		t.Errorf("expected status=PASS, got %v", out["status"])
	}
	if out["code"] != "NO_STALE_MANAGED_SKILLS" {
		t.Errorf("expected code=NO_STALE_MANAGED_SKILLS, got %v", out["code"])
	}
	if out["signal.removed"] != float64(0) {
		t.Errorf("expected signal.removed=0, got %v", out["signal.removed"])
	}
}

// TestReconcile_RemoveStaleSkills: stale スキルを検出・削除
func TestReconcile_RemoveStaleSkills(t *testing.T) {
	tmp := t.TempDir()
	agentsSkills := filepath.Join(tmp, "skills")
	mkManagedSkillDir(t, agentsSkills, "foo", ".dotfiles-managed")
	mkManagedSkillDir(t, agentsSkills, "stale", ".dotfiles-managed")

	manifest := writeManifest(t, tmp, `{"version":1,"source_root":"/src","skills":["foo"]}`)

	var capturedArgs []string
	orig := execCommandFn
	execCommandFn = func(name string, arg ...string) *exec.Cmd {
		capturedArgs = append([]string{name}, arg...)
		return exec.Command("true")
	}
	t.Cleanup(func() { execCommandFn = orig })

	rc, out := runReconcileCmd("--manifest", manifest, "--agents-skills", agentsSkills, "--skills-cmd", "bunx --bun skills")
	if rc != 0 {
		t.Errorf("expected rc=0, got %d", rc)
	}
	if out["status"] != "PASS" {
		t.Errorf("expected status=PASS, got %v", out["status"])
	}
	if out["code"] != "RECONCILE_COMPLETE" {
		t.Errorf("expected code=RECONCILE_COMPLETE, got %v", out["code"])
	}
	if out["signal.removed"] != float64(1) {
		t.Errorf("expected signal.removed=1, got %v", out["signal.removed"])
	}
	if out["signal.removed_names"] != "stale" {
		t.Errorf("expected signal.removed_names=stale, got %v", out["signal.removed_names"])
	}

	// コマンド引数を検証
	expectedArgs := []string{"bunx", "--bun", "skills", "remove", "-g", "-y", "stale"}
	if len(capturedArgs) != len(expectedArgs) {
		t.Errorf("expected args %v, got %v", expectedArgs, capturedArgs)
	} else {
		for i, a := range expectedArgs {
			if capturedArgs[i] != a {
				t.Errorf("arg[%d]: expected %q, got %q", i, a, capturedArgs[i])
			}
		}
	}
}

// TestReconcile_EmptyManifestSafetyStop: スキル数0はFAIL/EMPTY_MANIFEST
func TestReconcile_EmptyManifestSafetyStop(t *testing.T) {
	tmp := t.TempDir()
	agentsSkills := filepath.Join(tmp, "skills")
	manifest := writeManifest(t, tmp, `{"version":1,"source_root":"/src","skills":[]}`)

	rc, out := runReconcileCmd("--manifest", manifest, "--agents-skills", agentsSkills, "--skills-cmd", "bunx --bun skills")
	if rc != 1 {
		t.Errorf("expected rc=1, got %d", rc)
	}
	if out["status"] != "FAIL" {
		t.Errorf("expected status=FAIL, got %v", out["status"])
	}
	if out["code"] != "EMPTY_MANIFEST" {
		t.Errorf("expected code=EMPTY_MANIFEST, got %v", out["code"])
	}
}

// TestReconcile_ManifestNotFound: 存在しないパスはFAIL/MANIFEST_ERROR
func TestReconcile_ManifestNotFound(t *testing.T) {
	tmp := t.TempDir()
	agentsSkills := filepath.Join(tmp, "skills")

	rc, out := runReconcileCmd("--manifest", "/nonexistent/manifest.json", "--agents-skills", agentsSkills, "--skills-cmd", "bunx --bun skills")
	if rc != 1 {
		t.Errorf("expected rc=1, got %d", rc)
	}
	if out["status"] != "FAIL" {
		t.Errorf("expected status=FAIL, got %v", out["status"])
	}
	if out["code"] != "MANIFEST_ERROR" {
		t.Errorf("expected code=MANIFEST_ERROR, got %v", out["code"])
	}
}

// TestReconcile_InvalidManifestJSON: 不正JSONはFAIL/MANIFEST_ERROR
func TestReconcile_InvalidManifestJSON(t *testing.T) {
	tmp := t.TempDir()
	agentsSkills := filepath.Join(tmp, "skills")
	manifest := writeManifest(t, tmp, `{not json}`)

	rc, out := runReconcileCmd("--manifest", manifest, "--agents-skills", agentsSkills, "--skills-cmd", "bunx --bun skills")
	if rc != 1 {
		t.Errorf("expected rc=1, got %d", rc)
	}
	if out["status"] != "FAIL" {
		t.Errorf("expected status=FAIL, got %v", out["status"])
	}
	if out["code"] != "MANIFEST_ERROR" {
		t.Errorf("expected code=MANIFEST_ERROR, got %v", out["code"])
	}
}

// TestReconcile_AgentsSkillsDirNotExist: ディレクトリ未存在はPASS/NO_STALE_MANAGED_SKILLS
func TestReconcile_AgentsSkillsDirNotExist(t *testing.T) {
	tmp := t.TempDir()
	agentsSkills := filepath.Join(tmp, "nonexistent")
	manifest := writeManifest(t, tmp, `{"version":1,"source_root":"/src","skills":["foo"]}`)

	rc, out := runReconcileCmd("--manifest", manifest, "--agents-skills", agentsSkills, "--skills-cmd", "bunx --bun skills")
	if rc != 0 {
		t.Errorf("expected rc=0, got %d", rc)
	}
	if out["status"] != "PASS" {
		t.Errorf("expected status=PASS, got %v", out["status"])
	}
	if out["code"] != "NO_STALE_MANAGED_SKILLS" {
		t.Errorf("expected code=NO_STALE_MANAGED_SKILLS, got %v", out["code"])
	}
}

// TestReconcile_RemoveCommandFails: コマンド失敗はFAIL/REMOVE_FAILED
func TestReconcile_RemoveCommandFails(t *testing.T) {
	tmp := t.TempDir()
	agentsSkills := filepath.Join(tmp, "skills")
	mkManagedSkillDir(t, agentsSkills, "stale", ".dotfiles-managed")
	manifest := writeManifest(t, tmp, `{"version":1,"source_root":"/src","skills":["foo"]}`)

	orig := execCommandFn
	execCommandFn = func(name string, arg ...string) *exec.Cmd {
		return exec.Command("false")
	}
	t.Cleanup(func() { execCommandFn = orig })

	rc, out := runReconcileCmd("--manifest", manifest, "--agents-skills", agentsSkills, "--skills-cmd", "bunx --bun skills")
	if rc != 1 {
		t.Errorf("expected rc=1, got %d", rc)
	}
	if out["status"] != "FAIL" {
		t.Errorf("expected status=FAIL, got %v", out["status"])
	}
	if out["code"] != "REMOVE_FAILED" {
		t.Errorf("expected code=REMOVE_FAILED, got %v", out["code"])
	}
}

// TestReconcile_MissingRequiredFlags: 必須フラグ欠落はrc=1
func TestReconcile_MissingRequiredFlags(t *testing.T) {
	tmp := t.TempDir()

	rc, _ := runReconcileCmd("--agents-skills", tmp, "--skills-cmd", "bunx --bun skills")
	if rc != 1 {
		t.Errorf("expected rc=1 when --manifest missing, got %d", rc)
	}

	rc, _ = runReconcileCmd("--manifest", "/some/manifest.json", "--skills-cmd", "bunx --bun skills")
	if rc != 1 {
		t.Errorf("expected rc=1 when --agents-skills missing, got %d", rc)
	}

	rc, _ = runReconcileCmd("--manifest", "/some/manifest.json", "--agents-skills", tmp)
	if rc != 1 {
		t.Errorf("expected rc=1 when --skills-cmd missing, got %d", rc)
	}
}

// TestReconcile_ExternalSkillsPreserved: マーカーなしスキルは削除対象外
func TestReconcile_ExternalSkillsPreserved(t *testing.T) {
	tmp := t.TempDir()
	agentsSkills := filepath.Join(tmp, "skills")
	// external: マーカーなし（マニフェストに存在しない）
	mkManagedSkillDir(t, agentsSkills, "external", "")
	// managed: マーカーあり、マニフェストにも存在
	mkManagedSkillDir(t, agentsSkills, "foo", ".dotfiles-managed")

	manifest := writeManifest(t, tmp, `{"version":1,"source_root":"/src","skills":["foo"]}`)

	var called bool
	orig := execCommandFn
	execCommandFn = func(name string, arg ...string) *exec.Cmd {
		called = true
		return exec.Command("true")
	}
	t.Cleanup(func() { execCommandFn = orig })

	rc, out := runReconcileCmd("--manifest", manifest, "--agents-skills", agentsSkills, "--skills-cmd", "bunx --bun skills")
	if rc != 0 {
		t.Errorf("expected rc=0, got %d", rc)
	}
	if out["code"] != "NO_STALE_MANAGED_SKILLS" {
		t.Errorf("expected code=NO_STALE_MANAGED_SKILLS, got %v", out["code"])
	}
	if called {
		t.Errorf("expected no remove command for external skills")
	}
}

// TestReconcile_CustomMarker: カスタムマーカー名の動作確認
func TestReconcile_CustomMarker(t *testing.T) {
	tmp := t.TempDir()
	agentsSkills := filepath.Join(tmp, "skills")
	// .custom-marker でマーク（マニフェストに存在しない → stale）
	mkManagedSkillDir(t, agentsSkills, "stale", ".custom-marker")
	// デフォルトマーカーのみ（カスタムマーカーなし → 検出されない）
	mkManagedSkillDir(t, agentsSkills, "notmanaged", ".dotfiles-managed")

	manifest := writeManifest(t, tmp, `{"version":1,"source_root":"/src","skills":["notmanaged"]}`)

	orig := execCommandFn
	execCommandFn = func(name string, arg ...string) *exec.Cmd {
		return exec.Command("true")
	}
	t.Cleanup(func() { execCommandFn = orig })

	rc, out := runReconcileCmd("--manifest", manifest, "--agents-skills", agentsSkills, "--skills-cmd", "bunx --bun skills", "--marker", ".custom-marker")
	if rc != 0 {
		t.Errorf("expected rc=0, got %d", rc)
	}
	if out["code"] != "RECONCILE_COMPLETE" {
		t.Errorf("expected code=RECONCILE_COMPLETE, got %v", out["code"])
	}
	if out["signal.removed_names"] != "stale" {
		t.Errorf("expected signal.removed_names=stale, got %v", out["signal.removed_names"])
	}
}
