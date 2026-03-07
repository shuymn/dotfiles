package cmd

import (
	"errors"
	"os"
	"path/filepath"
	"testing"
)

func runAuditCodexCmd(args ...string) (int, map[string]any) {
	rc, stdout, _, err := runCommandOutput(AuditCodex(), "", args...)
	if err != nil {
		return 1, map[string]any{"_err": err.Error()}
	}
	return rc, parseJSONResult(stdout)
}

// TestAuditCodex_CodexDirMissing: codex-skills ディレクトリ不在 → PASS/CODEX_DIR_MISSING
func TestAuditCodex_CodexDirMissing(t *testing.T) {
	tmp := t.TempDir()
	agentsSkills := filepath.Join(tmp, "agents-skills")
	codexSkills := filepath.Join(tmp, "nonexistent-codex")
	manifest := writeManifest(t, tmp, `{"version":1,"source_root":"/src","skills":["foo"]}`)

	rc, out := runAuditCodexCmd("--manifest", manifest, "--agents-skills", agentsSkills, "--codex-skills", codexSkills)
	if rc != 0 {
		t.Errorf("expected rc=0, got %d", rc)
	}
	if out["status"] != "PASS" {
		t.Errorf("expected status=PASS, got %v", out["status"])
	}
	if out["code"] != "CODEX_DIR_MISSING" {
		t.Errorf("expected code=CODEX_DIR_MISSING, got %v", out["code"])
	}
}

// TestAuditCodex_CodexDirEmpty: codex-skills 空 → PASS/CODEX_DIR_EMPTY
func TestAuditCodex_CodexDirEmpty(t *testing.T) {
	tmp := t.TempDir()
	agentsSkills := filepath.Join(tmp, "agents-skills")
	codexSkills := filepath.Join(tmp, "codex-skills")
	if err := os.MkdirAll(codexSkills, 0755); err != nil {
		t.Fatal(err)
	}
	manifest := writeManifest(t, tmp, `{"version":1,"source_root":"/src","skills":["foo"]}`)

	rc, out := runAuditCodexCmd("--manifest", manifest, "--agents-skills", agentsSkills, "--codex-skills", codexSkills)
	if rc != 0 {
		t.Errorf("expected rc=0, got %d", rc)
	}
	if out["status"] != "PASS" {
		t.Errorf("expected status=PASS, got %v", out["status"])
	}
	if out["code"] != "CODEX_DIR_EMPTY" {
		t.Errorf("expected code=CODEX_DIR_EMPTY, got %v", out["code"])
	}
}

// TestAuditCodex_CodexOnly: 重複なし（codex_only のみ） → PASS/AUDIT_COMPLETE, duplicates=0
func TestAuditCodex_CodexOnly(t *testing.T) {
	tmp := t.TempDir()
	agentsSkills := filepath.Join(tmp, "agents-skills")
	codexSkills := filepath.Join(tmp, "codex-skills")
	mkSkillDir(t, codexSkills, "skill-a")
	mkSkillDir(t, codexSkills, "skill-b")
	manifest := writeManifest(t, tmp, `{"version":1,"source_root":"/src","skills":["other"]}`)

	rc, out := runAuditCodexCmd("--manifest", manifest, "--agents-skills", agentsSkills, "--codex-skills", codexSkills)
	if rc != 0 {
		t.Errorf("expected rc=0, got %d", rc)
	}
	if out["status"] != "PASS" {
		t.Errorf("expected status=PASS, got %v", out["status"])
	}
	if out["code"] != "AUDIT_COMPLETE" {
		t.Errorf("expected code=AUDIT_COMPLETE, got %v", out["code"])
	}
	if out["signal.duplicates"] != float64(0) {
		t.Errorf("expected signal.duplicates=0, got %v", out["signal.duplicates"])
	}
	if out["signal.codex_only"] != float64(2) {
		t.Errorf("expected signal.codex_only=2, got %v", out["signal.codex_only"])
	}
	if out["signal.pruned"] != float64(0) {
		t.Errorf("expected signal.pruned=0, got %v", out["signal.pruned"])
	}
}

