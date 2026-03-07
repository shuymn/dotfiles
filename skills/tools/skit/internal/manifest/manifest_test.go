package manifest

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func writeFile(t *testing.T, dir, name, content string) string {
	t.Helper()
	p := filepath.Join(dir, name)
	if err := os.WriteFile(p, []byte(content), 0644); err != nil {
		t.Fatal(err)
	}
	return p
}

func TestLoadValid(t *testing.T) {
	tmp := t.TempDir()
	p := writeFile(t, tmp, "manifest.json", `{"version":1,"source_root":"/src","skills":["foo","bar"]}`)

	m, err := Load(p)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if m.Version != 1 {
		t.Errorf("version: got %d, want 1", m.Version)
	}
	if m.SourceRoot != "/src" {
		t.Errorf("source_root: got %q, want /src", m.SourceRoot)
	}
	if len(m.Skills) != 2 || m.Skills[0] != "foo" || m.Skills[1] != "bar" {
		t.Errorf("skills: got %v, want [foo bar]", m.Skills)
	}
}

func TestLoadEmptySkills(t *testing.T) {
	tmp := t.TempDir()
	p := writeFile(t, tmp, "manifest.json", `{"version":1,"source_root":"/src","skills":[]}`)

	m, err := Load(p)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(m.Skills) != 0 {
		t.Errorf("expected empty skills, got %v", m.Skills)
	}
}

func TestLoadFileNotFound(t *testing.T) {
	_, err := Load("/nonexistent/path/manifest.json")
	if err == nil {
		t.Fatal("expected error, got nil")
	}
}

func TestLoadInvalidJSON(t *testing.T) {
	tmp := t.TempDir()
	p := writeFile(t, tmp, "manifest.json", `{not json}`)

	_, err := Load(p)
	if err == nil {
		t.Fatal("expected error, got nil")
	}
}

func TestLoadEmptyStringInSkills(t *testing.T) {
	tmp := t.TempDir()
	p := writeFile(t, tmp, "manifest.json", `{"version":1,"source_root":"/src","skills":["foo",""]}`)

	_, err := Load(p)
	if err == nil {
		t.Fatal("expected error, got nil")
	}
	if !strings.Contains(err.Error(), "non-empty") {
		t.Errorf("expected 'non-empty' in error, got %q", err.Error())
	}
}

func TestLoadUnknownField(t *testing.T) {
	tmp := t.TempDir()
	p := writeFile(t, tmp, "manifest.json", `{"version":1,"source_root":"/src","skills":[],"unknown":"x"}`)

	_, err := Load(p)
	if err == nil {
		t.Fatal("expected error for unknown field, got nil")
	}
}
