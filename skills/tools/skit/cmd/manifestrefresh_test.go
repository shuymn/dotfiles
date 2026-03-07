package cmd

import (
	"bytes"
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func runManifestRefreshCmd(args ...string) (int, string) {
	var buf bytes.Buffer
	rc := runManifestRefresh(&buf, args)
	return rc, buf.String()
}

// TestSanitizeName: 各種入力パターンのサニタイズ検証
func TestSanitizeName(t *testing.T) {
	cases := []struct {
		input string
		want  string
	}{
		{"Hello World", "hello-world"},
		{"foo.bar", "foo.bar"},
		{"Foo_Bar-Baz", "foo_bar-baz"},
		{"---foo---", "foo"},
		{"..foo..", "foo"},
		{".foo.", "foo"},
		{"-foo-", "foo"},
		{"foo bar baz", "foo-bar-baz"},
		{"", "unnamed-skill"},
		{"---", "unnamed-skill"},
		{"...", "unnamed-skill"},
		{"abc123", "abc123"},
		{"a.b_c", "a.b_c"},
	}

	for _, tc := range cases {
		got := sanitizeName(tc.input)
		if got != tc.want {
			t.Errorf("sanitizeName(%q) = %q, want %q", tc.input, got, tc.want)
		}
	}
}

// TestSanitizeName_MaxLen: 255文字上限
func TestSanitizeName_MaxLen(t *testing.T) {
	long := strings.Repeat("a", 300)
	got := sanitizeName(long)
	if len(got) != 255 {
		t.Errorf("expected len=255, got %d", len(got))
	}
}

// TestDiscoverSkills: SKILL.md ありのディレクトリのみ検出、ファイル除外、ソート
func TestDiscoverSkills(t *testing.T) {
	tmp := t.TempDir()

	// SKILL.md を持つスキルディレクトリ
	for _, name := range []string{"beta-skill", "alpha-skill"} {
		d := filepath.Join(tmp, name)
		if err := os.MkdirAll(d, 0755); err != nil {
			t.Fatal(err)
		}
		if err := os.WriteFile(filepath.Join(d, "SKILL.md"), []byte("# skill"), 0644); err != nil {
			t.Fatal(err)
		}
	}

	// SKILL.md なしのディレクトリ（除外される）
	noSkill := filepath.Join(tmp, "no-skill-dir")
	if err := os.MkdirAll(noSkill, 0755); err != nil {
		t.Fatal(err)
	}

	// ファイル（除外される）
	if err := os.WriteFile(filepath.Join(tmp, "somefile.txt"), []byte("x"), 0644); err != nil {
		t.Fatal(err)
	}

	skills, err := discoverSkills(tmp)
	if err != nil {
		t.Fatalf("discoverSkills error: %v", err)
	}

	if len(skills) != 2 {
		t.Fatalf("expected 2 skills, got %d: %v", len(skills), skills)
	}
	if skills[0] != "alpha-skill" || skills[1] != "beta-skill" {
		t.Errorf("expected sorted [alpha-skill beta-skill], got %v", skills)
	}
}

// TestDiscoverSkills_Dedup: 複数ディレクトリ名が同一サニタイズ結果になる場合の重複排除
func TestDiscoverSkills_Dedup(t *testing.T) {
	tmp := t.TempDir()

	for _, name := range []string{"foo bar", "foo-bar"} {
		d := filepath.Join(tmp, name)
		if err := os.MkdirAll(d, 0755); err != nil {
			t.Fatal(err)
		}
		if err := os.WriteFile(filepath.Join(d, "SKILL.md"), []byte("# skill"), 0644); err != nil {
			t.Fatal(err)
		}
	}

	skills, err := discoverSkills(tmp)
	if err != nil {
		t.Fatalf("discoverSkills error: %v", err)
	}
	if len(skills) != 1 {
		t.Errorf("expected 1 deduplicated skill, got %d: %v", len(skills), skills)
	}
	if skills[0] != "foo-bar" {
		t.Errorf("expected foo-bar, got %v", skills[0])
	}
}

// TestFormatSourceRoot: 各種相対パス関係の検証
func TestFormatSourceRoot(t *testing.T) {
	cases := []struct {
		sourceRoot   string
		manifestPath string
		want         string
	}{
		{"/a/b/src", "/a/b/src/.dotfiles-managed-skills.json", "."},
		{"/a/b", "/a/b/src/.dotfiles-managed-skills.json", ".."},
		{"/a/sibling", "/a/b/manifest.json", "../sibling"},
	}

	for _, tc := range cases {
		got := formatSourceRoot(tc.sourceRoot, tc.manifestPath)
		if got != tc.want {
			t.Errorf("formatSourceRoot(%q, %q) = %q, want %q", tc.sourceRoot, tc.manifestPath, got, tc.want)
		}
	}
}

// TestManifestRefresh_PrintOnly: --print-only で JSON 出力の構造検証
func TestManifestRefresh_PrintOnly(t *testing.T) {
	tmp := t.TempDir()

	skillDir := filepath.Join(tmp, "my-skill")
	if err := os.MkdirAll(skillDir, 0755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(skillDir, "SKILL.md"), []byte("# skill"), 0644); err != nil {
		t.Fatal(err)
	}

	rc, out := runManifestRefreshCmd("--source", tmp, "--print-only")
	if rc != 0 {
		t.Fatalf("expected rc=0, got %d; output: %s", rc, out)
	}

	var m map[string]any
	if err := json.Unmarshal([]byte(strings.TrimSpace(out)), &m); err != nil {
		t.Fatalf("output is not valid JSON: %v\noutput: %s", err, out)
	}

	if m["version"] != float64(1) {
		t.Errorf("expected version=1, got %v", m["version"])
	}
	skills, ok := m["skills"].([]any)
	if !ok {
		t.Fatalf("expected skills to be array, got %T", m["skills"])
	}
	if len(skills) != 1 || skills[0] != "my-skill" {
		t.Errorf("expected skills=[my-skill], got %v", skills)
	}
	if _, hasSourceRoot := m["source_root"]; !hasSourceRoot {
		t.Error("expected source_root key in manifest")
	}
}

// TestManifestRefresh_WriteManifest: デフォルトパスへのファイル書き込み
func TestManifestRefresh_WriteManifest(t *testing.T) {
	tmp := t.TempDir()

	skillDir := filepath.Join(tmp, "alpha")
	if err := os.MkdirAll(skillDir, 0755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(skillDir, "SKILL.md"), []byte("# skill"), 0644); err != nil {
		t.Fatal(err)
	}

	rc, out := runManifestRefreshCmd("--source", tmp)
	if rc != 0 {
		t.Fatalf("expected rc=0, got %d; output: %s", rc, out)
	}

	defaultPath := filepath.Join(tmp, ".dotfiles-managed-skills.json")
	if _, err := os.Stat(defaultPath); err != nil {
		t.Fatalf("manifest file not created at default path: %v", err)
	}

	content, err := os.ReadFile(defaultPath)
	if err != nil {
		t.Fatal(err)
	}
	var m map[string]any
	if err := json.Unmarshal(content, &m); err != nil {
		t.Fatalf("manifest is not valid JSON: %v", err)
	}
	if m["version"] != float64(1) {
		t.Errorf("expected version=1, got %v", m["version"])
	}

	// log output に manifest_path と managed_skills が含まれるか確認
	if !strings.Contains(out, "manifest_path=") {
		t.Errorf("expected manifest_path in output, got: %s", out)
	}
	if !strings.Contains(out, "managed_skills=1") {
		t.Errorf("expected managed_skills=1 in output, got: %s", out)
	}
}

// TestManifestRefresh_CustomManifestPath: --manifest 指定時の書き込み先
func TestManifestRefresh_CustomManifestPath(t *testing.T) {
	tmp := t.TempDir()

	skillDir := filepath.Join(tmp, "skill-a")
	if err := os.MkdirAll(skillDir, 0755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(skillDir, "SKILL.md"), []byte("# skill"), 0644); err != nil {
		t.Fatal(err)
	}

	customPath := filepath.Join(tmp, "sub", "custom-manifest.json")
	rc, out := runManifestRefreshCmd("--source", tmp, "--manifest", customPath)
	if rc != 0 {
		t.Fatalf("expected rc=0, got %d; output: %s", rc, out)
	}

	if _, err := os.Stat(customPath); err != nil {
		t.Fatalf("manifest not created at custom path: %v", err)
	}
	if !strings.Contains(out, customPath) {
		t.Errorf("expected custom path in output, got: %s", out)
	}
}

// TestManifestRefresh_SourceNotExist: 存在しないディレクトリで exit 1
func TestManifestRefresh_SourceNotExist(t *testing.T) {
	rc, _ := runManifestRefreshCmd("--source", "/nonexistent/path/to/skills")
	if rc != 1 {
		t.Errorf("expected rc=1, got %d", rc)
	}
}

// TestManifestRefresh_NoSkills: スキルなしで空配列
func TestManifestRefresh_NoSkills(t *testing.T) {
	tmp := t.TempDir()

	rc, out := runManifestRefreshCmd("--source", tmp, "--print-only")
	if rc != 0 {
		t.Fatalf("expected rc=0, got %d; output: %s", rc, out)
	}

	var m map[string]any
	if err := json.Unmarshal([]byte(strings.TrimSpace(out)), &m); err != nil {
		t.Fatalf("output is not valid JSON: %v", err)
	}

	skills, ok := m["skills"].([]any)
	if !ok {
		t.Fatalf("expected skills to be array, got %T: %v", m["skills"], m["skills"])
	}
	if len(skills) != 0 {
		t.Errorf("expected empty skills array, got %v", skills)
	}
}

// TestManifestRefresh_MissingSource: --source 未指定で exit 1
func TestManifestRefresh_MissingSource(t *testing.T) {
	rc, _ := runManifestRefreshCmd("--print-only")
	if rc != 1 {
		t.Errorf("expected rc=1 when --source missing, got %d", rc)
	}
}
