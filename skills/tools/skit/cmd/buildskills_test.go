package cmd

import (
	"bytes"
	"crypto/sha256"
	"fmt"
	"io/fs"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

// skillsSourceRoot returns the skills/src directory relative to this test.
func skillsSourceRoot() string {
	return filepath.Join("..", "..", "..", "src")
}

type fileSnapshot struct {
	digest string
	mode   fs.FileMode
}

func snapshotTree(t *testing.T, root string) map[string]fileSnapshot {
	t.Helper()
	snap := make(map[string]fileSnapshot)
	err := filepath.WalkDir(root, func(path string, d fs.DirEntry, err error) error {
		if err != nil {
			return err
		}
		rel, _ := filepath.Rel(root, path)
		rel = filepath.ToSlash(rel)
		if d.IsDir() {
			snap[rel+"/"] = fileSnapshot{}
			return nil
		}
		data, err := os.ReadFile(path)
		if err != nil {
			return err
		}
		info, err := d.Info()
		if err != nil {
			return err
		}
		snap[rel] = fileSnapshot{
			digest: fmt.Sprintf("%x", sha256.Sum256(data)),
			mode:   info.Mode() & 0o777,
		}
		return nil
	})
	if err != nil {
		t.Fatalf("snapshotTree: %v", err)
	}
	return snap
}

func buildToTempDir(t *testing.T) string {
	t.Helper()
	tmp := t.TempDir()
	artifactRoot := filepath.Join(tmp, "artifacts")
	var buf bytes.Buffer
	if err := buildSkills(&buf, buildSkillsConfig(), skillsSourceRoot(), artifactRoot, false); err != nil {
		t.Fatalf("buildSkills: %v", err)
	}
	return artifactRoot
}

func TestSourceMarkdownUsesExplicitSkillRootForRuntimeRefs(t *testing.T) {
	srcRoot := skillsSourceRoot()
	entries, err := os.ReadDir(srcRoot)
	if err != nil {
		t.Fatalf("ReadDir: %v", err)
	}

	for _, e := range entries {
		if e.Name() == "tests" || !e.IsDir() {
			continue
		}
		skillRoot := filepath.Join(srcRoot, e.Name())
		if err := validateExplicitSkillRootPaths(skillRoot); err != nil {
			t.Errorf("%s: %v", e.Name(), err)
		}
	}
}

func TestBuildOutputsStandaloneArtifacts(t *testing.T) {
	artifactRoot := buildToTempDir(t)

	// Manifest file must exist.
	manifestPath := filepath.Join(artifactRoot, ".dotfiles-managed-skills.json")
	if _, err := os.Stat(manifestPath); err != nil {
		t.Errorf("manifest file missing: %v", err)
	}

	// _shared must not exist.
	if _, err := os.Stat(filepath.Join(artifactRoot, "_shared")); err == nil {
		t.Error("_shared directory exists in artifact root")
	}

	// tests and __pycache__ must not exist.
	for _, name := range []string{"tests", "__pycache__"} {
		matches, _ := filepath.Glob(filepath.Join(artifactRoot, "*", name))
		if len(matches) > 0 {
			t.Errorf("found %s in artifact: %v", name, matches)
		}
	}

	// No .md.tmpl files.
	err := filepath.WalkDir(artifactRoot, func(path string, d fs.DirEntry, err error) error {
		if err != nil {
			return err
		}
		if strings.HasSuffix(d.Name(), ".md.tmpl") {
			t.Errorf("found .md.tmpl in artifact: %s", path)
		}
		if strings.HasSuffix(d.Name(), ".fragments.json") {
			t.Errorf("found .fragments.json in artifact: %s", path)
		}
		return nil
	})
	if err != nil {
		t.Fatalf("WalkDir: %v", err)
	}

	skillPath := filepath.Join(artifactRoot, "commit", "SKILL.md")
	skillContent, err := os.ReadFile(skillPath)
	if err != nil {
		t.Fatalf("ReadFile SKILL.md: %v", err)
	}
	skillText := string(skillContent)
	if !strings.Contains(skillText, "<!-- do not edit: generated from skills/src/commit/SKILL.md; edit source and rebuild -->") {
		t.Error("SKILL.md missing generated notice")
	}
	if !strings.HasPrefix(skillText, "---\nname: commit\n") {
		t.Error("SKILL.md frontmatter should remain at the top")
	}
}

func TestBuildIsIdempotent(t *testing.T) {
	artifactRoot := buildToTempDir(t)
	first := snapshotTree(t, artifactRoot)

	var buf bytes.Buffer
	if err := buildSkills(&buf, buildSkillsConfig(), skillsSourceRoot(), artifactRoot, false); err != nil {
		t.Fatalf("second buildSkills: %v", err)
	}
	second := snapshotTree(t, artifactRoot)

	if len(first) != len(second) {
		t.Errorf("snapshot size changed: %d → %d", len(first), len(second))
	}
	for path, snap1 := range first {
		snap2, ok := second[path]
		if !ok {
			t.Errorf("path disappeared after second build: %s", path)
			continue
		}
		if snap1.digest != snap2.digest {
			t.Errorf("digest changed for %s", path)
		}
		if snap1.mode != snap2.mode {
			t.Errorf("mode changed for %s: %o → %o", path, snap1.mode, snap2.mode)
		}
	}
	for path := range second {
		if _, ok := first[path]; !ok {
			t.Errorf("new path appeared after second build: %s", path)
		}
	}
}
