package managedskills

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

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
		got := SanitizeName(tc.input)
		if got != tc.want {
			t.Errorf("SanitizeName(%q) = %q, want %q", tc.input, got, tc.want)
		}
	}
}

func TestSanitizeNameMaxLen(t *testing.T) {
	long := strings.Repeat("a", 300)
	got := SanitizeName(long)
	if len(got) != 255 {
		t.Errorf("expected len=255, got %d", len(got))
	}
}

func TestDiscoverSkills(t *testing.T) {
	tmp := t.TempDir()

	for _, name := range []string{"beta-skill", "alpha-skill"} {
		d := filepath.Join(tmp, name)
		if err := os.MkdirAll(d, 0755); err != nil {
			t.Fatal(err)
		}
		if err := os.WriteFile(filepath.Join(d, SkillFileName), []byte("# skill"), 0644); err != nil {
			t.Fatal(err)
		}
	}

	if err := os.MkdirAll(filepath.Join(tmp, "no-skill-dir"), 0755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(tmp, "somefile.txt"), []byte("x"), 0644); err != nil {
		t.Fatal(err)
	}

	skills, err := DiscoverSkills(tmp)
	if err != nil {
		t.Fatalf("DiscoverSkills error: %v", err)
	}

	if len(skills) != 2 {
		t.Fatalf("expected 2 skills, got %d: %v", len(skills), skills)
	}
	if skills[0] != "alpha-skill" || skills[1] != "beta-skill" {
		t.Errorf("expected sorted [alpha-skill beta-skill], got %v", skills)
	}
}

func TestDiscoverSkillsDedup(t *testing.T) {
	tmp := t.TempDir()

	for _, name := range []string{"foo bar", "foo-bar"} {
		d := filepath.Join(tmp, name)
		if err := os.MkdirAll(d, 0755); err != nil {
			t.Fatal(err)
		}
		if err := os.WriteFile(filepath.Join(d, SkillFileName), []byte("# skill"), 0644); err != nil {
			t.Fatal(err)
		}
	}

	skills, err := DiscoverSkills(tmp)
	if err != nil {
		t.Fatalf("DiscoverSkills error: %v", err)
	}
	if len(skills) != 1 {
		t.Errorf("expected 1 deduplicated skill, got %d: %v", len(skills), skills)
	}
	if skills[0] != "foo-bar" {
		t.Errorf("expected foo-bar, got %v", skills[0])
	}
}

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
		got := FormatSourceRoot(tc.sourceRoot, tc.manifestPath)
		if got != tc.want {
			t.Errorf("FormatSourceRoot(%q, %q) = %q, want %q", tc.sourceRoot, tc.manifestPath, got, tc.want)
		}
	}
}