// TestAuditCodex_ManagedDuplicateByManifest: マニフェストに含まれる重複 → managed_duplicate
func TestAuditCodex_ManagedDuplicateByManifest(t *testing.T) {
	tmp := t.TempDir()
	agentsSkills := filepath.Join(tmp, "agents-skills")
	codexSkills := filepath.Join(tmp, "codex-skills")
	// codex側にも agents側にも "foo" が存在
	mkSkillDir(t, codexSkills, "foo")
	mkSkillDir(t, agentsSkills, "foo") // マーカーなし、でもマニフェストに含まれる
	manifest := writeManifest(t, tmp, `{"version":1,"source_root":"/src","skills":["foo"]}`)

	rc, out := runAuditCodexCmd("--manifest", manifest, "--agents-skills", agentsSkills, "--codex-skills", codexSkills)
	if rc != 0 {
		t.Errorf("expected rc=0, got %d", rc)
	}
	if out["signal.duplicates"] != float64(1) {
		t.Errorf("expected signal.duplicates=1, got %v", out["signal.duplicates"])
	}
	if out["signal.managed_duplicates"] != float64(1) {
		t.Errorf("expected signal.managed_duplicates=1, got %v", out["signal.managed_duplicates"])
	}
	if out["signal.external_duplicates"] != float64(0) {
		t.Errorf("expected signal.external_duplicates=0, got %v", out["signal.external_duplicates"])
	}
}

// TestAuditCodex_ManagedDuplicateByMarker: マーカーファイルあり → managed_duplicate
func TestAuditCodex_ManagedDuplicateByMarker(t *testing.T) {
	tmp := t.TempDir()
	agentsSkills := filepath.Join(tmp, "agents-skills")
	codexSkills := filepath.Join(tmp, "codex-skills")
	mkSkillDir(t, codexSkills, "bar")
	mkManagedSkillDir(t, agentsSkills, "bar", ".dotfiles-managed") // マーカーあり
	manifest := writeManifest(t, tmp, `{"version":1,"source_root":"/src","skills":[]}`)

	rc, out := runAuditCodexCmd("--manifest", manifest, "--agents-skills", agentsSkills, "--codex-skills", codexSkills)
	if rc != 0 {
		t.Errorf("expected rc=0, got %d", rc)
	}
	if out["signal.managed_duplicates"] != float64(1) {
		t.Errorf("expected signal.managed_duplicates=1, got %v", out["signal.managed_duplicates"])
	}
	if out["signal.external_duplicates"] != float64(0) {
		t.Errorf("expected signal.external_duplicates=0, got %v", out["signal.external_duplicates"])
	}
}

// TestAuditCodex_ExternalDuplicate: マーカーなし・マニフェスト外 → external_duplicate
func TestAuditCodex_ExternalDuplicate(t *testing.T) {
	tmp := t.TempDir()
	agentsSkills := filepath.Join(tmp, "agents-skills")
	codexSkills := filepath.Join(tmp, "codex-skills")
	mkSkillDir(t, codexSkills, "ext")
	mkSkillDir(t, agentsSkills, "ext") // マーカーなし、マニフェストにも含まれない
	manifest := writeManifest(t, tmp, `{"version":1,"source_root":"/src","skills":[]}`)

	rc, out := runAuditCodexCmd("--manifest", manifest, "--agents-skills", agentsSkills, "--codex-skills", codexSkills)
	if rc != 0 {
		t.Errorf("expected rc=0, got %d", rc)
	}
	if out["signal.external_duplicates"] != float64(1) {
		t.Errorf("expected signal.external_duplicates=1, got %v", out["signal.external_duplicates"])
	}
	if out["signal.managed_duplicates"] != float64(0) {
		t.Errorf("expected signal.managed_duplicates=0, got %v", out["signal.managed_duplicates"])
	}
}

// TestAuditCodex_PruneDuplicates: --prune-duplicates で重複削除 → pruned count 確認
func TestAuditCodex_PruneDuplicates(t *testing.T) {
	tmp := t.TempDir()
	agentsSkills := filepath.Join(tmp, "agents-skills")
	codexSkills := filepath.Join(tmp, "codex-skills")
	mkSkillDir(t, codexSkills, "foo")
	mkSkillDir(t, codexSkills, "bar")
	mkManagedSkillDir(t, agentsSkills, "foo", ".dotfiles-managed")
	mkManagedSkillDir(t, agentsSkills, "bar", ".dotfiles-managed")
	manifest := writeManifest(t, tmp, `{"version":1,"source_root":"/src","skills":["foo","bar"]}`)

	var removed []string
	orig := removeAllFn
	removeAllFn = func(path string) error {
		removed = append(removed, filepath.Base(path))
		return nil
	}
	t.Cleanup(func() { removeAllFn = orig })

	rc, out := runAuditCodexCmd("--manifest", manifest, "--agents-skills", agentsSkills, "--codex-skills", codexSkills, "--prune-duplicates")
	if rc != 0 {
		t.Errorf("expected rc=0, got %d", rc)
	}
	if out["status"] != "PASS" {
		t.Errorf("expected status=PASS, got %v", out["status"])
	}
	if out["signal.pruned"] != float64(2) {
		t.Errorf("expected signal.pruned=2, got %v", out["signal.pruned"])
	}
	if len(removed) != 2 {
		t.Errorf("expected 2 removeAll calls, got %d: %v", len(removed), removed)
	}
}

