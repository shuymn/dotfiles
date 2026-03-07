package cmd

import (
	"os"
	"path/filepath"
	"testing"
)

func runMarkManagedCmd(args ...string) (int, map[string]any) {
	rc, stdout, _, err := runCommandOutput(MarkManaged(), "", args...)
	if err != nil {
		return 1, map[string]any{"_err": err.Error()}
	}
	return rc, parseJSONResult(stdout)
}

func writeManifest(t *testing.T, dir, content string) string {
	t.Helper()
	p := filepath.Join(dir, "manifest.json")
	if err := os.WriteFile(p, []byte(content), 0644); err != nil {
		t.Fatal(err)
	}
	return p
}

func mkSkillDir(t *testing.T, base, skill string) string {
	t.Helper()
	d := filepath.Join(base, skill)
	if err := os.MkdirAll(d, 0755); err != nil {
		t.Fatal(err)
	}
	return d
}

// TestMarkManaged_Normal: 2スキルが正常にマークされる
func TestMarkManaged_Normal(t *testing.T) {
	tmp := t.TempDir()
	agentsSkills := filepath.Join(tmp, "skills")
	mkSkillDir(t, agentsSkills, "foo")
	mkSkillDir(t, agentsSkills, "bar")

	manifest := writeManifest(t, tmp, `{"version":1,"source_root":"/src","skills":["foo","bar"]}`)

	rc, out := runMarkManagedCmd("--manifest", manifest, "--agents-skills", agentsSkills)
	if rc != 0 {
		t.Errorf("expected rc=0, got %d", rc)
	}
	if out["status"] != "PASS" {
		t.Errorf("expected status=PASS, got %v", out["status"])
	}
	if out["signal.marked"] != float64(2) {
		t.Errorf("expected signal.marked=2, got %v", out["signal.marked"])
	}
	if out["signal.missing"] != float64(0) {
		t.Errorf("expected signal.missing=0, got %v", out["signal.missing"])
	}

	// マーカーファイルの内容を確認
	for _, skill := range []string{"foo", "bar"} {
		markerPath := filepath.Join(agentsSkills, skill, ".dotfiles-managed")
		content, err := os.ReadFile(markerPath)
		if err != nil {
			t.Errorf("marker not found for %s: %v", skill, err)
			continue
		}
		if string(content) != "managed-by-dotfiles\n" {
			t.Errorf("marker content for %s: got %q, want %q", skill, content, "managed-by-dotfiles\n")
		}
	}
}

// TestMarkManaged_MissingSkill: 存在しないスキルはmissingに記録される
func TestMarkManaged_MissingSkill(t *testing.T) {
	tmp := t.TempDir()
	agentsSkills := filepath.Join(tmp, "skills")
	mkSkillDir(t, agentsSkills, "foo")
	// "bar" は作らない

	manifest := writeManifest(t, tmp, `{"version":1,"source_root":"/src","skills":["foo","bar"]}`)

	rc, out := runMarkManagedCmd("--manifest", manifest, "--agents-skills", agentsSkills)
	if rc != 0 {
		t.Errorf("expected rc=0, got %d", rc)
	}
	if out["status"] != "PASS" {
		t.Errorf("expected status=PASS, got %v", out["status"])
	}
	if out["signal.marked"] != float64(1) {
		t.Errorf("expected signal.marked=1, got %v", out["signal.marked"])
	}
	if out["signal.missing"] != float64(1) {
		t.Errorf("expected signal.missing=1, got %v", out["signal.missing"])
	}
	if out["signal.missing_names"] != "bar" {
		t.Errorf("expected signal.missing_names=bar, got %v", out["signal.missing_names"])
	}
}

// TestMarkManaged_EmptySkills: skillsが空なら早期PASSを返す
func TestMarkManaged_EmptySkills(t *testing.T) {
	tmp := t.TempDir()
	agentsSkills := filepath.Join(tmp, "skills")

	manifest := writeManifest(t, tmp, `{"version":1,"source_root":"/src","skills":[]}`)

	rc, out := runMarkManagedCmd("--manifest", manifest, "--agents-skills", agentsSkills)
	if rc != 0 {
		t.Errorf("expected rc=0, got %d", rc)
	}
	if out["status"] != "PASS" {
		t.Errorf("expected status=PASS, got %v", out["status"])
	}
	if out["code"] != "NOTHING_TO_MARK" {
		t.Errorf("expected code=NOTHING_TO_MARK, got %v", out["code"])
	}
}

// TestMarkManaged_ManifestNotFound: マニフェスト未存在はFAIL
func TestMarkManaged_ManifestNotFound(t *testing.T) {
	tmp := t.TempDir()
	agentsSkills := filepath.Join(tmp, "skills")

	rc, out := runMarkManagedCmd("--manifest", "/nonexistent/manifest.json", "--agents-skills", agentsSkills)
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

// TestMarkManaged_InvalidJSON: 不正JSONはFAIL
func TestMarkManaged_InvalidJSON(t *testing.T) {
	tmp := t.TempDir()
	agentsSkills := filepath.Join(tmp, "skills")

	manifest := writeManifest(t, tmp, `{not json}`)

	rc, out := runMarkManagedCmd("--manifest", manifest, "--agents-skills", agentsSkills)
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

// TestMarkManaged_MissingFlags: 必須フラグ欠落はexit 1
func TestMarkManaged_MissingFlags(t *testing.T) {
	rc, _ := runMarkManagedCmd("--agents-skills", "/some/path")
	if rc != 1 {
		t.Errorf("expected rc=1 when --manifest missing, got %d", rc)
	}

	rc, _ = runMarkManagedCmd("--manifest", "/some/manifest.json")
	if rc != 1 {
		t.Errorf("expected rc=1 when --agents-skills missing, got %d", rc)
	}
}

// TestMarkManaged_CustomMarker: カスタムマーカー名が使われる
func TestMarkManaged_CustomMarker(t *testing.T) {
	tmp := t.TempDir()
	agentsSkills := filepath.Join(tmp, "skills")
	mkSkillDir(t, agentsSkills, "foo")

	manifest := writeManifest(t, tmp, `{"version":1,"source_root":"/src","skills":["foo"]}`)

	rc, out := runMarkManagedCmd("--manifest", manifest, "--agents-skills", agentsSkills, "--marker", ".custom-marker")
	if rc != 0 {
		t.Errorf("expected rc=0, got %d", rc)
	}
	if out["status"] != "PASS" {
		t.Errorf("expected status=PASS, got %v", out["status"])
	}

	markerPath := filepath.Join(agentsSkills, "foo", ".custom-marker")
	if _, err := os.Stat(markerPath); err != nil {
		t.Errorf("custom marker not created: %v", err)
	}
}

// TestMarkManaged_MarkerContent: マーカーファイルの内容を検証
func TestMarkManaged_MarkerContent(t *testing.T) {
	tmp := t.TempDir()
	agentsSkills := filepath.Join(tmp, "skills")
	mkSkillDir(t, agentsSkills, "foo")

	manifest := writeManifest(t, tmp, `{"version":1,"source_root":"/src","skills":["foo"]}`)

	rc, _ := runMarkManagedCmd("--manifest", manifest, "--agents-skills", agentsSkills)
	if rc != 0 {
		t.Fatalf("expected rc=0, got %d", rc)
	}

	content, err := os.ReadFile(filepath.Join(agentsSkills, "foo", ".dotfiles-managed"))
	if err != nil {
		t.Fatalf("marker not found: %v", err)
	}
	if string(content) != "managed-by-dotfiles\n" {
		t.Errorf("marker content: got %q, want %q", content, "managed-by-dotfiles\n")
	}
}