// TestAuditCodex_DryRun: --prune-duplicates なし → pruned=0
func TestAuditCodex_DryRun(t *testing.T) {
	tmp := t.TempDir()
	agentsSkills := filepath.Join(tmp, "agents-skills")
	codexSkills := filepath.Join(tmp, "codex-skills")
	mkSkillDir(t, codexSkills, "foo")
	mkManagedSkillDir(t, agentsSkills, "foo", ".dotfiles-managed")
	manifest := writeManifest(t, tmp, `{"version":1,"source_root":"/src","skills":["foo"]}`)

	var removeCalled bool
	orig := removeAllFn
	removeAllFn = func(path string) error {
		removeCalled = true
		return nil
	}
	t.Cleanup(func() { removeAllFn = orig })

	rc, out := runAuditCodexCmd("--manifest", manifest, "--agents-skills", agentsSkills, "--codex-skills", codexSkills)
	if rc != 0 {
		t.Errorf("expected rc=0, got %d", rc)
	}
	if out["signal.pruned"] != float64(0) {
		t.Errorf("expected signal.pruned=0, got %v", out["signal.pruned"])
	}
	if removeCalled {
		t.Errorf("expected removeAllFn not to be called in dry-run mode")
	}
}

// TestAuditCodex_ManifestError: マニフェスト読み込み失敗 → FAIL/MANIFEST_ERROR
func TestAuditCodex_ManifestError(t *testing.T) {
	tmp := t.TempDir()
	agentsSkills := filepath.Join(tmp, "agents-skills")
	codexSkills := filepath.Join(tmp, "codex-skills")

	rc, out := runAuditCodexCmd("--manifest", "/nonexistent/manifest.json", "--agents-skills", agentsSkills, "--codex-skills", codexSkills)
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

// TestAuditCodex_MissingRequiredFlags: 必須フラグ欠落 → rc=1
func TestAuditCodex_MissingRequiredFlags(t *testing.T) {
	tmp := t.TempDir()

	rc, _ := runAuditCodexCmd("--agents-skills", tmp, "--codex-skills", tmp)
	if rc != 1 {
		t.Errorf("expected rc=1 when --manifest missing, got %d", rc)
	}

	rc, _ = runAuditCodexCmd("--manifest", "/some/manifest.json", "--codex-skills", tmp)
	if rc != 1 {
		t.Errorf("expected rc=1 when --agents-skills missing, got %d", rc)
	}

	rc, _ = runAuditCodexCmd("--manifest", "/some/manifest.json", "--agents-skills", tmp)
	if rc != 1 {
		t.Errorf("expected rc=1 when --codex-skills missing, got %d", rc)
	}
}

// TestAuditCodex_PruneFailed: RemoveAll エラー → FAIL/PRUNE_FAILED
func TestAuditCodex_PruneFailed(t *testing.T) {
	tmp := t.TempDir()
	agentsSkills := filepath.Join(tmp, "agents-skills")
	codexSkills := filepath.Join(tmp, "codex-skills")
	mkSkillDir(t, codexSkills, "foo")
	mkManagedSkillDir(t, agentsSkills, "foo", ".dotfiles-managed")
	manifest := writeManifest(t, tmp, `{"version":1,"source_root":"/src","skills":["foo"]}`)

	orig := removeAllFn
	removeAllFn = func(path string) error {
		return errors.New("permission denied")
	}
	t.Cleanup(func() { removeAllFn = orig })

	rc, out := runAuditCodexCmd("--manifest", manifest, "--agents-skills", agentsSkills, "--codex-skills", codexSkills, "--prune-duplicates")
	if rc != 1 {
		t.Errorf("expected rc=1, got %d", rc)
	}
	if out["status"] != "FAIL" {
		t.Errorf("expected status=FAIL, got %v", out["status"])
	}
	if out["code"] != "PRUNE_FAILED" {
		t.Errorf("expected code=PRUNE_FAILED, got %v", out["code"])
	}
}
